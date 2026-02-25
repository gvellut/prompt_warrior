This repository is a Python CLI program that manages prompts for tasks for a LLM. 

The prompts are stored as Markdown (but the format is irrelevant because it is not read by the tool except as an opaque text).

The prompts are manually managed and passed to the LLM explicitly by the user (it is not a task management tool for autonomous development by the LLM).

There is a table of content of tasks : this links to prompts in Markdown format and has memory of what is being worked on and the order. The tasks can be ordered in a hierarchy.

The code is organized as:
- `src/prompt_warrior/__main__.py` for the entrypoint.
- `src/prompt_warrior/commands/*.py` for one file per command.
- `src/prompt_warrior/core.py`, `src/prompt_warrior/models.py`, and `src/prompt_warrior/constants.py` for shared logic/models/config.
- `src/prompt_warrior/clipboard.py` for system-specific (macos, Windows, Linux) copying to clipboard.


## Lint
After making edits to the Python code, always run `ruff check --fix` at the end and fix the issues that come up.
Always run `ruff format` at the end before returning to the user.

## Python

Use relative imports for the same module or below ie with a single '.'. Never use '..' : Always use the absolute import then.
Do not use dataclasses. Always use attrs and @define.