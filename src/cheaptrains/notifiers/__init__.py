"""Pluggable notification channels."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Notifier(ABC):
    @abstractmethod
    def send(self, subject: str, message: str, html: Optional[str] = None) -> None:
        """``message`` is a plain-text body every notifier must support.
        ``html`` is an optional richer rendering -- notifiers that can't
        display HTML (Telegram, console) simply ignore it."""
        raise NotImplementedError
