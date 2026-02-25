from __future__ import annotations

from pathlib import Path

import click
from rich.tree import Tree

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.constants import (
    DEFAULT_MAX_FOLDER_TASKS,
    PWAR_CLEAN_TO_FOLDERS_DRY_RUN,
    PWAR_MAX_FOLDER_TASKS,
)
from prompt_warrior.core import (
    apply_clean_to_folders_plan,
    load_document_for_command,
    plan_clean_to_folders,
)
from prompt_warrior.models import AppContext, CleanToFoldersPlan
from prompt_warrior.rich_error import RichErrorCommand


def _render_projected_task_tree(app_ctx: AppContext, plan: CleanToFoldersPlan) -> None:
    tree = Tree(str(app_ctx.prompts_dir))
    folder_children: dict[tuple[str, ...], set[str]] = {}
    folder_files: dict[tuple[str, ...], set[str]] = {}

    for link_path in plan.projected_task_link_paths.values():
        path = Path(link_path)
        folder_parts = tuple(path.parent.parts) if path.parent != Path(".") else ()
        folder_files.setdefault(folder_parts, set()).add(path.name)

        current_parts: tuple[str, ...] = ()
        for part in folder_parts:
            folder_children.setdefault(current_parts, set()).add(part)
            current_parts = (*current_parts, part)

    def add_nodes(node: Tree, folder_parts: tuple[str, ...]) -> None:
        for child_folder in sorted(
            folder_children.get(folder_parts, set()), key=str.casefold
        ):
            child_parts = (*folder_parts, child_folder)
            child_node = node.add(child_folder)
            add_nodes(child_node, child_parts)

        for file_name in sorted(
            folder_files.get(folder_parts, set()),
            key=str.casefold,
        ):
            node.add(file_name)

    add_nodes(tree, ())
    app_ctx.console.print(tree)


@click.command(
    cls=RichErrorCommand,
    help=(
        "Move current root-level task files into generated folders "
        "and rewrite __plan.md links."
    ),
)
@click.option(
    "--max-folder-tasks",
    type=int,
    default=DEFAULT_MAX_FOLDER_TASKS,
    show_default=True,
    envvar=PWAR_MAX_FOLDER_TASKS,
    help="Max task files per generated folder. Use 0 to disable foldering (no-op).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    envvar=PWAR_CLEAN_TO_FOLDERS_DRY_RUN,
    help=(
        "Preview the projected task-file tree without moving files "
        "or editing __plan.md."
    ),
)
@pass_app_context
def clean_to_folders(
    app_ctx: AppContext,
    max_folder_tasks: int,
    dry_run: bool,
) -> None:
    app_ctx.logger.debug(
        "Running clean-to-folders with max_folder_tasks=%s dry_run=%s",
        max_folder_tasks,
        dry_run,
    )
    work_path, document = load_document_for_command(app_ctx)
    plan = plan_clean_to_folders(
        app_ctx,
        document,
        max_folder_tasks=max_folder_tasks,
    )

    if dry_run:
        if plan.noop_reason is not None:
            app_ctx.console.print(plan.noop_reason, style="warning")
        _render_projected_task_tree(app_ctx, plan)
        app_ctx.console.print(
            (
                "Would move "
                f"{len(plan.moves)} task file(s) into "
                f"{len(plan.created_folder_rel_paths)} new folder(s); "
                f"would update {len(plan.rewrites)} link(s) in __plan.md."
            ),
            style="highlight",
        )
        return

    if plan.noop_reason is not None:
        app_ctx.console.print(plan.noop_reason, style="warning")
        return

    apply_clean_to_folders_plan(app_ctx, document, work_path, plan)
    app_ctx.console.print(
        (
            "Moved "
            f"{len(plan.moves)} task file(s) into "
            f"{len(plan.created_folder_rel_paths)} new folder(s)."
        ),
        style="success",
    )
    app_ctx.console.print(
        f"Updated {len(plan.rewrites)} link(s) in __plan.md.",
        style="highlight",
    )
