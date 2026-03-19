from __future__ import annotations

import logging
from pathlib import Path
import unittest
from unittest.mock import patch

from click.testing import CliRunner
from rich.console import Console

from prompt_warrior.__main__ import cli
from prompt_warrior.core import task_display_path
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


class TaskDisplayPathTests(unittest.TestCase):
    def test_default_display_path_strips_markdown_suffix(self) -> None:
        app_ctx = _build_app_context(".prompts", full_path=False)

        display_path = task_display_path(app_ctx, "J_tasks/R_task.md")

        self.assertEqual(display_path, "J_tasks/R_task")

    def test_full_path_display_uses_default_prompts_dir_and_keeps_suffix(self) -> None:
        app_ctx = _build_app_context(".prompts", full_path=True)

        display_path = task_display_path(app_ctx, "J_tasks/R_task.md")

        self.assertEqual(display_path, ".prompts/J_tasks/R_task.md")

    def test_full_path_display_uses_custom_prompts_dir(self) -> None:
        app_ctx = _build_app_context("custom-prompts", full_path=True)

        display_path = task_display_path(app_ctx, "J_tasks/R_task.md")

        self.assertEqual(display_path, "custom-prompts/J_tasks/R_task.md")


class FullPathCliTests(unittest.TestCase):
    def test_init_full_path_prints_prefixed_markdown_path(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "prompt_warrior.__main__.select_clipboard_provider",
                return_value=_DummyClipboard(),
            ):
                result = runner.invoke(cli, ["--full-path", "init"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Created initial task: .prompts/", result.output)
            self.assertIn(".md", result.output)

            work_text = Path(".prompts/__plan.md").read_text(encoding="utf-8")
            self.assertIn("](", work_text)
            self.assertNotIn("(.prompts/", work_text)

    def test_add_full_path_prints_prefixed_markdown_path_without_changing_link(
        self,
    ) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            prompts_dir = Path(".prompts")
            prompts_dir.mkdir()
            (prompts_dir / "__plan.md").write_text("", encoding="utf-8")

            with patch(
                "prompt_warrior.__main__.select_clipboard_provider",
                return_value=_DummyClipboard(),
            ):
                result = runner.invoke(cli, ["--full-path", "add", "Add", "path"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Added task: .prompts/", result.output)
            self.assertIn(".md", result.output)

            work_text = (prompts_dir / "__plan.md").read_text(encoding="utf-8")
            self.assertIn("](", work_text)
            self.assertNotIn("(.prompts/", work_text)

    def test_read_full_path_uses_env_overrides_for_prompts_dir_and_flag(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            prompts_dir = Path("custom-prompts")
            task_rel_path = Path("J_tasks/R_current.md")
            (prompts_dir / task_rel_path.parent).mkdir(parents=True)
            (prompts_dir / "__plan.md").write_text(
                "* [Current](J_tasks/R_current.md)\n",
                encoding="utf-8",
            )
            (prompts_dir / task_rel_path).write_text("current task", encoding="utf-8")

            with patch(
                "prompt_warrior.__main__.select_clipboard_provider",
                return_value=_DummyClipboard(),
            ):
                result = runner.invoke(
                    cli,
                    ["read"],
                    env={
                        "PWAR_FULL_PATH": "1",
                        "PWAR_PROMPTS_DIR": "custom-prompts",
                    },
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn(
                "Copied task content from custom-prompts/J_tasks/R_current.md",
                result.output,
            )


if __name__ == "__main__":
    unittest.main()
