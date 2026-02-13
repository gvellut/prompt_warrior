from __future__ import annotations

import click

from prompt_warrior.cli_params import argument_task_reference, pass_app_context
from prompt_warrior.constants import PWAR_KEEP_CHILDREN
from prompt_warrior.core import (
    collect_subtree_indices,
    delete_task_block,
    delete_task_keep_children,
    load_document_for_command,
    remove_task_files,
    resolve_reference,
    write_work_lines,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import AppContext, BulletType
from prompt_warrior.rich_error import RichErrorCommand


@click.command(
    cls=RichErrorCommand,
    help="Delete a task by reference and optionally keep/promote its direct children.",
)
@argument_task_reference
@click.option(
    "--keep-children",
    is_flag=True,
    envvar=PWAR_KEEP_CHILDREN,
    help="Delete only the target task and promote direct children to the target level.",
)
@pass_app_context
def delete(app_ctx: AppContext, task_ref: str, keep_children: bool) -> None:
    app_ctx.logger.debug(
        "Running delete with task_ref=%s keep_children=%s",
        task_ref,
        keep_children,
    )
    work_path, document = load_document_for_command(app_ctx)

    resolution = resolve_reference(document, task_ref)
    task_index = resolution.task_index
    task = document.tasks[task_index]

    descendants = collect_subtree_indices(document, task_index)[1:]
    direct_children_count = len(task.child_task_indices)

    if task.bullet == BulletType.ACTIVE or direct_children_count > 0:
        confirmation_message = (
            f"Delete task '{task.label}' on line {task.line_number}? "
            f"direct children: {direct_children_count}, "
            f"total descendants: {len(descendants)}"
        )
        if not click.confirm(confirmation_message, default=False):
            raise PromptWarriorError("Delete cancelled by user.")

    if keep_children:
        lines = delete_task_keep_children(document, task_index)
        remove_task_files(app_ctx, [task])
    else:
        lines = delete_task_block(document, task_index)
        delete_indices = collect_subtree_indices(document, task_index)
        remove_task_files(app_ctx, [document.tasks[index] for index in delete_indices])

    write_work_lines(work_path, lines)
    app_ctx.console.print(f"Deleted task: {task.label}", style="success")
