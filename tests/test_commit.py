from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from prompt_warrior.__main__ import cli
from prompt_warrior.commands.commit import build_commit_copied_line


class _DummyClipboard:
    def __init__(self) -> None:
        self.copied: list[str] = []

    def copy(self, text: str) -> None:
        self.copied.append(text)


def test_build_commit_copied_line_styles_command_separately() -> None:
    line = build_commit_copied_line("gaa && gcam 'Initialization'")

    assert line.plain == "gaa && gcam 'Initialization' copied to clipboard"
    assert [span.style for span in line.spans] == ["highlight", "success"]


def test_recursive_commit_uses_shallowest_closed_task_label() -> None:
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

        clipboard = _DummyClipboard()
        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=clipboard,
        ):
            result = runner.invoke(cli, ["commit", "--recursive"])

        assert result.exit_code == 0, result.output
        assert clipboard.copied == ["gaa && gcam 'Parent'"]
        assert "gaa && gcam 'Parent' copied to clipboard" in result.output
        assert (
            "Marked 2 task(s) as done starting with 'Current child' A_tasks/A_current."
        ) in result.output
        assert "Top level: no remaining relevant task." in result.output
        assert (prompts_dir / "__plan.md").read_text(encoding="utf-8") == (
            "! [Parent](A_tasks/A_parent.md)\n"
            "  ! [Done child](A_tasks/A_done.md)\n"
            "  ! [Current child](A_tasks/A_current.md)\n"
        )


def test_recursive_commit_keeps_leaf_label_when_parent_stays_open() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        (prompts_dir / "__plan.md").write_text(
            (
                "- [Parent](A_tasks/A_parent.md)\n"
                "  - [Planned sibling](A_tasks/A_sibling.md)\n"
                "  * [Current child](A_tasks/A_current.md)\n"
            ),
            encoding="utf-8",
        )

        clipboard = _DummyClipboard()
        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=clipboard,
        ):
            result = runner.invoke(cli, ["commit", "--recursive"])

        assert result.exit_code == 0, result.output
        assert clipboard.copied == ["gaa && gcam 'Current child'"]
        assert "gaa && gcam 'Current child' copied to clipboard" in result.output
        assert (
            "Marked 1 task(s) as done starting with 'Current child' A_tasks/A_current."
        ) in result.output
        assert "Sublevel 1: 1 remaining relevant task." in result.output
        assert (prompts_dir / "__plan.md").read_text(encoding="utf-8") == (
            "- [Parent](A_tasks/A_parent.md)\n"
            "  - [Planned sibling](A_tasks/A_sibling.md)\n"
            "  ! [Current child](A_tasks/A_current.md)\n"
        )


def test_recursive_no_done_keeps_deepest_active_task_label() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        original_plan = (
            "- [Parent](A_tasks/A_parent.md)\n"
            "  ! [Done child](A_tasks/A_done.md)\n"
            "  * [Current child](A_tasks/A_current.md)\n"
        )
        (prompts_dir / "__plan.md").write_text(
            original_plan,
            encoding="utf-8",
        )

        clipboard = _DummyClipboard()
        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=clipboard,
        ):
            result = runner.invoke(cli, ["commit", "--recursive", "--no-done"])

        assert result.exit_code == 0, result.output
        assert clipboard.copied == ["gaa && gcam 'Current child'"]
        assert (
            result.output.strip() == "gaa && gcam 'Current child' copied to clipboard"
        )
        assert (prompts_dir / "__plan.md").read_text(encoding="utf-8") == original_plan


def test_non_recursive_commit_always_quotes_single_word_label() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        prompts_dir = Path(".prompts")
        prompts_dir.mkdir()
        original_plan = "* [Initialization](A_tasks/A_initialization.md)\n"
        (prompts_dir / "__plan.md").write_text(original_plan, encoding="utf-8")

        clipboard = _DummyClipboard()
        with patch(
            "prompt_warrior.__main__.select_clipboard_provider",
            return_value=clipboard,
        ):
            result = runner.invoke(cli, ["commit", "--no-done"])

        assert result.exit_code == 0, result.output
        assert clipboard.copied == ["gaa && gcam 'Initialization'"]
        assert (
            result.output.strip() == "gaa && gcam 'Initialization' copied to clipboard"
        )
        assert (prompts_dir / "__plan.md").read_text(encoding="utf-8") == original_plan
