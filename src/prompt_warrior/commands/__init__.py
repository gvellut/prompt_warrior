from __future__ import annotations

import click

from .add import add
from .commit import commit
from .clean_to_folders import clean_to_folders
from .delete import delete
from .done import done
from .init import init
from .next_task import next_task
from .read import read

__all__ = [
    "add",
    "commit",
    "clean_to_folders",
    "delete",
    "done",
    "init",
    "next_task",
    "read",
]


def register_commands(cli: click.Group) -> None:
    cli.add_command(init)
    cli.add_command(add)
    cli.add_command(done)
    cli.add_command(next_task)
    cli.add_command(read)
    cli.add_command(commit)
    cli.add_command(delete)
    cli.add_command(clean_to_folders)
