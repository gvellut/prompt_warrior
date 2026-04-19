from __future__ import annotations

import builtins
import time

import click
from rich.console import Group
from rich.text import Text

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.constants import (
    DEFAULT_BRANCH_COMMAND,
    DEFAULT_BRANCH_COPY_INTERVAL,
    PWAR_BRANCH,
    PWAR_BRANCH_COMMAND,
    PWAR_BRANCH_COPY_INTERVAL,
)
from prompt_warrior.core import (
    child_task_indices,
    copy_task_content,
    deepest_active_task_index,
    format_level_name,
    load_document_for_command,
    render_task_line,
    task_display_path,
    write_work_lines,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import ACTIONABLE_BULLETS, AppContext, BulletType
from prompt_warrior.rich_error import RichErrorCommand


def build_activated_task_line(app_ctx: AppContext, task) -> Text:
    return Text.assemble(
        ("Activated task: ", "success"),
        (f"'{task.label}'", "label_highlight"),
        (" ", "success"),
        (task_display_path(app_ctx, task.link_path), "highlight"),
    )


@click.command(
    name="next",
    cls=RichErrorCommand,
    help="Activate the next task and copy its markdown file content to the clipboard.",
)
@click.option(
    "--branch",
    is_flag=True,
    envvar=PWAR_BRANCH,
    help="Also copy and print a branch command for the activated task.",
)
@click.option(
    "--branch-command",
    default=DEFAULT_BRANCH_COMMAND,
    show_default=True,
    envvar=PWAR_BRANCH_COMMAND,
    help="Command prefix used for the branch command.",
)
@click.option(
    "--branch-copy-interval",
    type=int,
    default=DEFAULT_BRANCH_COPY_INTERVAL,
    show_default=True,
    envvar=PWAR_BRANCH_COPY_INTERVAL,
    help="Delay before branch-command clipboard copy, in 100ms units.",
)
@pass_app_context
def next_task(
    app_ctx: AppContext,
    branch: bool,
    branch_command: str,
    branch_copy_interval: int,
) -> None:
    app_ctx.logger.debug(
        "Running next with branch=%s branch_command=%s branch_copy_interval=%s",
        branch,
        branch_command,
        branch_copy_interval,
    )
    work_path, document = load_document_for_command(app_ctx)

    deepest_active = deepest_active_task_index(document)
    if deepest_active is None:
        scope_parent: int | None = None
    elif document.tasks[deepest_active].child_task_indices:
        scope_parent = deepest_active
    else:
        scope_parent = None

    scope_tasks = child_task_indices(document, scope_parent)

    scope_active = [
        index
        for index in scope_tasks
        if document.tasks[index].bullet == BulletType.ACTIVE
    ]
    if scope_active:
        active_task_index = deepest_active_task_index(document)
        if active_task_index is None:
            raise PromptWarriorError(
                "There is already an active task. Run `pwr done` first."
            )
        active_task = document.tasks[active_task_index]
        raise build_active_task_error(app_ctx, active_task)

    next_candidate = builtins.next(
        (
            index
            for index in scope_tasks
            if document.tasks[index].bullet in ACTIONABLE_BULLETS
        ),
        None,
    )

    if next_candidate is None:
        if scope_parent is not None:
            raise PromptWarriorError(
                "No remaining '-' or '?' child task. "
                "Run `pwr done` to close the parent first."
            )
        raise PromptWarriorError("No remaining '-' or '?' top-level task to activate.")

    task = document.tasks[next_candidate]
    copy_task_content(app_ctx, task)
    branch_line: Text | None = None
    if branch:
        normalized_branch_command = branch_command.strip()
        if not normalized_branch_command:
            raise PromptWarriorError("--branch-command cannot be empty.")
        if branch_copy_interval < 0:
            raise PromptWarriorError("--branch-copy-interval must be >= 0.")
        time.sleep(branch_copy_interval / 10)
        app_ctx.clipboard.copy(f"{normalized_branch_command} {task.stem}")
        branch_line = Text()
        branch_line.append(normalized_branch_command, style="highlight")
        branch_line.append(" ")
        branch_line.append(task.stem, style="success")

    lines = list(document.lines)
    lines[task.line_index] = render_task_line(task, bullet=BulletType.ACTIVE)
    write_work_lines(work_path, lines)

    app_ctx.console.print(build_activated_task_line(app_ctx, task))
    app_ctx.console.print(
        "Copied task content.",
        style="highlight",
    )
    if branch_line is not None:
        app_ctx.console.print(branch_line)


def build_active_task_error(app_ctx: AppContext, task) -> PromptWarriorError:
    lines = build_active_task_error_lines(app_ctx, task)
    return PromptWarriorError(
        "\n".join(line.plain for line in lines),
        renderable=Group(*lines),
    )


def build_active_task_error_lines(app_ctx: AppContext, task) -> tuple[Text, ...]:
    error_line = Text("There is already an active task. Run `pwr done` first.")
    error_line.stylize("error")

    active_line = Text.assemble(
        ("Active task: ", "success"),
        (task.label, "highlight"),
    )
    level_line = Text.assemble(
        ("Level: ", "success"),
        (format_level_name(task.depth), "highlight"),
    )
    path_line = Text.assemble(
        ("Path: ", "success"),
        (task_display_path(app_ctx, task.link_path), "highlight"),
    )
    return (error_line, active_line, level_line, path_line)
