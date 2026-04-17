from __future__ import annotations


class PromptWarriorError(Exception):
    """Base exception for domain-level errors."""

    def __init__(self, message: str, *, renderable: object | None = None) -> None:
        super().__init__(message)
        self.renderable = renderable


class ParseIssue(PromptWarriorError):
    """Raised when the plan file has a structural issue."""
