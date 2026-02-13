from __future__ import annotations

import click

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.core import (
    copy_task_content,
    deepest_active_task_index,
    load_document_for_command,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import AppContext
from prompt_warrior.rich_error import RichErrorCommand


@click.command(
    cls=RichErrorCommand,
    help="Copy the deepest active task markdown content to the clipboard.",
)
@pass_app_context
def read(app_ctx: AppContext) -> None:
    app_ctx.logger.debug("Running read")
    _, document = load_document_for_command(app_ctx)

    current_task_index = deepest_active_task_index(document)
    if current_task_index is None:
        raise PromptWarriorError("No active task found to read.")

    task = document.tasks[current_task_index]
    task_path = copy_task_content(app_ctx, task)
    app_ctx.console.print(
        f"Copied task content from {task_path.name}",
        style="highlight",
    )
