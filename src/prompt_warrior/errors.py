from __future__ import annotations


class PromptWarriorError(Exception):
    """Base exception for domain-level errors."""


class ParseIssue(PromptWarriorError):
    """Raised when the plan file has a structural issue."""
