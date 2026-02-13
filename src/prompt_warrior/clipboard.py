from __future__ import annotations

import platform
import subprocess

from attrs import define

from .errors import PromptWarriorError
from .models import ClipboardProvider


@define
class MacOSClipboardProvider:
    def copy(self, text: str) -> None:
        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        except FileNotFoundError as exc:
            raise PromptWarriorError(
                "`pbcopy` was not found on this macOS system."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise PromptWarriorError(
                "Could not copy task content to the clipboard."
            ) from exc


@define
class UnsupportedClipboardProvider:
    system_name: str

    def copy(self, text: str) -> None:
        del text
        raise PromptWarriorError(
            "Clipboard copy is only implemented for macOS. "
            f"Detected system: {self.system_name}."
        )


def select_clipboard_provider() -> ClipboardProvider:
    system_name = platform.system()
    if system_name == "Darwin":
        return MacOSClipboardProvider()
    return UnsupportedClipboardProvider(system_name=system_name)
