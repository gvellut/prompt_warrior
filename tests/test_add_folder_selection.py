from __future__ import annotations

from pathlib import Path

from prompt_warrior.core import choose_top_level_add_folder, parse_work_lines


def _parse_document(lines: list[str]):
    return parse_work_lines(path=Path("__plan.md"), lines=lines)


def test_ignores_non_standard_last_top_level_when_reusing_folder() -> None:
    document = _parse_document(
        [
            "- [Ba root](Ba_tasks/Ba_root.md)\n",
            "- [Ja root](Ja_tasks/Ja_root.md)\n",
            "- [Ka root](Ka_tasks/Ka_root.md)\n",
            "- [odd](Ba_tasks/D.A_odd.md)\n",
        ]
    )

    folder = choose_top_level_add_folder(
        document,
        new_task_stem="La_new_task",
        max_folder_tasks=12,
        folder_name_override=None,
    )

    assert folder == Path("Ka_tasks")


def test_rolls_over_to_new_prefix_folder_when_current_standard_folder_is_full() -> None:
    document = _parse_document(
        [
            "- [Ba root](Ba_tasks/Ba_root.md)\n",
            "- [Ja first](Ja_tasks/Ja_first.md)\n",
            "- [Ja second](Ja_tasks/Ja_second.md)\n",
            "- [odd](Ba_tasks/D.A_odd.md)\n",
        ]
    )

    folder = choose_top_level_add_folder(
        document,
        new_task_stem="Ka_new_task",
        max_folder_tasks=2,
        folder_name_override=None,
    )

    assert folder == Path("Ka_tasks")
