# prompt_warrior

`prompt-warrior` is a CLI for managing prompt task files and a hierarchical task table-of-contents with Markdown.

Currently, the only supported system is macos (for copying to the clipboard using `pbcopy`).

## Code layout

- `src/prompt_warrior/__main__.py`: thin entrypoint
- `src/prompt_warrior/cli.py`: root Click group + app context setup
- `src/prompt_warrior/commands/*.py`: one file per command
- `src/prompt_warrior/core.py`: shared document/task operations
- `src/prompt_warrior/models.py`: shared models/enums
- `src/prompt_warrior/constants.py`: defaults, env vars, and parse constants

## Commands

### `prompt-warrior init`
Initialize a prompts workspace.

- Creates the prompts directory (default: `.prompts`)
- Creates `.prompts/__battle.md`
- By default creates one initial task and markdown file
- Fails if the prompts directory already exists
- In an IDE like VSCode, the link to the task Markdown file can be clicked on to see the content

Options:
- `--no-init-task`: create directory + `__battle.md` only
- `--init-task-label TEXT`: label and filename seed for the initial task

### `prompt-warrior add LABEL_WORDS...`
Create a task markdown file and add its line to `__battle.md`.

- Positional `LABEL_WORDS...` is required
- Positional text is always the display label in `__battle.md`
- `--filename` only change the filename stem
- New task lines are written as `BULLET [label](file.md)`

Options:
- `-l, --filename TEXT`: safe-ASCII filename stem override
- `-t, --top`: add at top of top-level list
- `-s, --sub TASK_REF`: add as planned child (`-`) under parent task
  - Parent must be non-inert: `-`, `*`, or `?` (`!` and `~` are rejected)
- `-c, --corr`: add as correction child (`?`) under deepest active task
- `-a, --agent`: add as agent child (`~`) under deepest active task

### `prompt-warrior next`
Activate the next actionable task and copy its markdown content to the clipboard.

Selection rules:
- If deepest active task has children: activate first `-` or `?` child
- Otherwise: activate first top-level `-` or `?`
- If no active task exists: activate first top-level `-` or `?`

Notes:
- Errors if current scope already has an active `*`
- Clipboard integration is implemented for macOS (`pbcopy`)

### `prompt-warrior read`
Copy the deepest active task content to the clipboard without changing task status.

Rules:
- Only the currently deepest active (`*`) task is considered
- Errors if no active task exists
- Clipboard integration is implemented for macOS (`pbcopy`)

### `prompt-warrior commit`
Copy a shell command for the deepest active task label to the clipboard.

Defaults:
- Copies `gaa && gcam '<active label>'`
- Also marks that deepest active task as done (`!`) and moves it to the end of its sibling list

Options:
- `-c, --commit-command TEXT`: commit command prefix (default: `gcam`)
- `-a, --add-all-command TEXT`: add-all command prefix (default: `gaa`)
- `-n, --no-done`: do not mark task done (keeps previous behavior)
- `-r, --recursive`: if all siblings are done (ignoring `~`), also close parent, and continue upward

Rules:
- If one command is empty, only the other command is copied (no `&&`)
- If both are empty, the command errors
- The copied command string is also printed to output
- When done-closing is enabled and `--recursive` is not used, output indicates whether all siblings are also done (ignoring `~`)

### `prompt-warrior done`
Close the deepest active task.

- Marks it done (`!`)
- Moves that task block to the bottom of its sibling list

Options:
- `-r, --recursive`: if all siblings are done (ignoring `~`), also close parent, and continue upward
- Without `--recursive`, output also indicates whether all siblings are done (ignoring `~`)

### `prompt-warrior delete TASK_REF`
Delete a task by reference.

Default behavior:
- Removes the task line and full subtree from `__battle.md`
- Deletes markdown files for task + descendants

Options:
- `--keep-children`: remove only the target task; promote direct children to target level; keep child files

Safety:
- Asks for confirmation if task is active or has children

## Task References

A task reference can be:
1. Full markdown stem without `.md` (exact match)
2. Prefix before `_` (exact match)
3. 0-based index in planned (`-`) tasks only

Resolution order is exactly: stem, then prefix, then planned index.

## Root Options

- `-d, --debug`: enable debug logs and stack traces on command errors
- `--prompts-dir PATH`: prompts workspace directory (default `.prompts`)

## Environment Variables (`PWAR_`)

All options can be set from env vars:

| Option | Env var |
|---|---|
| `--debug` | `PWAR_DEBUG` |
| `--prompts-dir` | `PWAR_PROMPTS_DIR` |
| `init --no-init-task` | `PWAR_NO_INIT_TASK` |
| `init --init-task-label` | `PWAR_INIT_TASK_LABEL` |
| `add --filename` | `PWAR_FILENAME` |
| `add --top` | `PWAR_TOP` |
| `add --sub` | `PWAR_SUB` |
| `add --corr` | `PWAR_CORR` |
| `add --agent` | `PWAR_AGENT` |
| `done --recursive` | `PWAR_RECURSIVE` |
| `commit --commit-command` | `PWAR_COMMIT_COMMAND` |
| `commit --add-all-command` | `PWAR_ADD_ALL_COMMAND` |
| `commit --no-done` | `PWAR_NO_DONE` |
| `delete --keep-children` | `PWAR_KEEP_CHILDREN` |

## 30-second workflow

Typical session order:

1. `prompt-warrior init --init-task-label "Initialization"`
2. `prompt-warrior next`
3. Work with the copied prompt in your LLM.
4. `prompt-warrior add Follow-up task`
5. `prompt-warrior add --sub A Subtask detail` (or use completion)
6. `prompt-warrior done`
7. `prompt-warrior next`
8. Repeat steps 3 to 7 until parent is complete.

## Autocompletion

Task-reference completion is enabled for:
- `add --sub TASK_REF`
- `delete TASK_REF`

Completion values are task stems (without `.md`).

### Bash

```bash
eval "$(_PROMPT_WARRIOR_COMPLETE=bash_source prompt-warrior)"
```

Persist in `~/.bashrc`.

### Zsh

```zsh
eval "$(_PROMPT_WARRIOR_COMPLETE=zsh_source prompt-warrior)"
```

Persist in `~/.zshrc`.

#### uv project

Set it up as follows to get auto-completion without installing `prompt-warrior`. Change the actual path to the cloned directory. 

Here the command is renamed `pwr`.

```sh
pwr() {
  uv run --project /Users/guilhem/Documents/projects/github/prompt_warrior prompt-warrior "$@"
}
eval "$(_PROMPT_WARRIOR_COMPLETE=zsh_source pwr)"
compdef pwr=prompt-warrior
```

## Battle file behavior and validation

- Non-task lines are preserved as-is
- Task lines support:
  - `BULLET [label](path)` (preferred)
  - `BULLET [](path) label` (legacy)
- Label resolution rule:
  - if link text (`[ ... ]`) is non-empty, use it
  - otherwise use trailing text after `](path)`
- Tabs/spaces are tolerated
- Fatal parse error only when direct children of the same parent use inconsistent indentation depths
- Warning is emitted if active (`*`) invariants are broken
