from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
import re
import string
import unicodedata

import click

from .constants import (
    DEFAULT_MAX_FOLDER_TASKS,
    DEFAULT_PROMPTS_DIR,
    FALLBACK_NEWLINE,
    INDENT_UNIT,
    INDENT_WIDTH,
    MARKDOWN_EXTENSION,
    MAX_SAFE_LABEL_LENGTH,
    TASK_LINE_RE,
    WORK_FILENAME,
)
from .errors import ParseIssue, PromptWarriorError
from .models import (
    BULLET_TO_CHAR,
    CHAR_TO_BULLET,
    AddMode,
    AppContext,
    BulletType,
    CleanToFoldersBucket,
    CleanToFoldersMove,
    CleanToFoldersPlan,
    CleanToFoldersRewrite,
    InvariantWarning,
    ReferenceKind,
    TaskLine,
    TaskReferenceResolution,
    TaskSignature,
    WorkDocument,
)


def has_newline(value: str) -> bool:
    return value.endswith("\n") or value.endswith("\r")


def detect_newline(lines: list[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return FALLBACK_NEWLINE


def indent_width(indent_raw: str) -> int:
    return len(indent_raw.expandtabs(INDENT_WIDTH))


def resolve_task_label(link_text: str, trailing_label: str) -> str:
    normalized_link_text = link_text.strip()
    if normalized_link_text:
        return normalized_link_text
    return trailing_label.strip()


def parse_bullet_token(token: str) -> tuple[BulletType, bool]:
    if token == "*?":
        return BulletType.ACTIVE, True
    if token == "!?":
        return BulletType.DONE, True
    if token == "?":
        return BulletType.CORRECTION, True
    return CHAR_TO_BULLET[token], False


def parse_work_lines(path: Path, lines: list[str]) -> WorkDocument:
    document = WorkDocument(
        path=path,
        lines=list(lines),
        tasks=[],
        newline=detect_newline(lines),
    )

    for index, line in enumerate(document.lines):
        match = TASK_LINE_RE.match(line)
        if not match:
            continue

        bullet_token = match.group("bullet")
        bullet, is_correction = parse_bullet_token(bullet_token)
        indent_raw = match.group("indent")
        label = resolve_task_label(
            link_text=match.group("link_text"),
            trailing_label=match.group("trailing_label"),
        )
        task = TaskLine(
            line_index=index,
            indent_raw=indent_raw,
            indent_expanded=indent_width(indent_raw),
            bullet=bullet,
            is_correction=is_correction,
            ws_after_bullet=match.group("ws1"),
            link_path=match.group("link"),
            label=label,
            newline=match.group("newline"),
            raw_line=line,
        )
        document.line_to_task_index[index] = len(document.tasks)
        document.tasks.append(task)

    build_tree(document)
    validate_child_indentation(document)
    document.warnings.extend(validate_active_invariants(document))
    return document


def parse_work_document(path: Path) -> WorkDocument:
    if not path.exists():
        raise PromptWarriorError(f"Missing plan file: {path}")

    content = path.read_text(encoding="utf-8")
    return parse_work_lines(path=path, lines=content.splitlines(keepends=True))


def build_tree(document: WorkDocument) -> None:
    stack: list[int] = []
    for task_index, task in enumerate(document.tasks):
        while (
            stack and task.indent_expanded <= document.tasks[stack[-1]].indent_expanded
        ):
            stack.pop()

        if stack:
            parent_index = stack[-1]
            task.parent_task_index = parent_index
            task.depth = document.tasks[parent_index].depth + 1
            document.tasks[parent_index].child_task_indices.append(task_index)
        else:
            task.parent_task_index = None
            task.depth = 0

        stack.append(task_index)


def validate_child_indentation(document: WorkDocument) -> None:
    for parent in document.tasks:
        children = parent.child_task_indices
        if len(children) < 2:
            continue

        first_child = document.tasks[children[0]]
        expected_depth = first_child.indent_expanded
        for child_index in children[1:]:
            child = document.tasks[child_index]
            if child.indent_expanded != expected_depth:
                raise ParseIssue(
                    "Inconsistent indentation below a single task: "
                    f"parent line {parent.line_number}, "
                    f"first child line {first_child.line_number} "
                    f"uses depth {expected_depth}, "
                    f"but line {child.line_number} "
                    f"uses depth {child.indent_expanded}. "
                    "All direct children of the same parent "
                    "must share one indentation depth."
                )


def validate_active_invariants(document: WorkDocument) -> list[InvariantWarning]:
    warnings: list[InvariantWarning] = []

    for parent_index, siblings in iter_sibling_groups(document):
        active_lines = [
            document.tasks[index].line_number
            for index in siblings
            if document.tasks[index].bullet == BulletType.ACTIVE
        ]
        if len(active_lines) > 1:
            if parent_index is None:
                scope = "top level"
            else:
                scope = f"children of line {document.tasks[parent_index].line_number}"
            active_line_list = ", ".join(map(str, active_lines))
            warnings.append(
                InvariantWarning(
                    f"Active-task invariant broken for {scope}: "
                    f"multiple '*' tasks found on lines {active_line_list}."
                )
            )

    active_indices = [
        index
        for index, task in enumerate(document.tasks)
        if task.bullet == BulletType.ACTIVE
    ]
    for left_idx, left in enumerate(active_indices):
        for right in active_indices[left_idx + 1 :]:
            if not (
                is_ancestor(document, left, right) or is_ancestor(document, right, left)
            ):
                warnings.append(
                    InvariantWarning(
                        "Active-task invariant broken: "
                        "active tasks are not in a single parent-descendant chain."
                    )
                )
                return warnings

    return warnings


def iter_sibling_groups(
    document: WorkDocument,
) -> Iterator[tuple[int | None, list[int]]]:
    yield None, top_level_task_indices(document)
    for parent_index, parent in enumerate(document.tasks):
        if parent.child_task_indices:
            yield parent_index, list(parent.child_task_indices)


def is_ancestor(
    document: WorkDocument, ancestor_index: int, descendant_index: int
) -> bool:
    current = document.tasks[descendant_index].parent_task_index
    while current is not None:
        if current == ancestor_index:
            return True
        current = document.tasks[current].parent_task_index
    return False


def top_level_task_indices(document: WorkDocument) -> list[int]:
    return [
        index
        for index, task in enumerate(document.tasks)
        if task.parent_task_index is None
    ]


def child_task_indices(document: WorkDocument, parent_index: int | None) -> list[int]:
    if parent_index is None:
        return top_level_task_indices(document)
    return list(document.tasks[parent_index].child_task_indices)


def block_end_line_index(document: WorkDocument, task_index: int) -> int:
    task = document.tasks[task_index]
    for candidate in document.tasks:
        if candidate.line_index <= task.line_index:
            continue
        if candidate.indent_expanded <= task.indent_expanded:
            return candidate.line_index
    return len(document.lines)


def task_signature(task: TaskLine) -> TaskSignature:
    return TaskSignature(
        link_path=task.link_path,
        label=task.label,
        indent_expanded=task.indent_expanded,
    )


def find_task_by_signature(
    document: WorkDocument, signature: TaskSignature
) -> int | None:
    for index, task in enumerate(document.tasks):
        if (
            task.link_path == signature.link_path
            and task.label == signature.label
            and task.indent_expanded == signature.indent_expanded
        ):
            return index
    return None


def render_task_line(
    task: TaskLine,
    *,
    bullet: BulletType | None = None,
    indent_raw: str | None = None,
    link_path: str | None = None,
) -> str:
    rendered_bullet = BULLET_TO_CHAR[bullet or task.bullet]
    if task.is_correction and (bullet or task.bullet) in {
        BulletType.ACTIVE,
        BulletType.DONE,
    }:
        rendered_bullet = f"{rendered_bullet}?"
    rendered_indent = task.indent_raw if indent_raw is None else indent_raw
    rendered_link_path = task.link_path if link_path is None else link_path
    return (
        f"{rendered_indent}{rendered_bullet}{task.ws_after_bullet}"
        f"[{task.label}]({rendered_link_path}){task.newline}"
    )


def ensure_insert_separation(lines: list[str], insert_at: int, newline: str) -> None:
    if insert_at > 0 and not has_newline(lines[insert_at - 1]):
        lines[insert_at - 1] = lines[insert_at - 1] + newline


def cleanup_delete_separation(
    lines: list[str], delete_start: int, newline: str
) -> None:
    if 0 < delete_start < len(lines) and not has_newline(lines[delete_start - 1]):
        lines[delete_start - 1] = lines[delete_start - 1] + newline


def write_work_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def emit_warnings(app_ctx: AppContext, document: WorkDocument) -> None:
    for warning in document.warnings:
        app_ctx.console.print(f"Warning: {warning.message}", style="warning")


def resolve_prompts_dir_from_ctx(ctx: click.Context | None) -> Path:
    current = ctx
    while current is not None:
        if (
            "prompts_dir" in current.params
            and current.params["prompts_dir"] is not None
        ):
            return Path(current.params["prompts_dir"])
        current = current.parent
    return Path(DEFAULT_PROMPTS_DIR)


def extract_prefix_from_stem(stem: str) -> str | None:
    if "_" not in stem:
        return None
    prefix, _ = stem.split("_", 1)
    return prefix or None


def is_standard_task_prefix(prefix: str | None) -> bool:
    if prefix is None:
        return False
    return re.fullmatch(r"(?:[A-Z]|[A-Z][a-z]|[A-Z][a-z][1-9])", prefix) is not None


def generated_task_folder_name(prefix: str) -> str:
    return f"{prefix}_tasks"


def normalize_task_folder(folder: Path) -> Path:
    return Path(".") if str(folder) in {"", "."} else folder


def task_folder_for_link_path(link_path: str) -> Path:
    return normalize_task_folder(Path(link_path).parent)


def task_folder_for_line(task: TaskLine) -> Path:
    return task_folder_for_link_path(task.link_path)


def folder_rel_path_to_link(folder: Path) -> str:
    normalized = normalize_task_folder(folder)
    if normalized == Path("."):
        return ""
    return normalized.as_posix()


def validate_folder_name_option(folder_name: str) -> Path:
    raw = folder_name.strip()
    if not raw:
        raise PromptWarriorError("--folder-name cannot be empty.")

    folder = Path(raw)
    if folder.is_absolute():
        raise PromptWarriorError("--folder-name must be a relative path.")

    parts = folder.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise PromptWarriorError(
            "--folder-name must be a normalized relative path without '.' or '..'."
        )

    return normalize_task_folder(folder)


def validate_max_folder_tasks(value: int) -> int:
    if value < 0:
        raise PromptWarriorError("--max-folder-tasks must be >= 0.")
    return value


def count_tasks_by_folder(document: WorkDocument) -> dict[Path, int]:
    counts: dict[Path, int] = {}
    for task in document.tasks:
        folder = task_folder_for_line(task)
        counts[folder] = counts.get(folder, 0) + 1
    return counts


def is_generated_task_folder(folder: Path) -> bool:
    normalized = normalize_task_folder(folder)
    if normalized == Path(".") or len(normalized.parts) != 1:
        return False
    name = normalized.name
    if not name.endswith("_tasks"):
        return False
    prefix = name[: -len("_tasks")]
    return is_standard_task_prefix(prefix)


def build_task_link_path(folder: Path, file_name: str) -> str:
    normalized = normalize_task_folder(folder)
    if normalized == Path("."):
        return file_name
    return (normalized / file_name).as_posix()


def make_safe_ascii_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.replace(" ", "_")
    ascii_value = re.sub(r"[^A-Za-z0-9_]+", "", ascii_value)
    ascii_value = re.sub(r"_+", "_", ascii_value).strip("_")
    return ascii_value[:MAX_SAFE_LABEL_LENGTH] or "task"


def iter_prefix_candidates() -> Iterator[str]:
    for upper in string.ascii_uppercase:
        yield upper

    for lower in string.ascii_lowercase:
        for upper in string.ascii_uppercase:
            yield f"{upper}{lower}"

    for number in "123456789":
        for lower in string.ascii_lowercase:
            for upper in string.ascii_uppercase:
                yield f"{upper}{lower}{number}"


@lru_cache(maxsize=1)
def _prefix_order_lookup() -> dict[str, int]:
    return {prefix: index for index, prefix in enumerate(iter_prefix_candidates())}


def standard_prefix_order(prefix: str | None) -> int | None:
    if not is_standard_task_prefix(prefix):
        return None
    return _prefix_order_lookup()[prefix]


def next_standard_prefix(prefix: str | None) -> str:
    if prefix is None:
        return next(iter_prefix_candidates())

    current_order = standard_prefix_order(prefix)
    if current_order is None:
        raise PromptWarriorError(f"Unsupported task prefix for increment: '{prefix}'.")

    for candidate in iter_prefix_candidates():
        candidate_order = standard_prefix_order(candidate)
        if candidate_order is not None and candidate_order > current_order:
            return candidate

    raise PromptWarriorError(
        "No available task prefix left in the configured sequence."
    )


def choose_unused_prefix(used_prefixes: set[str]) -> str:
    for candidate in iter_prefix_candidates():
        if candidate not in used_prefixes:
            return candidate
    raise PromptWarriorError(
        "No available task prefix left in the configured sequence."
    )


def choose_next_prefix_after_last(used_prefixes: set[str]) -> str:
    last_prefix: str | None = None
    last_order: int | None = None
    for prefix in used_prefixes:
        prefix_order = standard_prefix_order(prefix)
        if prefix_order is None:
            continue
        if last_order is None or prefix_order > last_order:
            last_prefix = prefix
            last_order = prefix_order

    return next_standard_prefix(last_prefix)


def compose_stem(prefix: str, label_component: str) -> str:
    return f"{prefix}_{label_component}" if label_component else prefix


def choose_task_stem(
    app_ctx: AppContext,
    document: WorkDocument,
    parent_task_index: int | None,
    label_component: str,
) -> str:
    if parent_task_index is None:
        used_prefixes = {
            prefix
            for task in document.tasks
            if (prefix := extract_prefix_from_stem(task.stem)) is not None
        }

        while True:
            prefix = choose_next_prefix_after_last(used_prefixes)
            stem = compose_stem(prefix, label_component)
            if not (app_ctx.prompts_dir / f"{stem}{MARKDOWN_EXTENSION}").exists():
                return stem
            used_prefixes.add(prefix)

    parent_task = document.tasks[parent_task_index]
    parent_prefix = extract_prefix_from_stem(parent_task.stem)
    if parent_prefix is None:
        parent_prefix = make_safe_ascii_component(parent_task.stem)

    used_child_locals: set[str] = set()
    for child_index in parent_task.child_task_indices:
        child_prefix = extract_prefix_from_stem(document.tasks[child_index].stem)
        if not child_prefix:
            continue
        expected_prefix = f"{parent_prefix}."
        if child_prefix.startswith(expected_prefix):
            used_child_locals.add(child_prefix[len(expected_prefix) :])

    while True:
        local_prefix = choose_next_prefix_after_last(used_child_locals)
        full_prefix = f"{parent_prefix}.{local_prefix}"
        stem = compose_stem(full_prefix, label_component)
        if not (app_ctx.prompts_dir / f"{stem}{MARKDOWN_EXTENSION}").exists():
            return stem
        used_child_locals.add(local_prefix)


def choose_top_level_add_folder(
    document: WorkDocument,
    *,
    new_task_stem: str,
    max_folder_tasks: int,
    folder_name_override: str | None,
) -> Path:
    validate_max_folder_tasks(max_folder_tasks)

    if folder_name_override is not None:
        return validate_folder_name_option(folder_name_override)

    if max_folder_tasks == 0:
        return Path(".")

    task_counts = count_tasks_by_folder(document)
    ordered_top_level = _sorted_top_level_task_indices_for_foldering(document)
    last_standard_index: int | None = None
    for task_index in reversed(ordered_top_level):
        prefix = extract_prefix_from_stem(document.tasks[task_index].stem)
        if standard_prefix_order(prefix) is not None:
            last_standard_index = task_index
            break

    if last_standard_index is not None:
        folder = task_folder_for_line(document.tasks[last_standard_index])
        if is_generated_task_folder(folder) and (
            task_counts.get(folder, 0) < max_folder_tasks
        ):
            return folder

    prefix = extract_prefix_from_stem(new_task_stem)
    if prefix is None:
        raise PromptWarriorError(
            "Internal error: could not derive task prefix for folder naming."
        )
    return Path(generated_task_folder_name(prefix))


def choose_add_task_folder(
    document: WorkDocument,
    *,
    parent_task_index: int | None,
    new_task_stem: str,
    max_folder_tasks: int = DEFAULT_MAX_FOLDER_TASKS,
    folder_name_override: str | None = None,
) -> Path:
    if parent_task_index is not None:
        return task_folder_for_line(document.tasks[parent_task_index])

    return choose_top_level_add_folder(
        document,
        new_task_stem=new_task_stem,
        max_folder_tasks=max_folder_tasks,
        folder_name_override=folder_name_override,
    )


def deepest_active_task_index(document: WorkDocument) -> int | None:
    active_indices = [
        index
        for index, task in enumerate(document.tasks)
        if task.bullet == BulletType.ACTIVE
    ]
    if not active_indices:
        return None

    max_depth = max(document.tasks[index].depth for index in active_indices)
    candidates = [
        index for index in active_indices if document.tasks[index].depth == max_depth
    ]
    candidates.sort(key=lambda index: document.tasks[index].line_index)
    return candidates[0]


def resolve_reference(
    document: WorkDocument, reference: str
) -> TaskReferenceResolution:
    stem_matches = [
        index for index, task in enumerate(document.tasks) if task.stem == reference
    ]
    if len(stem_matches) == 1:
        return TaskReferenceResolution(
            task_index=stem_matches[0], kind=ReferenceKind.STEM
        )
    if len(stem_matches) > 1:
        raise PromptWarriorError(
            f"Reference '{reference}' is ambiguous by stem. "
            f"Matches: {format_match_list(document, stem_matches)}"
        )

    prefix_matches = [
        index
        for index, task in enumerate(document.tasks)
        if (prefix := extract_prefix_from_stem(task.stem)) is not None
        and prefix == reference
    ]
    if len(prefix_matches) == 1:
        return TaskReferenceResolution(
            task_index=prefix_matches[0], kind=ReferenceKind.PREFIX
        )
    if len(prefix_matches) > 1:
        raise PromptWarriorError(
            f"Reference '{reference}' is ambiguous by prefix. "
            f"Matches: {format_match_list(document, prefix_matches)}"
        )

    if reference.isdigit():
        index_value = int(reference)
        planned_indices = [
            index
            for index, task in enumerate(document.tasks)
            if task.bullet == BulletType.PLANNED
        ]
        if 0 <= index_value < len(planned_indices):
            return TaskReferenceResolution(
                task_index=planned_indices[index_value],
                kind=ReferenceKind.INDEX,
            )
        if not planned_indices:
            raise PromptWarriorError(
                "No planned ('-') tasks exist, so index references are unavailable."
            )
        raise PromptWarriorError(
            f"Planned-task index {index_value} is out of range. "
            f"Available range: 0 to {len(planned_indices) - 1}."
        )

    raise PromptWarriorError(
        f"Could not resolve task reference '{reference}'. "
        "Use a full stem, prefix, or planned-task index."
    )


def format_match_list(document: WorkDocument, task_indices: list[int]) -> str:
    items = [
        f"{document.tasks[index].stem} (line {document.tasks[index].line_number})"
        for index in task_indices
    ]
    return ", ".join(items)


def sibling_group(
    document: WorkDocument, task_index: int
) -> tuple[int | None, list[int]]:
    parent_index = document.tasks[task_index].parent_task_index
    return parent_index, child_task_indices(document, parent_index)


def insertion_point_for_new_task(
    document: WorkDocument,
    *,
    mode: AddMode,
    parent_task_index: int | None,
    top: bool,
) -> tuple[int, str]:
    if mode in {AddMode.SUBTASK, AddMode.CORRECTION_CHILD, AddMode.AGENT_CHILD}:
        if parent_task_index is None:
            raise PromptWarriorError(
                "Internal error: missing parent for child insertion."
            )

        parent = document.tasks[parent_task_index]
        if parent.child_task_indices:
            indent_raw = document.tasks[parent.child_task_indices[0]].indent_raw
        else:
            indent_raw = f"{parent.indent_raw}{INDENT_UNIT}"

        if top and parent.child_task_indices:
            first_child_index = parent.child_task_indices[0]
            return document.tasks[first_child_index].line_index, indent_raw

        return block_end_line_index(document, parent_task_index), indent_raw

    top_level_indices = top_level_task_indices(document)
    if not top_level_indices:
        return len(document.lines), ""

    if top:
        return document.tasks[top_level_indices[0]].line_index, ""

    planned_top = [
        index
        for index in top_level_indices
        if document.tasks[index].bullet == BulletType.PLANNED
    ]
    if planned_top:
        return block_end_line_index(document, planned_top[-1]), ""

    done_top = [
        index
        for index in top_level_indices
        if document.tasks[index].bullet == BulletType.DONE
    ]
    if done_top:
        return document.tasks[done_top[0]].line_index, ""

    return len(document.lines), ""


def task_display_path(app_ctx: AppContext, link_path: str) -> str:
    if app_ctx.full_path:
        return (app_ctx.prompts_dir / link_path).as_posix()
    return Path(link_path).with_suffix("").as_posix()


def resolve_task_path(app_ctx: AppContext, link_path: str) -> Path:
    task_path = Path(link_path)
    if task_path.is_absolute():
        return task_path
    return app_ctx.prompts_dir / task_path


def require_workspace(app_ctx: AppContext) -> Path:
    prompts_dir = app_ctx.prompts_dir
    work_path = prompts_dir / WORK_FILENAME

    if not prompts_dir.exists():
        raise PromptWarriorError(
            f"Prompts directory '{prompts_dir}' does not exist. Run `pwr init` first."
        )
    if not prompts_dir.is_dir():
        raise PromptWarriorError(f"Path '{prompts_dir}' exists but is not a directory.")
    if not work_path.exists():
        raise PromptWarriorError(f"Missing plan file '{work_path}'.")

    return work_path


def load_document_for_command(app_ctx: AppContext) -> tuple[Path, WorkDocument]:
    work_path = require_workspace(app_ctx)
    document = parse_work_document(work_path)
    app_ctx.logger.debug(
        "Loaded work document from %s with %d parsed task lines.",
        work_path,
        len(document.tasks),
    )
    emit_warnings(app_ctx, document)
    return work_path, document


def copy_task_content(app_ctx: AppContext, task: TaskLine) -> Path:
    task_path = resolve_task_path(app_ctx, task.link_path)
    if not task_path.exists():
        raise PromptWarriorError(f"Task file does not exist: {task_path}")

    task_content = task_path.read_text(encoding="utf-8")
    app_ctx.clipboard.copy(task_content)
    return task_path


def build_commit_command(
    task_label: str, add_all_command: str, commit_command: str
) -> str:
    normalized_add_all = add_all_command.strip()
    normalized_commit = commit_command.strip()

    if not normalized_add_all and not normalized_commit:
        raise PromptWarriorError(
            "Both --add-all-command and --commit-command are empty."
        )

    command_parts: list[str] = []
    if normalized_add_all:
        command_parts.append(normalized_add_all)
    if normalized_commit:
        command_parts.append(
            f"{normalized_commit} {_always_single_quote_shell(task_label)}"
        )

    return " && ".join(command_parts)


def _always_single_quote_shell(value: str) -> str:
    escaped_value = value.replace("'", "'\"'\"'")
    return f"'{escaped_value}'"


def delete_task_block(document: WorkDocument, task_index: int) -> list[str]:
    lines = list(document.lines)
    start = document.tasks[task_index].line_index
    end = block_end_line_index(document, task_index)
    del lines[start:end]
    cleanup_delete_separation(lines, start, document.newline)
    return lines


def delete_task_keep_children(document: WorkDocument, task_index: int) -> list[str]:
    lines = list(document.lines)
    task = document.tasks[task_index]

    for child_index in task.child_task_indices:
        child = document.tasks[child_index]
        lines[child.line_index] = render_task_line(child, indent_raw=task.indent_raw)

    del lines[task.line_index]
    cleanup_delete_separation(lines, task.line_index, document.newline)
    return lines


def collect_subtree_indices(document: WorkDocument, root_index: int) -> list[int]:
    result: list[int] = []
    stack = [root_index]
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(reversed(document.tasks[current].child_task_indices))
    result.sort(key=lambda index: document.tasks[index].line_index)
    return result


def remove_task_files(app_ctx: AppContext, tasks: list[TaskLine]) -> None:
    for task in tasks:
        task_path = resolve_task_path(app_ctx, task.link_path)
        try:
            task_path.unlink()
        except FileNotFoundError:
            app_ctx.console.print(
                f"Warning: file not found while deleting task link target: {task_path}",
                style="warning",
            )


def mark_done_and_move_to_bottom(document: WorkDocument, task_index: int) -> list[str]:
    lines = list(document.lines)
    task = document.tasks[task_index]
    lines[task.line_index] = render_task_line(task, bullet=BulletType.DONE)

    parent_index, siblings = sibling_group(document, task_index)
    del parent_index
    if not siblings or siblings[-1] == task_index:
        return lines

    start = task.line_index
    end = block_end_line_index(document, task_index)
    block = lines[start:end]

    last_sibling = siblings[-1]
    destination = block_end_line_index(document, last_sibling)
    del lines[start:end]

    if destination > start:
        destination -= end - start

    ensure_insert_separation(lines, destination, document.newline)
    lines[destination:destination] = block
    return lines


def remaining_relevant_siblings_count(document: WorkDocument, task_index: int) -> int:
    _, siblings = sibling_group(document, task_index)
    return sum(
        1
        for sibling_index in siblings
        if document.tasks[sibling_index].bullet
        not in {BulletType.DONE, BulletType.AGENT}
    )


def siblings_all_done(document: WorkDocument, parent_index: int) -> bool:
    considered_children = 0
    for child_index in document.tasks[parent_index].child_task_indices:
        bullet = document.tasks[child_index].bullet
        if bullet == BulletType.AGENT:
            continue
        considered_children += 1
        if bullet != BulletType.DONE:
            return False
    return considered_children > 0


def _clean_bucket_folder_name(
    document: WorkDocument,
    bucket: CleanToFoldersBucket,
    *,
    used_folder_names: set[str],
) -> Path:
    chosen_prefix: str | None = None
    for root_task_index in bucket.root_task_indices:
        prefix = extract_prefix_from_stem(document.tasks[root_task_index].stem)
        if is_standard_task_prefix(prefix):
            chosen_prefix = prefix
            break

    if chosen_prefix is not None:
        return Path(generated_task_folder_name(chosen_prefix))

    index = 1
    while True:
        candidate = f"{index:04d}_tasks"
        if candidate not in used_folder_names:
            return Path(candidate)
        index += 1


def _sorted_clean_candidates(document: WorkDocument) -> list[tuple[int, list[int]]]:
    candidates: list[tuple[int, list[int]]] = []
    for root_task_index in _sorted_top_level_task_indices_for_foldering(document):
        root_task = document.tasks[root_task_index]
        if task_folder_for_line(root_task) != Path("."):
            continue
        candidates.append(
            (
                root_task_index,
                collect_subtree_indices(document, root_task_index),
            )
        )

    return candidates


def _task_foldering_order_key(task: TaskLine) -> tuple[tuple[int, int], str, str, int]:
    return (
        (0, prefix_rank)
        if (prefix_rank := standard_prefix_order(extract_prefix_from_stem(task.stem)))
        is not None
        else (1, 0),
        task.stem.casefold(),
        task.link_path.casefold(),
        task.line_index,
    )


def _sorted_top_level_task_indices_for_foldering(document: WorkDocument) -> list[int]:
    indices = top_level_task_indices(document)
    indices.sort(key=lambda index: _task_foldering_order_key(document.tasks[index]))
    return indices


def plan_clean_to_folders(
    app_ctx: AppContext,
    document: WorkDocument,
    *,
    max_folder_tasks: int = DEFAULT_MAX_FOLDER_TASKS,
) -> CleanToFoldersPlan:
    validated_max = validate_max_folder_tasks(max_folder_tasks)
    plan = CleanToFoldersPlan(max_folder_tasks=validated_max)
    plan.projected_task_link_paths = {
        task_index: task.link_path for task_index, task in enumerate(document.tasks)
    }

    if validated_max == 0:
        plan.noop_reason = "Foldering disabled by --max-folder-tasks=0."
        return plan

    candidates = _sorted_clean_candidates(document)
    if not candidates:
        plan.noop_reason = "No root-level task files to move."
        return plan

    buckets: list[CleanToFoldersBucket] = []
    current_bucket = CleanToFoldersBucket(folder_rel_path=Path("__pending__"))

    for root_task_index, subtree_indices in candidates:
        subtree_size = len(subtree_indices)
        if current_bucket.task_indices and (
            current_bucket.task_count + subtree_size > validated_max
        ):
            buckets.append(current_bucket)
            current_bucket = CleanToFoldersBucket(folder_rel_path=Path("__pending__"))

        current_bucket.root_task_indices.append(root_task_index)
        current_bucket.task_indices.extend(subtree_indices)
        current_bucket.task_count += subtree_size

    if current_bucket.task_indices:
        buckets.append(current_bucket)

    existing_folder_names = (
        {path.name for path in app_ctx.prompts_dir.iterdir() if path.is_dir()}
        if app_ctx.prompts_dir.exists()
        else set()
    )
    used_folder_names = set(existing_folder_names)
    assigned_bucket_folders: set[Path] = set()

    for bucket in buckets:
        folder_rel_path = _clean_bucket_folder_name(
            document,
            bucket,
            used_folder_names=used_folder_names,
        )
        bucket.folder_rel_path = folder_rel_path
        used_folder_names.add(folder_rel_path.name)
        assigned_bucket_folders.add(folder_rel_path)

    destination_abs_paths: set[Path] = set()

    for bucket in buckets:
        for task_index in bucket.task_indices:
            task = document.tasks[task_index]
            source_rel_path = Path(task.link_path)
            destination_rel_path = bucket.folder_rel_path / source_rel_path.name
            move = CleanToFoldersMove(
                task_index=task_index,
                source_rel_path=source_rel_path,
                destination_rel_path=destination_rel_path,
            )
            plan.moves.append(move)

            rewrite = CleanToFoldersRewrite(
                task_index=task_index,
                line_index=task.line_index,
                old_link_path=task.link_path,
                new_link_path=destination_rel_path.as_posix(),
            )
            plan.rewrites.append(rewrite)
            plan.projected_task_link_paths[task_index] = rewrite.new_link_path

    for move in plan.moves:
        source_abs_path = app_ctx.prompts_dir / move.source_rel_path
        destination_abs_path = app_ctx.prompts_dir / move.destination_rel_path

        if not source_abs_path.exists():
            raise PromptWarriorError(f"Task file does not exist: {source_abs_path}")
        if destination_abs_path in destination_abs_paths:
            raise PromptWarriorError(
                f"Internal error: duplicate move destination {destination_abs_path}"
            )
        destination_abs_paths.add(destination_abs_path)

        destination_parent = destination_abs_path.parent
        if destination_parent.exists() and not destination_parent.is_dir():
            raise PromptWarriorError(
                "Destination parent exists but is not a directory: "
                f"{destination_parent}"
            )
        if destination_abs_path.exists():
            raise PromptWarriorError(
                f"Destination file already exists: {destination_abs_path}"
            )

    plan.buckets = buckets
    plan.rewrites.sort(key=lambda rewrite: rewrite.line_index)
    plan.created_folder_rel_paths = list(
        dict.fromkeys(
            bucket.folder_rel_path
            for bucket in buckets
            if not (app_ctx.prompts_dir / bucket.folder_rel_path).exists()
        )
    )
    return plan


def apply_clean_to_folders_plan(
    app_ctx: AppContext,
    document: WorkDocument,
    work_path: Path,
    plan: CleanToFoldersPlan,
) -> None:
    if plan.noop_reason is not None or not plan.moves:
        return

    for folder_rel_path in plan.created_folder_rel_paths:
        (app_ctx.prompts_dir / folder_rel_path).mkdir(parents=True, exist_ok=True)

    for move in plan.moves:
        source_abs_path = app_ctx.prompts_dir / move.source_rel_path
        destination_abs_path = app_ctx.prompts_dir / move.destination_rel_path
        source_abs_path.rename(destination_abs_path)

    lines = list(document.lines)
    for rewrite in plan.rewrites:
        task = document.tasks[rewrite.task_index]
        lines[rewrite.line_index] = render_task_line(
            task,
            link_path=rewrite.new_link_path,
        )

    write_work_lines(work_path, lines)
