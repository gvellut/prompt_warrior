from __future__ import annotations

import click
from rich.console import Console

from .constants import RICH_THEME
from .models import AppContext


class RichErrorCommand(click.Command):
    """A command class that prints domain errors with Rich styling."""

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except click.exceptions.Exit:
            raise
        except click.Abort:
            raise
        except Exception as exc:  # noqa: BLE001
            app_ctx = ctx.find_object(AppContext)
            console = app_ctx.console if app_ctx else Console(theme=RICH_THEME)
            debug = app_ctx.debug if app_ctx else False

            if isinstance(exc, click.ClickException):
                message = exc.format_message()
                exit_code = exc.exit_code
            else:
                message = str(exc) if str(exc) else exc.__class__.__name__
                exit_code = 1

            console.print(message, style="error")
            if debug:
                console.print_exception()

            raise click.exceptions.Exit(exit_code) from exc
