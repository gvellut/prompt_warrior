from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from prompt_warrior.__main__ import cli


class _DummyClipboard:
    def __init__(self) -> None:
        self.copied: list[str] = []

    def copy(self, text: str) -> None:
        self.copied.append(text)


class CommitCliTests(unittest.TestCase):
    def test_recursive_commit_uses_shallowest_closed_task_label(self) -> None:
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

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(clipboard.copied, ["gaa && gcam 'Parent'"])
            self.assertIn("Marked 2 task(s) as done", result.output)
            self.assertIn("Top level: no remaining relevant task.", result.output)
            self.assertEqual(
                (prompts_dir / "__plan.md").read_text(encoding="utf-8"),
                (
                    "! [Parent](A_tasks/A_parent.md)\n"
                    "  ! [Done child](A_tasks/A_done.md)\n"
                    "  ! [Current child](A_tasks/A_current.md)\n"
                ),
            )

    def test_recursive_commit_keeps_leaf_label_when_parent_stays_open(self) -> None:
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

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(clipboard.copied, ["gaa && gcam 'Current child'"])
            self.assertIn("Marked 1 task(s) as done", result.output)
            self.assertIn("Sublevel 1: 1 remaining relevant task.", result.output)
            self.assertEqual(
                (prompts_dir / "__plan.md").read_text(encoding="utf-8"),
                (
                    "- [Parent](A_tasks/A_parent.md)\n"
                    "  - [Planned sibling](A_tasks/A_sibling.md)\n"
                    "  ! [Current child](A_tasks/A_current.md)\n"
                ),
            )

    def test_recursive_no_done_keeps_deepest_active_task_label(self) -> None:
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

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(clipboard.copied, ["gaa && gcam 'Current child'"])
            self.assertEqual(result.output.strip(), "gaa && gcam 'Current child'")
            self.assertEqual(
                (prompts_dir / "__plan.md").read_text(encoding="utf-8"),
                original_plan,
            )

    def test_non_recursive_commit_always_quotes_single_word_label(self) -> None:
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

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(clipboard.copied, ["gaa && gcam 'Initialization'"])
            self.assertEqual(result.output.strip(), "gaa && gcam 'Initialization'")
            self.assertEqual(
                (prompts_dir / "__plan.md").read_text(encoding="utf-8"),
                original_plan,
            )


if __name__ == "__main__":
    unittest.main()
