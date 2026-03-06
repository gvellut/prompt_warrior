from __future__ import annotations

import click

from prompt_warrior.cli_params import (
    argument_label_words,
    pass_app_context,
    shell_complete_subtask_reference,
)
from prompt_warrior.constants import (
    DEFAULT_MAX_FOLDER_TASKS,
    MARKDOWN_EXTENSION,
    PWAR_AGENT,
    PWAR_CORR,
    PWAR_FILENAME,
    PWAR_FOLDER_NAME,
    PWAR_MAX_FOLDER_TASKS,
    PWAR_SUB,
    PWAR_TOP,
)
from prompt_warrior.core import (
    build_task_link_path,
    choose_add_task_folder,
    choose_task_stem,
    deepest_active_task_index,
    ensure_insert_separation,
    insertion_point_for_new_task,
    load_document_for_command,
    make_safe_ascii_component,
    resolve_reference,
    task_display_path,
    write_work_lines,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import (
    BULLET_TO_CHAR,
    SUBTASK_PARENT_BULLETS,
    AddMode,
    AppContext,
    BulletType,
)
from prompt_warrior.rich_error import RichErrorCommand


@click.command(cls=RichErrorCommand, help="Create a new task and add it to __plan.md.")
@argument_label_words
@click.option(
    "-l",
    "--filename",
    "filename",
    envvar=PWAR_FILENAME,
    help="Override filename seed with safe-ASCII conversion.",
)
@click.option(
    "-t",
    "--top",
    is_flag=True,
    envvar=PWAR_TOP,
    help="Insert new task at top of target list (top-level or selected parent).",
)
@click.option(
    "-s",
    "--sub",
    "sub_reference",
    metavar="TASK_REF",
    envvar=PWAR_SUB,
    shell_complete=shell_complete_subtask_reference,
    help="Create as planned subtask under TASK_REF.",
)
@click.option(
    "--max-folder-tasks",
    type=int,
    default=DEFAULT_MAX_FOLDER_TASKS,
    show_default=True,
    envvar=PWAR_MAX_FOLDER_TASKS,
    help=(
        "Max task files per auto-generated folder. Use 0 to keep files at prompts root."
    ),
)
@click.option(
    "--folder-name",
    envvar=PWAR_FOLDER_NAME,
    help="Relative folder for new top-level task files (multiple levels allowed).",
)
@click.option(
    "-c",
    "--corr",
    is_flag=True,
    envvar=PWAR_CORR,
    help="Create as correction child (?) under the deepest active task.",
)
@click.option(
    "-a",
    "--agent",
    "agent_mode",
    is_flag=True,
    envvar=PWAR_AGENT,
    help="Create as agent child (~) under the deepest active task.",
)
@pass_app_context
def add(
    app_ctx: AppContext,
    label_words: tuple[str, ...],
    filename: str | None,
    top: bool,
    sub_reference: str | None,
    max_folder_tasks: int,
    folder_name: str | None,
    corr: bool,
    agent_mode: bool,
) -> None:
    app_ctx.logger.debug(
        "Running add with label_words=%s filename=%s top=%s "
        "sub_reference=%s max_folder_tasks=%s folder_name=%s corr=%s agent_mode=%s",
        label_words,
        filename,
        top,
        sub_reference,
        max_folder_tasks,
        folder_name,
        corr,
        agent_mode,
    )

    if not label_words:
        raise PromptWarriorError(
            "`add` requires positional label text (LABEL_WORDS...)."
        )

    mode_count = int(sub_reference is not None) + int(corr) + int(agent_mode)
    if mode_count > 1:
        raise PromptWarriorError("Use only one of --sub, --corr, or --agent.")

    label = " ".join(label_words).strip()
    if not label:
        raise PromptWarriorError("Task label cannot be empty.")

    if filename is not None:
        label_component = make_safe_ascii_component(filename)
    else:
        label_component = make_safe_ascii_component(label)

    work_path, document = load_document_for_command(app_ctx)

    parent_task_index: int | None = None
    bullet = BulletType.PLANNED
    mode = AddMode.TOP_LEVEL

    if sub_reference is not None:
        resolution = resolve_reference(document, sub_reference)
        parent_task_index = resolution.task_index
        parent_task = document.tasks[parent_task_index]
        if parent_task.bullet not in SUBTASK_PARENT_BULLETS:
            bullet_char = BULLET_TO_CHAR[parent_task.bullet]
            raise PromptWarriorError(
                f"Task '{parent_task.label}' on line "
                f"{parent_task.line_number} is inert ('{bullet_char}'). "
                "`--sub` only allows '-', '*', or '?' tasks."
            )
        mode = AddMode.SUBTASK
    elif corr:
        parent_task_index = deepest_active_task_index(document)
        if parent_task_index is None:
            raise PromptWarriorError(
                "No active task found. `--corr` requires an active task."
            )
        bullet = BulletType.CORRECTION
        mode = AddMode.CORRECTION_CHILD
    elif agent_mode:
        parent_task_index = deepest_active_task_index(document)
        if parent_task_index is None:
            raise PromptWarriorError(
                "No active task found. `--agent` requires an active task."
            )
        bullet = BulletType.AGENT
        mode = AddMode.AGENT_CHILD

    insert_at, indent_raw = insertion_point_for_new_task(
        document,
        mode=mode,
        parent_task_index=parent_task_index,
        top=top,
    )

    stem = choose_task_stem(
        app_ctx,
        document=document,
        parent_task_index=parent_task_index,
        label_component=label_component,
    )
    file_name = f"{stem}{MARKDOWN_EXTENSION}"
    target_folder = choose_add_task_folder(
        document,
        parent_task_index=parent_task_index,
        new_task_stem=stem,
        max_folder_tasks=max_folder_tasks,
        folder_name_override=folder_name,
    )
    task_link_path = build_task_link_path(target_folder, file_name)
    task_path = app_ctx.prompts_dir / task_link_path
    task_path.parent.mkdir(parents=True, exist_ok=True)
    if task_path.exists():
        raise PromptWarriorError(f"Task file already exists: {task_path}")
    task_path.write_text("", encoding="utf-8")

    new_line = (
        f"{indent_raw}{BULLET_TO_CHAR[bullet]} [{label}]({task_link_path})"
        f"{document.newline}"
    )
    lines = list(document.lines)
    ensure_insert_separation(lines, insert_at, document.newline)
    lines.insert(insert_at, new_line)

    write_work_lines(work_path, lines)
    app_ctx.console.print(
        f"Added task: {task_display_path(task_link_path)}", style="success"
    )
