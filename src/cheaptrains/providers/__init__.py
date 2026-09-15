"""Pluggable price-lookup backends.

Every provider implements ``get_cheapest_price(origin, destination, travel_date)``
and returns the cheapest single-leg :class:`Offer` for that day, or ``None``
if nothing could be found. Swap providers in config.yaml (``provider: mock``
or ``provider: renfe``) without touching the alerting logic in ``alerts.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Offer:
    price: float
    currency: str
    departure_time: Optional[str] = None
    train_id: Optional[str] = None
    url: Optional[str] = None


class PriceProvider(ABC):
    @abstractmethod
    def get_cheapest_price(
        self, origin: str, destination: str, travel_date: date
    ) -> Optional[Offer]:
        """Return the cheapest offer for a single-direction trip on that date."""
        raise NotImplementedError

    def close(self) -> None:
        """Release any resources (browser sessions, connections, ...)."""
        return None
