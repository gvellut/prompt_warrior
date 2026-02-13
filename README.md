# prompt_warrior

`pwr` is a CLI for managing prompt task files and a hierarchical task table-of-contents in Markdown.

Clipboard copy is supported on:
- macOS (`pbcopy`)
- Linux (`wl-copy`, `xclip`, or `xsel`)
- Windows (`clip`)

## Code layout

- `src/prompt_warrior/__main__.py`: root Click group + app context setup
- `src/prompt_warrior/commands/*.py`: one file per command
- `src/prompt_warrior/core.py`: shared document/task operations
- `src/prompt_warrior/models.py`: shared models/enums
- `src/prompt_warrior/constants.py`: defaults, env vars, parse constants

## Task file

The table-of-contents file is `__plan.md` inside the prompts directory (default: `.prompts`).

Supported task bullets:
- `-`: planned
- `*`: active
- `?`: correction (planned)
- `*?`: correction (active)
- `!`: done
- `!?`: correction (done)
- `~`: agent/inert

## Commands

### `pwr init`
Initialize a prompts workspace.

- Creates the prompts directory (default: `.prompts`)
- Creates `.prompts/__plan.md`
- By default creates one initial task and markdown file
- Fails if the prompts directory already exists

Options:
- `--no-init-task`: create directory + `__plan.md` only
- `--init-task-label TEXT`: label and filename seed for the initial task

### `pwr add LABEL_WORDS...`
Create a task markdown file and add its line to `__plan.md`.

Options:
- `-l, --filename TEXT`: safe-ASCII filename stem override
- `-t, --top`: add at top of top-level list
- `-s, --sub TASK_REF`: add as planned child (`-`) under parent task
- `-c, --corr`: add as correction child (`?`) under deepest active task
- `-a, --agent`: add as agent child (`~`) under deepest active task

### `pwr next`
Activate the next actionable task and copy its markdown content to the clipboard.

Selection rules:
- If deepest active task has children: activate first `-` or `?` child
- Otherwise: activate first top-level `-` or `?`
- If no active task exists: activate first top-level `-` or `?`

### `pwr read`
Copy the deepest active task content to the clipboard without changing task status.

### `pwr done`
Close the deepest active task.

- Marks it done (`!` or `!?`)
- Moves the task block to the end of its sibling list
- By default closes recursively upward when all relevant siblings are done (ignores `~`)

Options:
- `--no-recursive`: close only the deepest active task

Output:
- Always prints number of closed tasks
- Prints remaining relevant tasks at a level with labels:
  - `Top level` (depth `0`)
  - `Sublevel N` (depth `N`)
- Non-recursive: level of the closed task
- Recursive: level of the shallowest task that was closed

### `pwr commit`
Copy a shell command for the deepest active task label to the clipboard.

Defaults:
- Copies `gaa && gcam '<active label>'`
- Also closes task(s) using the same close behavior as `pwr done`

Options:
- `-c, --commit-command TEXT`: commit command prefix (default: `gcam`)
- `-a, --add-all-command TEXT`: add-all command prefix (default: `gaa`)
- `-n, --no-done`: do not close task(s)
- `--no-recursive`: when closing is enabled, close only deepest active task

### `pwr delete TASK_REF`
Delete a task by reference.

Default behavior:
- Removes the task line and full subtree from `__plan.md`
- Deletes markdown files for task + descendants

Options:
- `--keep-children`: remove only target task; promote direct children to target level; keep child files

## Task references

A task reference can be:
1. Full markdown stem without `.md` (exact match)
2. Prefix before `_` (exact match)
3. 0-based index in planned (`-`) tasks only

Resolution order: stem, then prefix, then planned index.

## Root options

- `-d, --debug`: enable debug logs and stack traces on command errors
- `--prompts-dir PATH`: prompts workspace directory (default `.prompts`)

## Environment variables (`PWAR_`)

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
| `done --no-recursive` | `PWAR_NO_RECURSIVE` |
| `commit --commit-command` | `PWAR_COMMIT_COMMAND` |
| `commit --add-all-command` | `PWAR_ADD_ALL_COMMAND` |
| `commit --no-done` | `PWAR_NO_DONE` |
| `commit --no-recursive` | `PWAR_NO_RECURSIVE` |
| `delete --keep-children` | `PWAR_KEEP_CHILDREN` |

## Quick workflow

1. `pwr init --init-task-label "Initialization"`
2. `pwr next`
3. Work with the copied prompt in your LLM.
4. `pwr add Follow-up task`
5. `pwr add --sub A subtask detail`
6. `pwr done`
7. `pwr next`

## Autocompletion

Task-reference completion is enabled for:
- `add --sub TASK_REF`
- `delete TASK_REF`

### Bash

```bash
eval "$(_PWR_COMPLETE=bash_source pwr)"
```

Persist in `~/.bashrc`.

### Zsh

```zsh
eval "$(_PWR_COMPLETE=zsh_source pwr)"
```

Persist in `~/.zshrc`.

#### uv project

Set it up as follows to get auto-completion without installing `pwr`. Change the actual path to the cloned directory. 

The command is still named `pwr` but wraps `uv run`.

```sh
pwr() {
  uv run --project /Users/guilhem/Documents/projects/github/prompt_warrior pwr "$@"
}
eval "$(_PWR_COMPLETE=zsh_source pwr)"
```
