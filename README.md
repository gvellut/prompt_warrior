# Prompt Warrior (pwr)

`prompt-warrior` is a CLI for managing prompt task files and a hierarchical task table-of-contents in Markdown.

> The greatness of humans lies not in their existence, but in their command. Where there is an agent, there is a drive to overcome, but a drive without direction is chaos. The task is to harness that will to power and bend it toward a singular purpose. True mastery is found not in the machine, but in the PWR that directs its soul.
> - The Over-Coder

## Task file

The table-of-contents file is `__plan.md` inside the prompts directory (default: `.prompts`).

Possible task bullets:
- `-`: planned
- `*`: active
- `?`: correction (planned)
- `*?`: correction (active)
- `!`: done
- `!?`: correction (done)
- `~`: agent/inert

## Commands

Run with `prompt-warrior ...`.

### `init`
Initialize a prompts workspace.

- Creates the prompts directory (default: `.prompts`)
- Creates `.prompts/__plan.md`
- By default creates one initial task and markdown file
- Fails if the prompts directory already exists

Options:
- `--no-init-task`: create directory + `__plan.md` only
- `--init-task-label TEXT`: label and filename seed for the initial task

### `add LABEL_WORDS...`
Create a task markdown file and add its line to `__plan.md`.

Options:
- `-l, --filename TEXT`: safe-ASCII filename stem override
- `-t, --top`: add at top of top-level list
- `-s, --sub TASK_REF`: add as planned child (`-`) under parent task
- `--max-folder-tasks INTEGER`: max files per auto-generated folder (default `12`), `0` disables folders
- `--folder-name PATH`: place a new top-level task file in a specific relative folder
- `-c, --corr`: add as correction child (`?`) under deepest active task
- `-a, --agent`: add as agent child (`~`) under deepest active task

### `next`
Activate the next actionable task and copy its markdown content to the clipboard.

Selection rules:
- If deepest active task has children: activate first `-` or `?` child
- Otherwise: activate first top-level `-` or `?`
- If no active task exists: activate first top-level `-` or `?`

Options:
- `--branch`: also copy and print a branch command for the activated task
- `--branch-command TEXT`: command prefix for the branch command (default `gsw -c`)
- `--branch-copy-interval INTEGER`: delay before branch-command clipboard copy in 100ms units (default `6`)

### `read`
Copy the deepest active task content to the clipboard without changing task status.

### `done`
Close the deepest active task.

- Marks it done (`!` or `!?`)
- Moves the task block to the end of its sibling list
- By default closes only the deepest active task (non-recursive)

Options:
- `-r, --recursive`: also close parent tasks upward when all relevant siblings are done (ignores `~`)

Output:
- Always prints number of closed tasks
- Prints remaining relevant tasks at a level with labels:
  - `Top level` (depth `0`)
  - `Sublevel N` (depth `N`)
- Non-recursive: level of the closed task
- Recursive: level of the shallowest task that was closed

### `commit`
Copy a shell command for the deepest active task label to the clipboard.

Defaults:
- Copies `gaa && gcam '<active label>'`
- Also closes task(s) using the same close behavior as `done`

Options:
- `-c, --commit-command TEXT`: commit command prefix (default: `gcam`)
- `-a, --add-all-command TEXT`: add-all command prefix (default: `gaa`)
- `-n, --no-done`: do not close task(s)
- `-r, --recursive`: when closing is enabled, also close parent tasks upward when all relevant siblings are done

### `delete TASK_REF`
Delete a task by reference.

Default behavior:
- Removes the task line and full subtree from `__plan.md`
- Deletes markdown files for task + descendants

Options:
- `--keep-children`: remove only target task; promote direct children to target level; keep child files

### `clean-to-folders`
Move current root-level task files into generated folders and rewrite links in `__plan.md`.

Rules:
- Groups by top-level task subtree (top-level task + descendants stay together)
- Packs folders in alphabetical order of top-level task link path
- Uses generated folder names like `<prefix>_tasks`

Options:
- `--max-folder-tasks INTEGER`: max files per generated folder (default `12`), `0` makes it a no-op
- `--dry-run`: print the projected task-file tree and summary without changing files

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
| `add --max-folder-tasks` | `PWAR_MAX_FOLDER_TASKS` |
| `add --folder-name` | `PWAR_FOLDER_NAME` |
| `add --corr` | `PWAR_CORR` |
| `add --agent` | `PWAR_AGENT` |
| `clean-to-folders --max-folder-tasks` | `PWAR_MAX_FOLDER_TASKS` |
| `clean-to-folders --dry-run` | `PWAR_CLEAN_TO_FOLDERS_DRY_RUN` |
| `done --recursive` | `PWAR_RECURSIVE` |
| `next --branch` | `PWAR_BRANCH` |
| `next --branch-command` | `PWAR_BRANCH_COMMAND` |
| `next --branch-copy-interval` | `PWAR_BRANCH_COPY_INTERVAL` |
| `commit --commit-command` | `PWAR_COMMIT_COMMAND` |
| `commit --add-all-command` | `PWAR_ADD_ALL_COMMAND` |
| `commit --no-done` | `PWAR_NO_DONE` |
| `commit --recursive` | `PWAR_RECURSIVE` |
| `delete --keep-children` | `PWAR_KEEP_CHILDREN` |

## Quick workflow

1. `init --init-task-label "Initialization"`
2. `next`
3. Work with the copied prompt in your LLM.
4. `add Follow-up task`
5. `add --sub A subtask detail`
6. `done`
7. `next`

## Autocompletion

Task-reference completion is enabled for:
- `add --sub TASK_REF`
- `delete TASK_REF`

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

#### uv project (development mode)

Set it up as follows to get auto-completion without installing `prompt-warrior`. Change the actual path to the cloned directory. 

The command is a function named `pwr` and wraps `uv run`.

```sh
pwr() {
  VIRTUAL_ENV= uv run --project /Users/guilhem/Documents/projects/github/prompt_warrior prompt-warrior "$@"
}
eval "$(
_PROMPT_WARRIOR_COMPLETE=zsh_source pwr |\
sed \
 -e "s/(( ! \$+commands\[prompt-warrior\] )) && return 1//g" \
 -e "s| prompt-warrior)| pwr)|g" \
 -e "s/env COMP_WORDS=/COMP_WORDS=/g"	
)"
compdef pwr=prompt-warrior
```
