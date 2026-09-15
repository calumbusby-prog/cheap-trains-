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


def _format_date(d: date) -> str:
    return d.strftime("%a %d %b %Y")


def _format_time(offer: Offer) -> str:
    return offer.departure_time or "time TBD"


def format_alert(route: RouteConfig, deal: RoundTripDeal) -> tuple[str, str, str]:
    """Returns (subject, plain_text_body, html_body)."""
    subject = f"Cheap weekend fare: {route.name} - {deal.total_price:.2f} {route.currency}"

    legs = [
        ("Outbound", deal.outbound_date, deal.outbound_offer),
        ("Return", deal.return_date, deal.return_offer),
    ]

    label_width = max(len(label) for label, _, _ in legs)
    date_width = max(len(_format_date(d)) for _, d, _ in legs)
    text_lines = [
        f"{route.name}",
        f"{deal.total_price:.2f} {route.currency} total "
        f"(threshold {route.max_total_price:.2f} {route.currency})",
        "",
    ]
    for label, leg_date, offer in legs:
        text_lines.append(
            f"{label:<{label_width}}  {_format_date(leg_date):<{date_width}}  "
            f"{_format_time(offer):>5}  {offer.price:>8.2f} {offer.currency}"
        )
    if deal.outbound_offer.url:
        text_lines += ["", f"Book: {deal.outbound_offer.url}"]
    text = "\n".join(text_lines)

    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e5e5;color:#555;">{label}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e5e5;">{_format_date(leg_date)}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e5e5;">{_format_time(offer)}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e5e5;text-align:right;font-weight:600;">{offer.price:.2f} {offer.currency}</td>
        </tr>"""
        for label, leg_date, offer in legs
    )
    book_html = (
        f'<p style="margin:16px 0 0;"><a href="{deal.outbound_offer.url}" '
        f'style="color:#0b5fff;">Book this trip &rarr;</a></p>'
        if deal.outbound_offer.url
        else ""
    )
    html = f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:480px;">
      <h2 style="margin:0 0 4px;font-size:18px;">{route.name}</h2>
      <p style="margin:0 0 16px;font-size:26px;font-weight:700;color:#0a8a3c;">
        {deal.total_price:.2f} {route.currency}
        <span style="font-size:13px;font-weight:400;color:#777;">
          &nbsp;(threshold {route.max_total_price:.2f} {route.currency})
        </span>
      </p>
      <table style="border-collapse:collapse;width:100%;">
        <thead>
          <tr style="background:#f7f7f7;text-align:left;">
            <th style="padding:8px 14px;font-size:12px;text-transform:uppercase;color:#888;">Leg</th>
            <th style="padding:8px 14px;font-size:12px;text-transform:uppercase;color:#888;">Date</th>
            <th style="padding:8px 14px;font-size:12px;text-transform:uppercase;color:#888;">Time</th>
            <th style="padding:8px 14px;font-size:12px;text-transform:uppercase;color:#888;text-align:right;">Price</th>
          </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
      </table>
      {book_html}
    </div>
    """

    return subject, text, html


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

            subject, text, html = format_alert(route, deal)
            for notifier in notifiers:
                try:
                    notifier.send(subject, text, html)
                except Exception:  # noqa: BLE001
                    logger.exception("Notifier %s failed to send alert", type(notifier).__name__)
            store.record_alert(route.name, deal.outbound_date, deal.return_date, deal.total_price)
            alerts_sent += 1
            logger.info("Alerted on %s for %.2f %s", route.name, deal.total_price, route.currency)

    return alerts_sent
