from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console

from prompt_warrior.core import choose_task_stem, parse_work_lines
from prompt_warrior.models import AppContext


class _ClipboardStub:
    def copy(self, text: str) -> None:
        del text


def _parse_document(lines: list[str]):
    return parse_work_lines(path=Path("__plan.md"), lines=lines)


def _make_app_ctx(prompts_dir: Path) -> AppContext:
    return AppContext(
        debug=False,
        prompts_dir=prompts_dir,
        full_path=False,
        console=Console(record=True),
        logger=logging.getLogger("prompt_warrior.tests"),
        clipboard=_ClipboardStub(),
    )


def test_top_level_uses_prefix_after_last_instead_of_filling_gap(
    tmp_path: Path,
) -> None:
    document = _parse_document(
        [
            "- [P root](P_root.md)\n",
            "- [Q root](Q_root.md)\n",
            "- [R root](R_root.md)\n",
            "- [T root](T_root.md)\n",
            "- [U root](U_root.md)\n",
            "- [V root](V_root.md)\n",
        ]
    )

    stem = choose_task_stem(
        _make_app_ctx(tmp_path),
        document=document,
        parent_task_index=None,
        label_component="new_task",
    )

    assert stem == "W_new_task"


def test_child_uses_prefix_after_last_in_custom_global_order(tmp_path: Path) -> None:
    document = _parse_document(
        [
            "- [Parent](P_parent.md)\n",
            "  - [B child](P.B_child.md)\n",
            "  - [Aa child](P.Aa_child.md)\n",
        ]
    )

    stem = choose_task_stem(
        _make_app_ctx(tmp_path),
        document=document,
        parent_task_index=0,
        label_component="new_child",
    )

    assert stem == "P.Ba_new_child"
