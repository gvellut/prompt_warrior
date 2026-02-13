from __future__ import annotations

import click

from prompt_warrior.cli_params import option_recursive, pass_app_context
from prompt_warrior.constants import (
    DEFAULT_ADD_ALL_COMMAND,
    DEFAULT_COMMIT_COMMAND,
    PWAR_ADD_ALL_COMMAND,
    PWAR_COMMIT_COMMAND,
    PWAR_NO_DONE,
)
from prompt_warrior.core import (
    build_commit_command,
    deepest_active_task_index,
    load_document_for_command,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import AppContext
from prompt_warrior.rich_error import RichErrorCommand
from .done import close_deepest_active_task, print_close_result


@click.command(
    cls=RichErrorCommand,
    help="Copy a commit command based on the deepest active task label.",
)
@click.option(
    "-c",
    "--commit-command",
    default=DEFAULT_COMMIT_COMMAND,
    show_default=True,
    envvar=PWAR_COMMIT_COMMAND,
    help="Command prefix used for the commit step.",
)
@click.option(
    "-a",
    "--add-all-command",
    default=DEFAULT_ADD_ALL_COMMAND,
    show_default=True,
    envvar=PWAR_ADD_ALL_COMMAND,
    help="Command prefix used for the add-all step.",
)
@click.option(
    "-n",
    "--no-done",
    is_flag=True,
    envvar=PWAR_NO_DONE,
    help="Do not mark the deepest active task as done.",
)
@option_recursive
@pass_app_context
def commit(
    app_ctx: AppContext,
    commit_command: str,
    add_all_command: str,
    no_done: bool,
    recursive: bool,
) -> None:
    app_ctx.logger.debug(
        "Running commit with commit_command=%s add_all_command=%s no_done=%s "
        "recursive=%s",
        commit_command,
        add_all_command,
        no_done,
        recursive,
    )
    work_path, document = load_document_for_command(app_ctx)

    current_task_index = deepest_active_task_index(document)
    if current_task_index is None:
        raise PromptWarriorError("No active task found to commit.")

    task = document.tasks[current_task_index]
    command_text = build_commit_command(
        task_label=task.label,
        add_all_command=add_all_command,
        commit_command=commit_command,
    )
    app_ctx.clipboard.copy(command_text)
    app_ctx.console.print(command_text, style="highlight")

    if no_done:
        return

    closed_count, siblings_done = close_deepest_active_task(
        work_path=work_path,
        document=document,
        recursive=recursive,
    )
    print_close_result(app_ctx, closed_count, siblings_done)
