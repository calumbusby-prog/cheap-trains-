"""Ties together config, a price provider, the dedup store and notifiers
into a single "check all routes for cheap weekend fares" run."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .config import Config, RouteConfig
from .dates import WeekendWindow, upcoming_weekends
from .notifiers import Notifier
from .providers import Offer, PriceProvider
from .store import AlertStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoundTripDeal:
    outbound_date: date
    outbound_offer: Offer
    return_date: date
    return_offer: Offer

    @property
    def total_price(self) -> float:
        return self.outbound_offer.price + self.return_offer.price


def _cheapest_offer(
    provider: PriceProvider, origin: str, destination: str, candidate_dates: tuple[date, ...]
) -> Optional[tuple[date, Offer]]:
    best: Optional[tuple[date, Offer]] = None
    for candidate_date in candidate_dates:
        offer = provider.get_cheapest_price(origin, destination, candidate_date)
        if offer is None:
            continue
        if best is None or offer.price < best[1].price:
            best = (candidate_date, offer)
    return best


def find_cheapest_weekend_deal(
    provider: PriceProvider, route: RouteConfig, window: WeekendWindow
) -> Optional[RoundTripDeal]:
    outbound = _cheapest_offer(provider, route.origin, route.destination, window.outbound_dates)
    if outbound is None:
        return None
    inbound = _cheapest_offer(provider, route.destination, route.origin, window.return_dates)
    if inbound is None:
        return None
    outbound_date, outbound_offer = outbound
    return_date, return_offer = inbound
    return RoundTripDeal(
        outbound_date=outbound_date,
        outbound_offer=outbound_offer,
        return_date=return_date,
        return_offer=return_offer,
    )


def format_alert(route: RouteConfig, deal: RoundTripDeal) -> tuple[str, str]:
    subject = f"Cheap weekend fare: {route.name} - {deal.total_price:.2f} {route.currency}"
    lines = [
        f"{route.name} weekend trip for {deal.total_price:.2f} {route.currency} "
        f"(threshold {route.max_total_price:.2f} {route.currency})",
        f"Outbound: {deal.outbound_date.isoformat()} "
        f"({deal.outbound_offer.departure_time or 'time TBD'}) - "
        f"{deal.outbound_offer.price:.2f} {deal.outbound_offer.currency}",
        f"Return:   {deal.return_date.isoformat()} "
        f"({deal.return_offer.departure_time or 'time TBD'}) - "
        f"{deal.return_offer.price:.2f} {deal.return_offer.currency}",
    ]
    if deal.outbound_offer.url:
        lines.append(f"Book: {deal.outbound_offer.url}")
    return subject, "\n".join(lines)


def run_once(
    config: Config,
    provider: PriceProvider,
    notifiers: list[Notifier],
    store: AlertStore,
    today: Optional[date] = None,
) -> int:
    """Check every configured route against upcoming weekends. Returns the
    number of alerts sent."""
    today = today or date.today()
    alerts_sent = 0

    for route in config.routes:
        windows = upcoming_weekends(
            today,
            config.weekend.lookahead_weekends,
            config.weekend.outbound_days,
            config.weekend.return_days,
        )
        for window in windows:
            deal = find_cheapest_weekend_deal(provider, route, window)
            if deal is None:
                continue
            if deal.total_price > route.max_total_price:
                continue
            if not store.should_alert(route.name, deal.outbound_date, deal.return_date, deal.total_price):
                continue

            subject, message = format_alert(route, deal)
            for notifier in notifiers:
                try:
                    notifier.send(subject, message)
                except Exception:  # noqa: BLE001
                    logger.exception("Notifier %s failed to send alert", type(notifier).__name__)
            store.record_alert(route.name, deal.outbound_date, deal.return_date, deal.total_price)
            alerts_sent += 1
            logger.info("Alerted on %s for %.2f %s", route.name, deal.total_price, route.currency)

    return alerts_sent
