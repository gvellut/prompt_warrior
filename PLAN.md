# Prompt Warrior CLI v1 Implementation Plan

## Summary

This plan implements a full task-management CLI in `src/prompt_warrior/__main__.py`, updates `README.md` with command docs and the requested 30-second workflow, and keeps assumptions explicit.

Primary goals:
1. Parse and update user-editable `work.md` while preserving formatting where possible.
2. Keep command behavior deterministic and explicit.
3. Provide explicit `PWAR_` env vars for all options.
4. Keep system-specific clipboard behavior macOS-only behind an abstraction.

## Scope implemented

### CLI and architecture

- Click root command with:
  - `-d/--debug` (`PWAR_DEBUG`)
  - `--prompts-dir` (`PWAR_PROMPTS_DIR`)
- Subcommands:
  - `init`
  - `add`
  - `done`
  - `next`
  - `delete`
- Custom `click.Command` subclass for all commands (not group): catches errors, prints message in red, prints traceback in debug mode.
- Rich console with themed styles:
  - `success`, `warning`, `error`, `highlight`, `important`

### Data model

Implemented with `attrs @define`:
- `AppContext`
- `TaskLine`
- `WorkDocument`
- `InvariantWarning`
- `TaskReferenceResolution`
- `TaskSignature`

Enums (`auto()`, uppercase names):
- `BulletType`
- `ReferenceKind`
- `AddMode`

### Parsing and validation

- `work.md` read with `splitlines(keepends=True)`.
- Task lines parsed using strict `BULLET [](path) label` regex.
- Non-task lines are preserved untouched.
- Tree built from indentation depth (`expandtabs(4)`) for structure.
- Fatal validation:
  - direct children under one parent must share one indentation depth.
- Warning validation:
  - multiple `*` in one sibling group,
  - active tasks not in one ancestor-descendant chain.

### Command behavior

#### `init`
- Fails if prompts dir already exists.
- Creates prompts dir + `work.md`.
- Default creates first task line and markdown file.
- `--no-init` leaves `work.md` empty.

#### `add LABEL_WORDS...`
- Positional label is required.
- Positional label is always the display label in `work.md`.
- `--label/--raw-label` only change filename seed.
- Supports:
  - top-level insertion,
  - `--top`,
  - `--sub TASK_REF`,
  - `--corr`,
  - `--agent`.
- Filename generation includes:
  - safe ASCII transformation helper,
  - ordered prefixes (`A..Z`, then `Aa..Za`, `Ab..Zb`, ..., then numbered variants),
  - subtask prefixing with `ParentPrefix.<local>`.

#### `done`
- Closes deepest active task.
- Marks `!`.
- Moves closed task block to end of sibling list.
- `--recursive` bubbles upward when siblings are all done (ignoring `~`).

#### `next`
- Chooses scope from deepest active:
  - if active has children, use its children,
  - else top-level,
  - if no active, top-level.
- Fails if scope already has `*`.
- Activates first `-` or `?`.
- Copies task file content to clipboard.

#### `delete TASK_REF`
- Reference resolution order:
  1. full stem,
  2. prefix,
  3. planned-task index.
- Confirmation when task is active or has children.
- Default delete removes subtree from `work.md` and deletes all linked files in subtree.
- `--keep-children` removes parent only, promotes direct children to parent level, keeps child files.

### Autocompletion

- Click shell completion enabled.
- Task-reference completion for:
  - `add --sub`
  - `delete TASK_REF`
- Completion inserts full task stem without `.md`.

### README updates

- Command-by-command short explanations.
- Explicit env var mapping table.
- Bash and zsh completion setup instructions.
- Added requested “30-second workflow”.

## Explicit assumptions and guesses

These were inferred where the written spec was ambiguous:

1. `status` refers to bullet state in `work.md`, not a separate file.
2. Link paths written by commands are local filenames in prompts directory.
3. If active invariants are broken and multiple deepest active tasks exist, first by file order is used, with warning.
4. For `delete --keep-children`, only direct children are promoted; their subtrees remain under them.
5. For promoted children, only direct child task-line indentation is adjusted to parent level.

Resolved with explicit user confirmation during planning:
- `add` display label comes from positional text.
- `add` errors when positional text is missing.

## Execution checklist by file

### `src/prompt_warrior/__main__.py`
- [x] Replace placeholder with complete CLI.
- [x] Add constants, enums, attrs models.
- [x] Add parser, validation, and mutation logic.
- [x] Add command implementations with explicit env vars.
- [x] Add macOS clipboard abstraction and use in `next`.
- [x] Add task reference completion.

### `README.md`
- [x] Add command docs.
- [x] Add env var mapping.
- [x] Add 30-second workflow.
- [x] Add autocomplete setup for bash and zsh.

### `PLAN.md`
- [x] Document plan, assumptions, and checklist.
