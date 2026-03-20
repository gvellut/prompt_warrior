from __future__ import annotations

from enum import Enum, auto
import logging
from pathlib import Path
from typing import Protocol

from attrs import define, field
from rich.console import Console

from .constants import FALLBACK_NEWLINE


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
SUBTASK_PARENT_BULLETS = {
    BulletType.PLANNED,
    BulletType.ACTIVE,
    BulletType.CORRECTION,
}


class ClipboardProvider(Protocol):
    def copy(self, text: str) -> None:
        """Copy text to system clipboard."""


@define
class InvariantWarning:
    message: str


@define
class TaskLine:
    line_index: int
    indent_raw: str
    indent_expanded: int
    bullet: BulletType
    is_correction: bool
    ws_after_bullet: str
    link_path: str
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
    full_path: bool
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


@define
class CloseTaskPlan:
    task_signatures: list[TaskSignature]
    shallowest_signature: TaskSignature
    shallowest_depth: int
    initial_link_path: str


@define
class CleanToFoldersMove:
    task_index: int
    source_rel_path: Path
    destination_rel_path: Path


@define
class CleanToFoldersRewrite:
    task_index: int
    line_index: int
    old_link_path: str
    new_link_path: str


@define
class CleanToFoldersBucket:
    folder_rel_path: Path
    root_task_indices: list[int] = field(factory=list)
    task_indices: list[int] = field(factory=list)
    task_count: int = 0


@define
class CleanToFoldersPlan:
    max_folder_tasks: int
    buckets: list[CleanToFoldersBucket] = field(factory=list)
    moves: list[CleanToFoldersMove] = field(factory=list)
    rewrites: list[CleanToFoldersRewrite] = field(factory=list)
    created_folder_rel_paths: list[Path] = field(factory=list)
    projected_task_link_paths: dict[int, str] = field(factory=dict)
    noop_reason: str | None = None
