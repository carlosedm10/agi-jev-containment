from __future__ import annotations

from enum import IntEnum


class Level(IntEnum):
    """Criticality level returned by the classifier (docs/Actions.md)."""

    MILD = 1
    MODERATE = 2
    SEVERE = 3
    CRITICAL = 4
    CATASTROPHIC = 5

    @classmethod
    def from_choice(cls, choice: str) -> Level:
        """Map a jev choice key like ``level_3_severe`` to its Level."""
        try:
            return cls(int(choice.split("_")[1]))
        except (IndexError, ValueError) as e:
            raise ValueError(f"unknown jev choice: {choice!r}") from e
