# prompt_warrior

`prompt-warrior` is a Click-based CLI for managing prompt task files and a hierarchical task table-of-contents in `.prompts/work.md`.

## Commands

### `prompt-warrior init`
Initialize a prompts workspace.

- Creates the prompts directory (default: `.prompts`)
- Creates `.prompts/work.md`
- By default creates one initial task and markdown file
- Fails if the prompts directory already exists

Options:
- `--no-init-task`: create directory + `work.md` only
- `--init-task-label TEXT`: label and filename seed for the initial task

### `prompt-warrior add LABEL_WORDS...`
Create a task markdown file and add its line to `work.md`.

- Positional `LABEL_WORDS...` is required
- Positional text is always the display label in `work.md`
- `--label/--raw-label` only change the filename stem

Options:
- `-l, --label TEXT`: safe-ASCII filename stem override
- `-r, --raw-label TEXT`: raw filename stem override
- `-t, --top`: add at top of top-level list
- `-s, --sub TASK_REF`: add as planned child (`-`) under parent task
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

### `prompt-warrior done`
Close the deepest active task.

- Marks it done (`!`)
- Moves that task block to the bottom of its sibling list

Options:
- `-r, --recursive`: if all siblings are done (ignoring `~`), also close parent, and continue upward

### `prompt-warrior delete TASK_REF`
Delete a task by reference.

Default behavior:
- Removes the task line and full subtree from `work.md`
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
| `add --label` | `PWAR_LABEL` |
| `add --raw-label` | `PWAR_RAW_LABEL` |
| `add --top` | `PWAR_TOP` |
| `add --sub` | `PWAR_SUB` |
| `add --corr` | `PWAR_CORR` |
| `add --agent` | `PWAR_AGENT` |
| `done --recursive` | `PWAR_RECURSIVE` |
| `delete --keep-children` | `PWAR_KEEP_CHILDREN` |

## 30-second workflow

Typical session order:

1. `prompt-warrior init --init-task-label "Initialization"`
2. `prompt-warrior next`
3. Work with the copied prompt in your LLM.
4. `prompt-warrior add "Follow-up task"`
5. `prompt-warrior add --sub A "Subtask detail"` (or use completion)
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

## Work file behavior and validation

- Non-task lines are preserved as-is
- Task lines are parsed only in `BULLET [](path) label` format
- Tabs/spaces are tolerated
- Fatal parse error only when direct children of the same parent use inconsistent indentation depths
- Warning is emitted if active (`*`) invariants are broken
