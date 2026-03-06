from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import click

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.constants import PWAR_RECURSIVE
from prompt_warrior.core import (
    deepest_active_task_index,
    find_task_by_signature,
    load_document_for_command,
    mark_done_and_move_to_bottom,
    parse_work_lines,
    remaining_relevant_siblings_count,
    siblings_all_done,
    task_display_path,
    task_signature,
    write_work_lines,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import AppContext, BulletType, TaskSignature, WorkDocument
from prompt_warrior.rich_error import RichErrorCommand


def close_deepest_active_task(
    work_path: Path,
    document: WorkDocument,
    recursive: bool,
) -> tuple[int, int, int, str]:
    current_task_index = deepest_active_task_index(document)
    if current_task_index is None:
        raise PromptWarriorError("No active task found to close.")

    current_task = document.tasks[current_task_index]
    initial_link_path = current_task.link_path
    current_signature = task_signature(current_task)
    shallowest_signature = current_signature
    shallowest_depth = current_task.depth
    lines = list(document.lines)
    closed_count = 0

    while True:
        document = parse_work_lines(work_path, lines)
        current_task_index = find_task_by_signature(document, current_signature)
        if current_task_index is None:
            raise PromptWarriorError(
                "Could not locate the task to close after internal reordering."
            )

        current_task = document.tasks[current_task_index]
        if current_task.depth < shallowest_depth:
            shallowest_depth = current_task.depth
            shallowest_signature = task_signature(current_task)

        parent_signature: TaskSignature | None = None
        parent_index = current_task.parent_task_index
        if parent_index is not None:
            parent_signature = task_signature(document.tasks[parent_index])

        lines = mark_done_and_move_to_bottom(document, current_task_index)
        closed_count += 1

        if not recursive or parent_signature is None:
            break

        updated_document = parse_work_lines(work_path, lines)
        updated_parent_index = find_task_by_signature(
            updated_document, parent_signature
        )
        if updated_parent_index is None:
            break

        parent_task = updated_document.tasks[updated_parent_index]
        if parent_task.bullet == BulletType.AGENT:
            break

        if parent_task.bullet == BulletType.DONE:
            break

        if not siblings_all_done(updated_document, updated_parent_index):
            break

        current_signature = task_signature(parent_task)

    updated_document = parse_work_lines(work_path, lines)
    scope_task_index = find_task_by_signature(updated_document, shallowest_signature)
    if scope_task_index is None:
        raise PromptWarriorError(
            "Could not locate the closed task scope after internal reordering."
        )

    remaining_tasks_in_scope = remaining_relevant_siblings_count(
        updated_document,
        scope_task_index,
    )

    write_work_lines(work_path, lines)
    return closed_count, shallowest_depth, remaining_tasks_in_scope, initial_link_path


def format_level_name(depth: int) -> str:
    if depth == 0:
        return "Top level"
    return f"Sublevel {depth}"


def print_close_result(
    app_ctx: AppContext,
    closed_count: int,
    shallowest_depth: int,
    remaining_tasks_in_scope: int,
    initial_link_path: str,
) -> None:
    display_path = task_display_path(initial_link_path)
    app_ctx.console.print(
        f"Marked {closed_count} task(s) as done starting with {display_path}.",
        style="success",
    )
    level_name = format_level_name(shallowest_depth)
    if remaining_tasks_in_scope == 0:
        app_ctx.console.print(
            f"{level_name}: no remaining relevant task.",
            style="highlight",
        )
        return

    plural = "s" if remaining_tasks_in_scope > 1 else ""
    app_ctx.console.print(
        f"{level_name}: {remaining_tasks_in_scope} remaining relevant task{plural}.",
        style="highlight",
    )


def option_recursive(function: Callable[..., object]) -> Callable[..., object]:
    return click.option(
        "--recursive",
        "-r",
        is_flag=True,
        envvar=PWAR_RECURSIVE,
        help="Also mark parent tasks done when all siblings are done.",
    )(function)


@click.command(
    cls=RichErrorCommand,
    help=(
        "Mark the deepest active task as done "
        "and move it to the end of its sibling list."
    ),
)
@option_recursive
@pass_app_context
def done(app_ctx: AppContext, recursive: bool) -> None:
    app_ctx.logger.debug("Running done with recursive=%s", recursive)
    work_path, document = load_document_for_command(app_ctx)
    closed_count, shallowest_depth, remaining_tasks_in_scope, initial_link_path = (
        close_deepest_active_task(
            work_path=work_path,
            document=document,
            recursive=recursive,
        )
    )
    print_close_result(
        app_ctx,
        closed_count,
        shallowest_depth,
        remaining_tasks_in_scope,
        initial_link_path,
    )
