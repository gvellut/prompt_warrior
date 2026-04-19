from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from rich.console import Console

from prompt_warrior.__main__ import cli
from prompt_warrior.commands.next_task import (
    build_activated_task_line,
    build_active_task_error_lines,
)
from prompt_warrior.core import parse_work_lines
from prompt_warrior.models import AppContext


class _DummyClipboard:
    def __init__(self) -> None:
        self.copied: list[str] = []

    def copy(self, text: str) -> None:
        self.copied.append(text)


def _build_app_context(prompts_dir: str, full_path: bool) -> AppContext:
    return AppContext(
        debug=False,
        prompts_dir=Path(prompts_dir),
        full_path=full_path,
        console=Console(),
        logger=logging.getLogger("prompt_warrior.test"),
        clipboard=_DummyClipboard(),
    )


def test_next_error_lines_use_expected_styles() -> None:
    app_ctx = _build_app_context(".prompts", full_path=False)
    document = parse_work_lines(
        path=Path("__plan.md"),
        lines=["* [Current](A_tasks/A_current.md)\n"],
    )

    lines = build_active_task_error_lines(app_ctx, document.tasks[0])

    assert lines[0].plain == "There is already an active task. Run `pwr done` first."
    assert lines[0].spans[0].style == "error"
    assert lines[1].plain == "Active task: Current"
    assert lines[1].spans[0].style == "success"
    assert lines[1].spans[1].style == "highlight"
    assert lines[2].plain == "Level: Top level"
    assert lines[2].spans[0].style == "success"
    assert lines[2].spans[1].style == "highlight"
    assert lines[3].plain == "Path: A_tasks/A_current"
    assert lines[3].spans[0].style == "success"
    assert lines[3].spans[1].style == "highlight"


def test_activated_task_line_uses_label_highlight_and_highlight_path() -> None:
    app_ctx = _build_app_context(".prompts", full_path=False)
    document = parse_work_lines(
        path=Path("__plan.md"),
        lines=["- [commit](S_tasks/X_commit.md)\n"],
    )

    line = build_activated_task_line(app_ctx, document.tasks[0])

    assert line.plain == "Activated task: 'commit' S_tasks/X_commit"
    assert [span.style for span in line.spans] == [
        "success",
        "label_highlight",
        "success",
        "highlight",
    ]


def test_next_reports_active_top_level_task_details() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            "* [Current](A_tasks/A_current.md)\n- [Next](A_tasks/A_next.md)\n",
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(cli, ["next"])

        assert result.exit_code == 1, result.output
        assert "There is already an active task. Run `pwr done` first." in result.output
        assert "Active task: Current" in result.output
        assert "Level: Top level" in result.output
        assert "Path: A_tasks/A_current" in result.output


def test_next_reports_deepest_active_task_details() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            (
                "* [Parent](A_tasks/A_parent.md)\n"
                "  * [Current child](A_tasks/A_current.md)\n"
                "- [Next root](B_tasks/B_next.md)\n"
            ),
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(cli, ["next"])

        assert result.exit_code == 1, result.output
        assert "Active task: Current child" in result.output
        assert "Level: Sublevel 1" in result.output
        assert "Path: A_tasks/A_current" in result.output
        assert "Active task: Parent" not in result.output


def test_next_full_path_error_uses_prompts_dir_prefix() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path("custom-prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            "* [Current](J_tasks/R_current.md)\n",
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(
                cli,
                ["next"],
                env={
                    "PWAR_FULL_PATH": "1",
                    "PWAR_PROMPTS_DIR": "custom-prompts",
                },
            )

        assert result.exit_code == 1, result.output
        assert "Path: custom-prompts/J_tasks/R_current.md" in result.output


def test_next_activates_planned_task_and_copies_content() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        task_rel_path = Path("A_tasks/A_next.md")
        (prompts_dir / task_rel_path.parent).mkdir(parents=True)
        (prompts_dir / "__plan.md").write_text(
            "- [Next](A_tasks/A_next.md)\n",
            encoding="utf-8",
        )
        (prompts_dir / task_rel_path).write_text("next task body", encoding="utf-8")

        clipboard = _DummyClipboard()
        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=clipboard,
        ):
            result = runner.invoke(cli, ["next"])

        assert result.exit_code == 0, result.output
        assert clipboard.copied == ["next task body"]
        assert "Activated task: 'Next' A_tasks/A_next" in result.output
        assert "Copied task content." in result.output
        assert (prompts_dir / "__plan.md").read_text(encoding="utf-8") == (
            "* [Next](A_tasks/A_next.md)\n"
        )
