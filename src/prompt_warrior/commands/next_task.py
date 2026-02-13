from __future__ import annotations

import builtins

import click

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.core import (
    child_task_indices,
    copy_task_content,
    deepest_active_task_index,
    load_document_for_command,
    render_task_line,
    write_work_lines,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import ACTIONABLE_BULLETS, AppContext, BulletType
from prompt_warrior.rich_error import RichErrorCommand


@click.command(
    name="next",
    cls=RichErrorCommand,
    help="Activate the next task and copy its markdown file content to the clipboard.",
)
@pass_app_context
def next_task(app_ctx: AppContext) -> None:
    app_ctx.logger.debug("Running next")
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
        raise PromptWarriorError(
            "There is already an active task at this level. Run `pwr done` first."
        )

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
    task_path = copy_task_content(app_ctx, task)

    lines = list(document.lines)
    lines[task.line_index] = render_task_line(task, bullet=BulletType.ACTIVE)
    write_work_lines(work_path, lines)

    app_ctx.console.print(f"Activated task: {task.label}", style="success")
    app_ctx.console.print(
        f"Copied task content from {task_path.name}",
        style="highlight",
    )
