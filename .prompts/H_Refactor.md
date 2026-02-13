- Refactor: Split the commands in each file. If used multiple places, either create a separate module or keep to main place (as long as no circular imports) eg print_close_result and close_deepest_active_task in done.py (even though used by commit too). You can also create a model.py for common models. Defaults + env var can be put in a specific file

- Update the README.md + AGENTS.md when relevant.
