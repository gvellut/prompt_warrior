from __future__ import annotations

from click.shell_completion import BashComplete, ZshComplete, add_completion_class

_ZSH_COMMAND_GUARD = "(( ! $+commands[%(prog_name)s] )) && return 1"
_ZSH_COMMAND_OR_FUNCTION_GUARD = (
    "(( ! $+commands[%(prog_name)s] && ! $+functions[%(prog_name)s] )) && return 1"
)
_ZSH_ENV_EXEC_PREFIX = "$(env COMP_WORDS="
_ZSH_DIRECT_EXEC_PREFIX = "$(COMP_WORDS="
_BASH_ENV_EXEC_PREFIX = "response=$(env COMP_WORDS="
_BASH_DIRECT_EXEC_PREFIX = "response=$(COMP_WORDS="


class FunctionAwareZshComplete(ZshComplete):
    source_template = ZshComplete.source_template.replace(
        _ZSH_COMMAND_GUARD,
        _ZSH_COMMAND_OR_FUNCTION_GUARD,
    ).replace(
        _ZSH_ENV_EXEC_PREFIX,
        _ZSH_DIRECT_EXEC_PREFIX,
    )


class FunctionAwareBashComplete(BashComplete):
    source_template = BashComplete.source_template.replace(
        _BASH_ENV_EXEC_PREFIX,
        _BASH_DIRECT_EXEC_PREFIX,
    )


def register_shell_completion_overrides() -> None:
    add_completion_class(FunctionAwareZshComplete, name="zsh")
    add_completion_class(FunctionAwareBashComplete, name="bash")
