from __future__ import annotations

from typing import Optional

from . import Notifier


class ConsoleNotifier(Notifier):
    """Prints alerts to stdout. Useful for --dry-run and local testing."""

    def send(self, subject: str, message: str, html: Optional[str] = None) -> None:
        print(f"=== {subject} ===\n{message}\n")
