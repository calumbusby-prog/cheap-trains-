"""A deterministic fake price provider, useful for demos, tests and dry runs
without needing a browser or hitting any real ticketing site."""

from __future__ import annotations

import hashlib
import random
from datetime import date
from typing import Optional

from . import Offer, PriceProvider


class MockProvider(PriceProvider):
    def __init__(
        self,
        base_price: float = 45.0,
        volatility: float = 30.0,
        seed_prefix: str = "cheaptrains-mock",
    ) -> None:
        self.base_price = base_price
        self.volatility = volatility
        self.seed_prefix = seed_prefix

    def get_cheapest_price(
        self, origin: str, destination: str, travel_date: date
    ) -> Optional[Offer]:
        key = f"{self.seed_prefix}:{origin.lower()}:{destination.lower()}:{travel_date.isoformat()}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        rng = random.Random(digest)
        price = round(max(9.0, self.base_price + rng.uniform(-self.volatility, self.volatility)), 2)
        hour = rng.randint(6, 21)
        return Offer(
            price=price,
            currency="EUR",
            departure_time=f"{hour:02d}:00",
            train_id=f"MOCK-{digest[:6].upper()}",
            url=None,
        )
