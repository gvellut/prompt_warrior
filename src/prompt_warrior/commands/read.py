from __future__ import annotations

import click

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.core import (
    deepest_active_task_index,
    load_document_for_command,
    task_display_path,
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
    app_ctx.console.print(
        "Copied task content from"
        f" [success]{task_display_path(task.link_path)}[/success]",
        style="highlight",
    )
