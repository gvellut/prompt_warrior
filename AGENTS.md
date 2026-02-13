This repository is a Python CLI program that manages prompts for tasks for a LLM. 

The prompts are stored as Markdown (but the format is irrelevant because it is not read by the tool) except as an opaque text.

The prompts are manually managed and passed to the LLM explicitly by the user (it is not a task management tool for autonomous development by the LLM).

There is a table of content of tasks : this links to prompts in Markdown format and has memory of what is being worked on and the order. The tasks can be ordered in a hierarchy.

The code is organized as:
- `src/prompt_warrior/__main__.py` for the entrypoint.
- `src/prompt_warrior/cli.py` for root CLI wiring.
- `src/prompt_warrior/commands/*.py` for one file per command.
- `src/prompt_warrior/core.py`, `src/prompt_warrior/models.py`, and `src/prompt_warrior/constants.py` for shared logic/models/config.

After making edits to the Python code, run `ruff check --fix` and fix the issues that come up.

Run `ruff format` at the end.
