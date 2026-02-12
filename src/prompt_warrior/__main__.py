from __future__ import annotations

import builtins
import logging
import platform
import re
import string
import subprocess
import unicodedata
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Iterator, Protocol

import click
from attrs import define, field
from click.shell_completion import CompletionItem
from rich.console import Console
from rich.theme import Theme

DEFAULT_PROMPTS_DIR = ".prompts"
WORK_FILENAME = "work.md"
DEFAULT_INIT_TASK_LABEL = "Initialization"
MARKDOWN_EXTENSION = ".md"
INDENT_WIDTH = 4
INDENT_UNIT = " " * INDENT_WIDTH
MAX_SAFE_LABEL_LENGTH = 48
FALLBACK_NEWLINE = "\n"

ENVVAR_PREFIX = "PWAR"
PWAR_DEBUG = f"{ENVVAR_PREFIX}_DEBUG"
PWAR_PROMPTS_DIR = f"{ENVVAR_PREFIX}_PROMPTS_DIR"
PWAR_NO_INIT_TASK = f"{ENVVAR_PREFIX}_NO_INIT_TASK"
PWAR_INIT_TASK_LABEL = f"{ENVVAR_PREFIX}_INIT_TASK_LABEL"
PWAR_FILENAME = f"{ENVVAR_PREFIX}_FILENAME"
PWAR_TOP = f"{ENVVAR_PREFIX}_TOP"
PWAR_SUB = f"{ENVVAR_PREFIX}_SUB"
PWAR_CORR = f"{ENVVAR_PREFIX}_CORR"
PWAR_AGENT = f"{ENVVAR_PREFIX}_AGENT"
PWAR_RECURSIVE = f"{ENVVAR_PREFIX}_RECURSIVE"
PWAR_KEEP_CHILDREN = f"{ENVVAR_PREFIX}_KEEP_CHILDREN"

RICH_THEME = Theme(
    {
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "highlight": "magenta",
        "important": "bold",
    }
)

TASK_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<bullet>[-*?!~])(?P<ws1>\s+)\[\]\((?P<link>[^)]+)\)(?P<ws2>\s+)(?P<label>[^\r\n]*)(?P<newline>\r?\n?)$"
)


class BulletType(Enum):
    PLANNED = auto()
    ACTIVE = auto()
    CORRECTION = auto()
    DONE = auto()
    AGENT = auto()


class ReferenceKind(Enum):
    STEM = auto()
    PREFIX = auto()
    INDEX = auto()


class AddMode(Enum):
    TOP_LEVEL = auto()
    SUBTASK = auto()
    CORRECTION_CHILD = auto()
    AGENT_CHILD = auto()


BULLET_TO_CHAR = {
    BulletType.PLANNED: "-",
    BulletType.ACTIVE: "*",
    BulletType.CORRECTION: "?",
    BulletType.DONE: "!",
    BulletType.AGENT: "~",
}
CHAR_TO_BULLET = {value: key for key, value in BULLET_TO_CHAR.items()}
ACTIONABLE_BULLETS = {BulletType.PLANNED, BulletType.CORRECTION}


class PromptWarriorError(Exception):
    """Base exception for domain-level errors."""


class ParseIssue(PromptWarriorError):
    """Raised when the work file has a structural issue."""


class ClipboardProvider(Protocol):
    def copy(self, text: str) -> None:
        """Copy text to system clipboard."""


@define
class MacOSClipboardProvider:
    def copy(self, text: str) -> None:
        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        except FileNotFoundError as exc:
            raise PromptWarriorError(
                "`pbcopy` was not found on this macOS system."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise PromptWarriorError(
                "Could not copy task content to the clipboard."
            ) from exc


@define
class UnsupportedClipboardProvider:
    system_name: str

    def copy(self, text: str) -> None:
        raise PromptWarriorError(
            f"Clipboard copy is only implemented for macOS. Detected system: {self.system_name}."
        )


@define
class InvariantWarning:
    message: str


@define
class TaskLine:
    line_index: int
    indent_raw: str
    indent_expanded: int
    bullet: BulletType
    ws_after_bullet: str
    link_path: str
    ws_after_link: str
    label: str
    newline: str
    raw_line: str
    parent_task_index: int | None = None
    child_task_indices: list[int] = field(factory=list)
    depth: int = 0

    @property
    def line_number(self) -> int:
        return self.line_index + 1

    @property
    def stem(self) -> str:
        return Path(self.link_path).stem


@define
class WorkDocument:
    path: Path
    lines: list[str]
    tasks: list[TaskLine]
    warnings: list[InvariantWarning] = field(factory=list)
    newline: str = FALLBACK_NEWLINE
    line_to_task_index: dict[int, int] = field(factory=dict)


@define
class AppContext:
    debug: bool
    prompts_dir: Path
    console: Console
    logger: logging.Logger
    clipboard: ClipboardProvider


@define
class TaskReferenceResolution:
    task_index: int
    kind: ReferenceKind


@define
class TaskSignature:
    link_path: str
    label: str
    indent_expanded: int


class RichErrorCommand(click.Command):
    """A command class that prints domain errors with Rich styling."""

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except click.exceptions.Exit:
            raise
        except click.Abort:
            raise
        except Exception as exc:  # noqa: BLE001
            app_ctx = ctx.find_object(AppContext)
            console = app_ctx.console if app_ctx else Console(theme=RICH_THEME)
            debug = app_ctx.debug if app_ctx else False

            if isinstance(exc, click.ClickException):
                message = exc.format_message()
                exit_code = exc.exit_code
            else:
                message = str(exc) if str(exc) else exc.__class__.__name__
                exit_code = 1

            console.print(message, style="error")
            if debug:
                console.print_exception()

            raise click.exceptions.Exit(exit_code) from exc


pass_app_context = click.make_pass_decorator(AppContext)


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


def parse_work_lines(path: Path, lines: list[str]) -> WorkDocument:
    document = WorkDocument(
        path=path, lines=list(lines), tasks=[], newline=detect_newline(lines)
    )

    for index, line in enumerate(document.lines):
        match = TASK_LINE_RE.match(line)
        if not match:
            continue

        bullet_char = match.group("bullet")
        bullet = CHAR_TO_BULLET[bullet_char]
        indent_raw = match.group("indent")
        task = TaskLine(
            line_index=index,
            indent_raw=indent_raw,
            indent_expanded=indent_width(indent_raw),
            bullet=bullet,
            ws_after_bullet=match.group("ws1"),
            link_path=match.group("link"),
            ws_after_link=match.group("ws2"),
            label=match.group("label"),
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
        raise PromptWarriorError(f"Missing work file: {path}")

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
    for parent_index, parent in enumerate(document.tasks):
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
                    f"parent line {parent.line_number}, first child line {first_child.line_number} "
                    f"uses depth {expected_depth}, but line {child.line_number} uses depth {child.indent_expanded}. "
                    "All direct children of the same parent must share one indentation depth."
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
            warnings.append(
                InvariantWarning(
                    f"Active-task invariant broken for {scope}: multiple '*' tasks found on lines {', '.join(map(str, active_lines))}."
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
                        "Active-task invariant broken: active tasks are not in a single parent-descendant chain."
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
        link_path=task.link_path, label=task.label, indent_expanded=task.indent_expanded
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
) -> str:
    rendered_bullet = BULLET_TO_CHAR[bullet or task.bullet]
    rendered_indent = task.indent_raw if indent_raw is None else indent_raw
    return (
        f"{rendered_indent}{rendered_bullet}{task.ws_after_bullet}[]({task.link_path})"
        f"{task.ws_after_link}{task.label}{task.newline}"
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


def shell_complete_task_reference(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    del param

    prompts_dir = resolve_prompts_dir_from_ctx(ctx)
    work_path = prompts_dir / WORK_FILENAME
    if not work_path.exists():
        return []

    try:
        document = parse_work_document(work_path)
    except PromptWarriorError:
        return []

    stems = sorted({task.stem for task in document.tasks if task.stem})
    return [CompletionItem(stem) for stem in stems if stem.startswith(incomplete)]


def argument_label_words(function: Callable[..., object]) -> Callable[..., object]:
    return click.argument("label_words", nargs=-1, metavar="LABEL_WORDS...")(function)


def argument_task_reference(function: Callable[..., object]) -> Callable[..., object]:
    return click.argument(
        "task_ref", metavar="TASK_REF", shell_complete=shell_complete_task_reference
    )(function)


def extract_prefix_from_stem(stem: str) -> str | None:
    if "_" not in stem:
        return None
    prefix, _ = stem.split("_", 1)
    return prefix or None


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


def choose_unused_prefix(used_prefixes: set[str]) -> str:
    for candidate in iter_prefix_candidates():
        if candidate not in used_prefixes:
            return candidate
    raise PromptWarriorError(
        "No available task prefix left in the configured sequence."
    )


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
            for index in top_level_task_indices(document)
            if (prefix := extract_prefix_from_stem(document.tasks[index].stem))
            is not None
        }

        while True:
            prefix = choose_unused_prefix(used_prefixes)
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
        local_prefix = choose_unused_prefix(used_child_locals)
        full_prefix = f"{parent_prefix}.{local_prefix}"
        stem = compose_stem(full_prefix, label_component)
        if not (app_ctx.prompts_dir / f"{stem}{MARKDOWN_EXTENSION}").exists():
            return stem
        used_child_locals.add(local_prefix)


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
            f"Reference '{reference}' is ambiguous by stem. Matches: {format_match_list(document, stem_matches)}"
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
            f"Reference '{reference}' is ambiguous by prefix. Matches: {format_match_list(document, prefix_matches)}"
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
                task_index=planned_indices[index_value], kind=ReferenceKind.INDEX
            )
        if not planned_indices:
            raise PromptWarriorError(
                "No planned ('-') tasks exist, so index references are unavailable."
            )
        raise PromptWarriorError(
            f"Planned-task index {index_value} is out of range. Available range: 0 to {len(planned_indices) - 1}."
        )

    raise PromptWarriorError(
        f"Could not resolve task reference '{reference}'. Use a full stem, prefix, or planned-task index."
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
            f"Prompts directory '{prompts_dir}' does not exist. Run `prompt-warrior init` first."
        )
    if not prompts_dir.is_dir():
        raise PromptWarriorError(f"Path '{prompts_dir}' exists but is not a directory.")
    if not work_path.exists():
        raise PromptWarriorError(f"Missing work file '{work_path}'.")

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


def select_clipboard_provider() -> ClipboardProvider:
    system_name = platform.system()
    if system_name == "Darwin":
        return MacOSClipboardProvider()
    return UnsupportedClipboardProvider(system_name=system_name)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    envvar=PWAR_DEBUG,
    help="Enable debug logging and stack traces on command errors.",
)
@click.option(
    "--prompts-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path(DEFAULT_PROMPTS_DIR),
    show_default=True,
    envvar=PWAR_PROMPTS_DIR,
    help="Directory containing prompts and work.md.",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool, prompts_dir: Path) -> None:
    """Prompt Warrior task CLI."""
    console = Console(theme=RICH_THEME)
    logger = logging.getLogger("prompt_warrior")

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(levelname)s %(message)s",
        )
    else:
        logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.debug("Debug mode enabled.")

    app_ctx = AppContext(
        debug=debug,
        prompts_dir=prompts_dir,
        console=console,
        logger=logger,
        clipboard=select_clipboard_provider(),
    )
    ctx.obj = app_ctx


@cli.command(
    cls=RichErrorCommand,
    help="Initialize the prompts directory and optional initial task.",
)
@click.option(
    "-b",
    "--no-init-task",
    is_flag=True,
    envvar=PWAR_NO_INIT_TASK,
    help="Create prompts directory and work.md without creating an initial task.",
)
@click.option(
    "--init-task-label",
    default=DEFAULT_INIT_TASK_LABEL,
    show_default=True,
    envvar=PWAR_INIT_TASK_LABEL,
    help="Label used for the initial task line and markdown filename seed.",
)
@pass_app_context
def init(app_ctx: AppContext, no_init_task: bool, init_task_label: str) -> None:
    prompts_dir = app_ctx.prompts_dir
    work_path = prompts_dir / WORK_FILENAME
    app_ctx.logger.debug(
        "Running init with prompts_dir=%s no_init=%s init_task=%s",
        prompts_dir,
        no_init_task,
        init_task_label,
    )

    if prompts_dir.exists():
        raise PromptWarriorError(f"Prompts directory already exists: {prompts_dir}")

    prompts_dir.mkdir(parents=True, exist_ok=False)

    if no_init_task:
        work_path.write_text("", encoding="utf-8")
        app_ctx.console.print(
            f"Initialized workspace at {prompts_dir}", style="success"
        )
        return

    label = init_task_label.strip() or DEFAULT_INIT_TASK_LABEL
    safe_component = make_safe_ascii_component(label)
    prefix = choose_unused_prefix(set())
    stem = compose_stem(prefix, safe_component)
    file_name = f"{stem}{MARKDOWN_EXTENSION}"

    (prompts_dir / file_name).write_text("", encoding="utf-8")
    work_path.write_text(
        f"- []({file_name}) {label}{FALLBACK_NEWLINE}", encoding="utf-8"
    )

    app_ctx.console.print(f"Initialized workspace at {prompts_dir}", style="success")
    app_ctx.console.print(f"Created initial task: {label}", style="highlight")


@cli.command(cls=RichErrorCommand, help="Create a new task and add it to work.md.")
@argument_label_words
@click.option(
    "-l",
    "--filename",
    "filename",
    envvar=PWAR_FILENAME,
    help="Override filename seed with safe-ASCII conversion.",
)
@click.option(
    "-t",
    "--top",
    is_flag=True,
    envvar=PWAR_TOP,
    help="Insert new planned task at the top of top-level tasks.",
)
@click.option(
    "-s",
    "--sub",
    "sub_reference",
    metavar="TASK_REF",
    envvar=PWAR_SUB,
    shell_complete=shell_complete_task_reference,
    help="Create as planned subtask under TASK_REF.",
)
@click.option(
    "-c",
    "--corr",
    is_flag=True,
    envvar=PWAR_CORR,
    help="Create as correction child (?) under the deepest active task.",
)
@click.option(
    "-a",
    "--agent",
    "agent_mode",
    is_flag=True,
    envvar=PWAR_AGENT,
    help="Create as agent child (~) under the deepest active task.",
)
@pass_app_context
def add(
    app_ctx: AppContext,
    label_words: tuple[str, ...],
    filename: str | None,
    top: bool,
    sub_reference: str | None,
    corr: bool,
    agent_mode: bool,
) -> None:
    app_ctx.logger.debug(
        "Running add with label_words=%s filename=%s top=%s sub_reference=%s corr=%s agent_mode=%s",
        label_words,
        filename,
        top,
        sub_reference,
        corr,
        agent_mode,
    )

    if not label_words:
        raise PromptWarriorError(
            "`add` requires positional label text (LABEL_WORDS...)."
        )

    mode_count = int(sub_reference is not None) + int(corr) + int(agent_mode)
    if mode_count > 1:
        raise PromptWarriorError("Use only one of --sub, --corr, or --agent.")

    if top and mode_count > 0:
        raise PromptWarriorError(
            "--top cannot be combined with --sub, --corr, or --agent."
        )

    label = " ".join(label_words).strip()
    if not label:
        raise PromptWarriorError("Task label cannot be empty.")

    if filename is not None:
        label_component = make_safe_ascii_component(filename)
    else:
        label_component = make_safe_ascii_component(label)

    work_path, document = load_document_for_command(app_ctx)

    parent_task_index: int | None = None
    bullet = BulletType.PLANNED
    mode = AddMode.TOP_LEVEL

    if sub_reference is not None:
        resolution = resolve_reference(document, sub_reference)
        parent_task_index = resolution.task_index
        mode = AddMode.SUBTASK
    elif corr:
        parent_task_index = deepest_active_task_index(document)
        if parent_task_index is None:
            raise PromptWarriorError(
                "No active task found. `--corr` requires an active task."
            )
        bullet = BulletType.CORRECTION
        mode = AddMode.CORRECTION_CHILD
    elif agent_mode:
        parent_task_index = deepest_active_task_index(document)
        if parent_task_index is None:
            raise PromptWarriorError(
                "No active task found. `--agent` requires an active task."
            )
        bullet = BulletType.AGENT
        mode = AddMode.AGENT_CHILD

    insert_at, indent_raw = insertion_point_for_new_task(
        document,
        mode=mode,
        parent_task_index=parent_task_index,
        top=top,
    )

    stem = choose_task_stem(
        app_ctx,
        document=document,
        parent_task_index=parent_task_index,
        label_component=label_component,
    )
    file_name = f"{stem}{MARKDOWN_EXTENSION}"
    task_path = app_ctx.prompts_dir / file_name
    task_path.write_text("", encoding="utf-8")

    new_line = f"{indent_raw}{BULLET_TO_CHAR[bullet]} []({file_name}) {label}{document.newline}"
    lines = list(document.lines)
    ensure_insert_separation(lines, insert_at, document.newline)
    lines.insert(insert_at, new_line)

    write_work_lines(work_path, lines)
    app_ctx.console.print(f"Added task: {label}", style="success")
    app_ctx.console.print(f"Created file: {file_name}", style="highlight")


@cli.command(
    cls=RichErrorCommand,
    help="Mark the deepest active task as done and move it to the end of its sibling list.",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    envvar=PWAR_RECURSIVE,
    help="Also mark parent tasks done when all siblings are done (ignoring '~').",
)
@pass_app_context
def done(app_ctx: AppContext, recursive: bool) -> None:
    app_ctx.logger.debug("Running done with recursive=%s", recursive)
    work_path, document = load_document_for_command(app_ctx)

    current_task_index = deepest_active_task_index(document)
    if current_task_index is None:
        raise PromptWarriorError("No active task found to close.")

    current_signature = task_signature(document.tasks[current_task_index])
    lines = list(document.lines)
    closed_count = 0

    while True:
        document = parse_work_lines(work_path, lines)
        current_task_index = find_task_by_signature(document, current_signature)
        if current_task_index is None:
            raise PromptWarriorError(
                "Could not locate the task to close after internal reordering."
            )

        parent_signature: TaskSignature | None = None
        parent_index = document.tasks[current_task_index].parent_task_index
        if parent_index is not None:
            parent_signature = task_signature(document.tasks[parent_index])

        lines = mark_done_and_move_to_bottom(document, current_task_index)
        closed_count += 1

        if not recursive or parent_signature is None:
            break

        updated_document = parse_work_lines(work_path, lines)
        updated_parent_index = find_task_by_signature(
            updated_document, parent_signature
        )
        if updated_parent_index is None:
            break

        parent_task = updated_document.tasks[updated_parent_index]
        if parent_task.bullet == BulletType.AGENT:
            break

        if parent_task.bullet == BulletType.DONE:
            break

        if not siblings_all_done(updated_document, updated_parent_index):
            break

        current_signature = task_signature(parent_task)

    write_work_lines(work_path, lines)
    app_ctx.console.print(f"Marked {closed_count} task(s) as done.", style="success")


@cli.command(
    name="next",
    cls=RichErrorCommand,
    help="Activate the next task and copy its markdown file content to the clipboard.",
)
@pass_app_context
def next_task(app_ctx: AppContext) -> None:
    app_ctx.logger.debug("Running next")
    work_path, document = load_document_for_command(app_ctx)

    deepest_active = deepest_active_task_index(document)
    if deepest_active is None:
        scope_parent: int | None = None
    elif document.tasks[deepest_active].child_task_indices:
        scope_parent = deepest_active
    else:
        scope_parent = None

    scope_tasks = child_task_indices(document, scope_parent)

    scope_active = [
        index
        for index in scope_tasks
        if document.tasks[index].bullet == BulletType.ACTIVE
    ]
    if scope_active:
        raise PromptWarriorError(
            "There is already an active task at this level. Run `prompt-warrior done` first."
        )

    next_candidate = builtins.next(
        (
            index
            for index in scope_tasks
            if document.tasks[index].bullet in ACTIONABLE_BULLETS
        ),
        None,
    )

    if next_candidate is None:
        if scope_parent is not None:
            raise PromptWarriorError(
                "No remaining '-' or '?' child task. Run `prompt-warrior done` to close the parent first."
            )
        raise PromptWarriorError("No remaining '-' or '?' top-level task to activate.")

    task = document.tasks[next_candidate]
    task_path = resolve_task_path(app_ctx, task.link_path)
    if not task_path.exists():
        raise PromptWarriorError(f"Task file does not exist: {task_path}")

    task_content = task_path.read_text(encoding="utf-8")
    app_ctx.clipboard.copy(task_content)

    lines = list(document.lines)
    lines[task.line_index] = render_task_line(task, bullet=BulletType.ACTIVE)
    write_work_lines(work_path, lines)

    app_ctx.console.print(f"Activated task: {task.label}", style="success")
    app_ctx.console.print(
        f"Copied task content from {task_path.name}", style="highlight"
    )


@cli.command(
    cls=RichErrorCommand,
    help="Delete a task by reference and optionally keep/promote its direct children.",
)
@argument_task_reference
@click.option(
    "--keep-children",
    is_flag=True,
    envvar=PWAR_KEEP_CHILDREN,
    help="Delete only the target task and promote direct children to the target level.",
)
@pass_app_context
def delete(app_ctx: AppContext, task_ref: str, keep_children: bool) -> None:
    app_ctx.logger.debug(
        "Running delete with task_ref=%s keep_children=%s", task_ref, keep_children
    )
    work_path, document = load_document_for_command(app_ctx)

    resolution = resolve_reference(document, task_ref)
    task_index = resolution.task_index
    task = document.tasks[task_index]

    descendants = collect_subtree_indices(document, task_index)[1:]
    direct_children_count = len(task.child_task_indices)

    if task.bullet == BulletType.ACTIVE or direct_children_count > 0:
        confirmation_message = (
            f"Delete task '{task.label}' on line {task.line_number}? "
            f"direct children: {direct_children_count}, total descendants: {len(descendants)}"
        )
        if not click.confirm(confirmation_message, default=False):
            raise PromptWarriorError("Delete cancelled by user.")

    if keep_children:
        lines = delete_task_keep_children(document, task_index)
        remove_task_files(app_ctx, [task])
    else:
        lines = delete_task_block(document, task_index)
        delete_indices = collect_subtree_indices(document, task_index)
        remove_task_files(app_ctx, [document.tasks[index] for index in delete_indices])

    write_work_lines(work_path, lines)
    app_ctx.console.print(f"Deleted task: {task.label}", style="success")


if __name__ == "__main__":
    cli()
