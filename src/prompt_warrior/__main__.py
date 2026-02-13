from __future__ import annotations

import logging
from pathlib import Path

import click
from rich.console import Console

from .clipboard import select_clipboard_provider
from .commands import register_commands
from .constants import DEFAULT_PROMPTS_DIR, PWAR_DEBUG, PWAR_PROMPTS_DIR, RICH_THEME
from .models import AppContext


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    envvar=PWAR_DEBUG,
    help="Enable debug logging and stack traces on command errors.",
)
@click.option(
    "--prompts-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path(DEFAULT_PROMPTS_DIR),
    show_default=True,
    envvar=PWAR_PROMPTS_DIR,
    help="Directory containing prompts and battle.md.",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool, prompts_dir: Path) -> None:
    """Prompt Warrior task CLI."""
    console = Console(theme=RICH_THEME)
    logger = logging.getLogger("prompt_warrior")

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(levelname)s %(message)s",
        )
    else:
        logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.debug("Debug mode enabled.")

    app_ctx = AppContext(
        debug=debug,
        prompts_dir=prompts_dir,
        console=console,
        logger=logger,
        clipboard=select_clipboard_provider(),
    )
    ctx.obj = app_ctx


register_commands(cli)

if __name__ == "__main__":
    cli()
