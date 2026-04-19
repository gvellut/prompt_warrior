from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from rich.console import Console

from prompt_warrior.__main__ import cli
from prompt_warrior.commands.done import build_close_result_line
from prompt_warrior.models import AppContext


class _DummyClipboard:
    def copy(self, text: str) -> None:
        del text


def _build_app_context(prompts_dir: str, full_path: bool) -> AppContext:
    return AppContext(
        debug=False,
        prompts_dir=Path(prompts_dir),
        full_path=full_path,
        console=Console(),
        logger=logging.getLogger("prompt_warrior.test"),
        clipboard=_DummyClipboard(),
    )


def test_build_close_result_line_styles_label_and_path() -> None:
    line = build_close_result_line(
        _build_app_context(".prompts", full_path=False),
        closed_count=2,
        initial_label="Current child",
        initial_link_path="A_tasks/A_current.md",
    )

    assert (
        line.plain
        == "Marked 2 task(s) as done starting with 'Current child' A_tasks/A_current."
    )
    assert [span.style for span in line.spans] == [
        "success",
        "label_highlight",
        "success",
        "highlight",
        "success",
    ]


def test_done_marks_task_and_reports_new_message() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            "* [Current](A_tasks/A_current.md)\n",
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(cli, ["done"])

        assert result.exit_code == 0, result.output
        assert (
            "Marked 1 task(s) as done starting with 'Current' A_tasks/A_current."
            in result.output
        )
        assert "Top level: no remaining relevant task." in result.output
        assert (prompts_dir / "__plan.md").read_text(encoding="utf-8") == (
            "! [Current](A_tasks/A_current.md)\n"
        )


def test_done_recursive_keeps_starting_leaf_label_and_path() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            (
                "- [Parent](A_tasks/A_parent.md)\n"
                "  ! [Done child](A_tasks/A_done.md)\n"
                "  * [Current child](A_tasks/A_current.md)\n"
            ),
            encoding="utf-8",
        )

        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=_DummyClipboard(),
        ):
            result = runner.invoke(cli, ["done", "--recursive"])

        assert result.exit_code == 0, result.output
        assert (
            "Marked 2 task(s) as done starting with 'Current child' A_tasks/A_current."
        ) in result.output
        assert "Top level: no remaining relevant task." in result.output
        assert (prompts_dir / "__plan.md").read_text(encoding="utf-8") == (
            "! [Parent](A_tasks/A_parent.md)\n"
            "  ! [Done child](A_tasks/A_done.md)\n"
            "  ! [Current child](A_tasks/A_current.md)\n"
        )


def test_done_full_path_uses_prompts_dir_prefix() -> None:
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
                ["done"],
                env={
                    "PWAR_FULL_PATH": "1",
                    "PWAR_PROMPTS_DIR": "custom-prompts",
                },
            )

        assert result.exit_code == 0, result.output
        assert "Marked 1 task(s) as done starting with 'Current'" in result.output
        assert "custom-prompts/J_tasks/R_current.md." in result.output
