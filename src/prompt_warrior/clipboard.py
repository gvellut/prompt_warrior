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
class WindowsClipboardProvider:
    def copy(self, text: str) -> None:
        try:
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
        except FileNotFoundError as exc:
            raise PromptWarriorError(
                "`clip` was not found on this Windows system."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise PromptWarriorError(
                "Could not copy task content to the clipboard."
            ) from exc


@define
class LinuxClipboardProvider:
    def copy(self, text: str) -> None:
        copy_commands = (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        )

        for command in copy_commands:
            try:
                subprocess.run(command, input=text.encode("utf-8"), check=True)
                return
            except FileNotFoundError:
                continue
            except subprocess.CalledProcessError:
                continue

        raise PromptWarriorError(
            "Could not copy task content to the clipboard. "
            "On Linux, install and configure one of: wl-copy, xclip, xsel."
        )


@define
class UnsupportedClipboardProvider:
    system_name: str

    def copy(self, text: str) -> None:
        del text
        raise PromptWarriorError(
            "Clipboard copy is only implemented for macOS, Linux, and Windows. "
            f"Detected system: {self.system_name}."
        )


def select_clipboard_provider() -> ClipboardProvider:
    system_name = platform.system()
    if system_name == "Darwin":
        return MacOSClipboardProvider()
    if system_name == "Windows":
        return WindowsClipboardProvider()
    if system_name == "Linux":
        return LinuxClipboardProvider()
    return UnsupportedClipboardProvider(system_name=system_name)
