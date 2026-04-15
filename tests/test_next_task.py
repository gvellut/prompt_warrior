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


class NextTaskCliTests(unittest.TestCase):
    def test_next_reports_active_top_level_task_details(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            prompts_dir = Path(".prompts")
            prompts_dir.mkdir()
            (prompts_dir / "__plan.md").write_text(
                ("* [Current](A_tasks/A_current.md)\n- [Next](A_tasks/A_next.md)\n"),
                encoding="utf-8",
            )

            with patch(
                "prompt_warrior.__main__.select_clipboard_provider",
                return_value=_DummyClipboard(),
            ):
                result = runner.invoke(cli, ["next"])

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn(
                "There is already an active task. Run `pwr done` first.",
                result.output,
            )
            self.assertIn("Active task: Current", result.output)
            self.assertIn("Level: Top level", result.output)
            self.assertIn("Path: A_tasks/A_current", result.output)

    def test_next_reports_deepest_active_task_details(self) -> None:
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

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("Active task: Current child", result.output)
            self.assertIn("Level: Sublevel 1", result.output)
            self.assertIn("Path: A_tasks/A_current", result.output)
            self.assertNotIn("Active task: Parent", result.output)

    def test_next_full_path_error_uses_prompts_dir_prefix(self) -> None:
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

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn(
                "Path: custom-prompts/J_tasks/R_current.md",
                result.output,
            )

    def test_next_activates_planned_task_and_copies_content(self) -> None:
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

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(clipboard.copied, ["next task body"])
            self.assertIn("Activated task: A_tasks/A_next", result.output)
            self.assertIn("Copied task content.", result.output)
            self.assertEqual(
                (prompts_dir / "__plan.md").read_text(encoding="utf-8"),
                "* [Next](A_tasks/A_next.md)\n",
            )


if __name__ == "__main__":
    unittest.main()
