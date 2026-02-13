from __future__ import annotations

import click

from .add import register as register_add
from .commit import register as register_commit
from .delete import register as register_delete
from .done import register as register_done
from .init import register as register_init
from .next_task import register as register_next
from .read import register as register_read


def register_commands(cli: click.Group) -> None:
    register_init(cli)
    register_add(cli)
    register_done(cli)
    register_next(cli)
    register_read(cli)
    register_commit(cli)
    register_delete(cli)
