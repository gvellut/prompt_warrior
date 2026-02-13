from __future__ import annotations

import re

from rich.theme import Theme

DEFAULT_PROMPTS_DIR = ".prompts"
WORK_FILENAME = "__battle.md"
DEFAULT_INIT_TASK_LABEL = "Initialization"
DEFAULT_COMMIT_COMMAND = "gcam"
DEFAULT_ADD_ALL_COMMAND = "gaa"
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
PWAR_COMMIT_COMMAND = f"{ENVVAR_PREFIX}_COMMIT_COMMAND"
PWAR_ADD_ALL_COMMAND = f"{ENVVAR_PREFIX}_ADD_ALL_COMMAND"
PWAR_NO_DONE = f"{ENVVAR_PREFIX}_NO_DONE"

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
    r"^(?P<indent>[ \t]*)(?P<bullet>[-*?!~])(?P<ws1>\s+)"
    r"\[(?P<link_text>[^\]]*)\]\((?P<link>[^)]+)\)"
    r"(?P<ws2>[ \t]*)(?P<trailing_label>[^\r\n]*)(?P<newline>\r?\n?)$"
)
