from __future__ import annotations

from pathlib import Path

import click

from prompt_warrior.cli_params import pass_app_context
from prompt_warrior.constants import (
    DEFAULT_INIT_TASK_LABEL,
    FALLBACK_NEWLINE,
    MARKDOWN_EXTENSION,
    PWAR_INIT_TASK_LABEL,
    PWAR_NO_INIT_TASK,
    WORK_FILENAME,
)
from prompt_warrior.core import (
    build_task_link_path,
    choose_unused_prefix,
    compose_stem,
    generated_task_folder_name,
    make_safe_ascii_component,
    task_display_path,
)
from prompt_warrior.errors import PromptWarriorError
from prompt_warrior.models import AppContext
from prompt_warrior.rich_error import RichErrorCommand


@click.command(
    cls=RichErrorCommand,
    help="Initialize the prompts directory and optional initial task.",
)
@click.option(
    "-b",
    "--no-init-task",
    is_flag=True,
    envvar=PWAR_NO_INIT_TASK,
    help="Create prompts directory and __plan.md without creating an initial task.",
)
@click.option(
    "--init-task-label",
    default=DEFAULT_INIT_TASK_LABEL,
    show_default=True,
    envvar=PWAR_INIT_TASK_LABEL,
    help="Label used for the initial task line and markdown filename seed.",
)
@pass_app_context
def init(app_ctx: AppContext, no_init_task: bool, init_task_label: str) -> None:
    prompts_dir = app_ctx.prompts_dir
    work_path = prompts_dir / WORK_FILENAME
    app_ctx.logger.debug(
        "Running init with prompts_dir=%s no_init=%s init_task=%s",
        prompts_dir,
        no_init_task,
        init_task_label,
    )

    if prompts_dir.exists():
        raise PromptWarriorError(f"Prompts directory already exists: {prompts_dir}")

    prompts_dir.mkdir(parents=True, exist_ok=False)

    if no_init_task:
        work_path.write_text("", encoding="utf-8")
        app_ctx.console.print(
            f"Initialized workspace at {prompts_dir}",
            style="success",
        )
        return

    label = init_task_label.strip() or DEFAULT_INIT_TASK_LABEL
    safe_component = make_safe_ascii_component(label)
    prefix = choose_unused_prefix(set())
    stem = compose_stem(prefix, safe_component)
    file_name = f"{stem}{MARKDOWN_EXTENSION}"
    task_link_path = build_task_link_path(
        Path(generated_task_folder_name(prefix)),
        file_name,
    )
    task_path = prompts_dir / task_link_path

    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text("", encoding="utf-8")
    work_path.write_text(
        f"- [{label}]({task_link_path}){FALLBACK_NEWLINE}",
        encoding="utf-8",
    )

    app_ctx.console.print(f"Initialized workspace at {prompts_dir}", style="success")
    app_ctx.console.print(
        "Created initial task:"
        f" [success]{task_display_path(app_ctx, task_link_path)}[/success]",
        style="highlight",
    )
