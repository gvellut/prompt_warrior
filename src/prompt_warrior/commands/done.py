from __future__ import annotations

from pathlib import Path

import click

from prompt_warrior.cli_params import option_recursive, pass_app_context
from prompt_warrior.core import (
    deepest_active_task_index,
    find_task_by_signature,
    load_document_for_command,
    mark_done_and_move_to_bottom,
    parse_work_lines,
    siblings_all_done,
    siblings_in_scope_all_done,
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
) -> tuple[int, bool | None]:
    current_task_index = deepest_active_task_index(document)
    if current_task_index is None:
        raise PromptWarriorError("No active task found to close.")

    closed_signature = task_signature(document.tasks[current_task_index])
    current_signature = closed_signature
    lines = list(document.lines)
    closed_count = 0

    while True:
        document = parse_work_lines(work_path, lines)
        current_task_index = find_task_by_signature(document, current_signature)
        if current_task_index is None:
            raise PromptWarriorError(
                "Could not locate the task to close after internal reordering."
            )

        parent_signature: TaskSignature | None = None
        parent_index = document.tasks[current_task_index].parent_task_index
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
    closed_task_index = find_task_by_signature(updated_document, closed_signature)
    siblings_done = (
        None
        if recursive or closed_task_index is None
        else siblings_in_scope_all_done(updated_document, closed_task_index)
    )

    write_work_lines(work_path, lines)
    return closed_count, siblings_done


def print_close_result(
    app_ctx: AppContext,
    closed_count: int,
    siblings_done: bool | None,
) -> None:
    app_ctx.console.print(f"Marked {closed_count} task(s) as done.", style="success")
    if siblings_done is True:
        app_ctx.console.print(
            "All siblings are also done.",
            style="highlight",
        )
    elif siblings_done is False:
        app_ctx.console.print(
            "Some siblings are not done yet.",
            style="highlight",
        )


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
    closed_count, siblings_done = close_deepest_active_task(
        work_path=work_path,
        document=document,
        recursive=recursive,
    )
    print_close_result(app_ctx, closed_count, siblings_done)
