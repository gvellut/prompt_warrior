from __future__ import annotations

from pathlib import Path
import logging
from unittest.mock import patch

from click.testing import CliRunner
from rich.console import Console

from prompt_warrior.__main__ import cli
from prompt_warrior.commands.current import build_current_lines
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


def test_current_lines_use_expected_styles_for_top_level_task() -> None:
    app_ctx = _build_app_context(".prompts", full_path=False)
    document = parse_work_lines(
        path=Path("__plan.md"),
        lines=[
            "* [Current](A_tasks/A_current.md)\n",
            "- [Next](A_tasks/A_next.md)\n",
        ],
    )

    lines = build_current_lines(app_ctx, document, 0)

    assert lines[0].plain == "Current task: Current"
    assert lines[0].spans[0].style == "success"
    assert lines[0].spans[1].style == "highlight"
    assert lines[1].plain == "Path: A_tasks/A_current"
    assert lines[1].spans[0].style == "success"
    assert lines[1].spans[1].style == "highlight"
    assert lines[2].plain == "Top level: 1 remaining task after current."
    assert lines[2].spans[0].style == "success"
    assert lines[2].spans[1].style == "highlight"


def test_current_reports_top_level_active_task() -> None:
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
            result = runner.invoke(cli, ["current"])

        assert result.exit_code == 0, result.output
        assert "Current task: Current" in result.output
        assert "Path: A_tasks/A_current" in result.output
        assert "Top level: 1 remaining task after current." in result.output


def test_current_reports_deepest_active_subtask_hierarchy() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            (
                "* [Parent](A_tasks/A_parent.md)\n"
                "  * [Current child](A_tasks/A_current.md)\n"
                "  - [Planned sibling](A_tasks/A_sibling.md)\n"
            ),
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(cli, ["current"])

        assert result.exit_code == 0, result.output
        assert "Current task: Current child" in result.output
        assert "Path: A_tasks/A_current" in result.output
        assert "Sublevel 1: 1 remaining task after current." in result.output
        assert "Hierarchy (bottom to top):" in result.output
        assert result.output.rstrip().endswith("Current child\nParent")


def test_current_marks_correction_leaf_in_hierarchy() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            (
                "* [Parent](A_tasks/A_parent.md)\n"
                "  *? [Correction child](A_tasks/A_current.md)\n"
            ),
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(cli, ["current"])

        assert result.exit_code == 0, result.output
        assert "Current task: Correction child" in result.output
        assert "Sublevel 1: No other remaining task." in result.output
        assert result.output.rstrip().endswith("Correction child (correction)\nParent")


def test_current_full_path_uses_prompts_dir_prefix() -> None:
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
                ["current"],
                env={
                    "PWAR_FULL_PATH": "1",
                    "PWAR_PROMPTS_DIR": "custom-prompts",
                },
            )

        assert result.exit_code == 0, result.output
        assert "Path: custom-prompts/J_tasks/R_current.md" in result.output


def test_current_fails_when_no_active_task_exists() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            "- [Planned](A_tasks/A_planned.md)\n",
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(cli, ["current"])

        assert result.exit_code == 1, result.output
        assert "No active task found to display." in result.output
