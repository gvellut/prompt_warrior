from __future__ import annotations

from collections.abc import Callable

import click
from click.shell_completion import CompletionItem

from .constants import WORK_FILENAME
from .core import parse_work_document, resolve_prompts_dir_from_ctx
from .errors import PromptWarriorError
from .models import SUBTASK_PARENT_BULLETS, AppContext

pass_app_context = click.make_pass_decorator(AppContext)


def shell_complete_task_reference(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    del param

    prompts_dir = resolve_prompts_dir_from_ctx(ctx)
    work_path = prompts_dir / WORK_FILENAME
    if not work_path.exists():
        return []

    try:
        document = parse_work_document(work_path)
    except PromptWarriorError:
        return []

    stems = sorted({task.stem for task in document.tasks if task.stem})
    return [CompletionItem(stem) for stem in stems if stem.startswith(incomplete)]


def shell_complete_subtask_reference(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    del param

    prompts_dir = resolve_prompts_dir_from_ctx(ctx)
    work_path = prompts_dir / WORK_FILENAME
    if not work_path.exists():
        return []

    try:
        document = parse_work_document(work_path)
    except PromptWarriorError:
        return []

    stems = sorted(
        {
            task.stem
            for task in document.tasks
            if task.stem and task.bullet in SUBTASK_PARENT_BULLETS
        }
    )
    return [CompletionItem(stem) for stem in stems if stem.startswith(incomplete)]


def argument_label_words(function: Callable[..., object]) -> Callable[..., object]:
    return click.argument("label_words", nargs=-1, metavar="LABEL_WORDS...")(function)


def argument_task_reference(function: Callable[..., object]) -> Callable[..., object]:
    return click.argument(
        "task_ref",
        metavar="TASK_REF",
        shell_complete=shell_complete_task_reference,
    )(function)
