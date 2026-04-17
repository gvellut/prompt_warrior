from __future__ import annotations

import click
from rich.text import Text

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.core import (
    deepest_active_task_index,
    format_level_name,
    load_document_for_command,
    remaining_relevant_siblings_count,
    task_display_path,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import AppContext, BulletType, TaskLine, WorkDocument
from prompt_warrior.rich_error import RichErrorCommand


def build_current_lines(
    app_ctx: AppContext,
    document: WorkDocument,
    task_index: int,
) -> tuple[Text, ...]:
    task = document.tasks[task_index]
    lines = [
        Text.assemble(
            ("Current task: ", "success"),
            (task.label, "highlight"),
        ),
        Text.assemble(
            ("Path: ", "success"),
            (task_display_path(app_ctx, task.link_path), "highlight"),
        ),
        build_remaining_tasks_line(document, task_index),
    ]

    if task.depth == 0:
        return tuple(lines)

    lines.append(Text("Hierarchy (bottom to top):", style="success"))
    lines.extend(build_hierarchy_lines(document, task_index))
    return tuple(lines)


def build_remaining_tasks_line(document: WorkDocument, task_index: int) -> Text:
    task = document.tasks[task_index]
    level_name = format_level_name(task.depth)
    remaining_after_current = max(
        remaining_relevant_siblings_count(document, task_index) - 1,
        0,
    )
    if remaining_after_current == 0:
        count_text = "No other remaining task."
    else:
        plural = "s" if remaining_after_current > 1 else ""
        count_text = f"{remaining_after_current} remaining task{plural} after current."

    return Text.assemble(
        (f"{level_name}: ", "success"),
        (count_text, "highlight"),
    )


def build_hierarchy_lines(document: WorkDocument, task_index: int) -> tuple[Text, ...]:
    hierarchy_indices: list[int] = []
    current_index: int | None = task_index
    while current_index is not None:
        hierarchy_indices.append(current_index)
        current_index = document.tasks[current_index].parent_task_index

    return tuple(
        Text(
            format_hierarchy_label(
                document.tasks[index],
                is_current=index == task_index,
            ),
            style="highlight",
        )
        for index in hierarchy_indices
    )


def format_hierarchy_label(task: TaskLine, *, is_current: bool) -> str:
    label = task.label
    if not is_current:
        return label
    if task.is_correction:
        return f"{label} (correction)"
    if task.bullet == BulletType.AGENT:
        return f"{label} (agent)"
    return label


@click.command(
    cls=RichErrorCommand,
    help="Display the deepest active task and its current context.",
)
@pass_app_context
def current(app_ctx: AppContext) -> None:
    app_ctx.logger.debug("Running current")
    _, document = load_document_for_command(app_ctx)

    current_task_index = deepest_active_task_index(document)
    if current_task_index is None:
        raise PromptWarriorError("No active task found to display.")

    for line in build_current_lines(app_ctx, document, current_task_index):
        app_ctx.console.print(line)
