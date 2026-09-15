"""Best-effort price provider that reads renfe.com's public ticket search.

Renfe has no documented public pricing API. This provider drives the real
renfe.com search form with Playwright (the same approach used by community
projects like renfe-bot and renfe-notifier-bot) and scrapes the cheapest
fare shown in the results list.

This is inherently fragile: Renfe can change their markup at any time, may
show interstitial cookie/consent dialogs, and may rate-limit or CAPTCHA
automated traffic. Treat this module as a starting point you will likely
need to adjust:

  1. Run with ``headless=False`` (see ``RenfeProvider.__init__``) to watch
     what happens and compare against the selectors below.
  2. Open renfe.com in a real browser's devtools, repeat the search, and
     update ``_SELECTORS`` to match what you see.
  3. If Renfe's terms of service prohibit automated access for your use
     case, use a licensed data source instead (e.g. a distributor/partner
     API such as Omio's or Trainline's business API) by writing a new class
     that implements ``PriceProvider`` -- the rest of this project does not
     care where prices come from.

Requires: ``pip install playwright`` and ``playwright install chromium``.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from . import Offer, PriceProvider

logger = logging.getLogger(__name__)

# Centralised here so they're the first (and hopefully only) thing you need
# to edit when Renfe changes their site.
_SEARCH_URL = "https://www.renfe.com/es/en"
_SELECTORS = {
    "accept_cookies": "#onetrust-accept-btn-handler",
    "origin_input": "#origin",
    "destination_input": "#destination",
    "origin_suggestion": "li.rf-autocomplete__suggestion",
    "destination_suggestion": "li.rf-autocomplete__suggestion",
    "outbound_date_input": "#first-input",
    "search_button": "#buscarBillet",
    "results_rows": "div.trayectoTren",
    "result_price": ".precio-final",
}


class RenfeProvider(PriceProvider):
    def __init__(self, headless: bool = True, timeout_ms: int = 20000) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "RenfeProvider requires playwright. Install it with "
                "`pip install playwright && playwright install chromium`."
            ) from exc

        self._timeout_ms = timeout_ms
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)

    def get_cheapest_price(
        self, origin: str, destination: str, travel_date: date
    ) -> Optional[Offer]:
        page = self._browser.new_page()
        try:
            page.goto(_SEARCH_URL, timeout=self._timeout_ms)
            self._dismiss_cookie_banner(page)
            self._fill_station(page, _SELECTORS["origin_input"], _SELECTORS["origin_suggestion"], origin)
            self._fill_station(
                page, _SELECTORS["destination_input"], _SELECTORS["destination_suggestion"], destination
            )
            self._set_date(page, travel_date)
            page.click(_SELECTORS["search_button"], timeout=self._timeout_ms)
            page.wait_for_selector(_SELECTORS["results_rows"], timeout=self._timeout_ms)

            prices = []
            for price_el in page.query_selector_all(_SELECTORS["result_price"]):
                text = (price_el.inner_text() or "").strip()
                parsed = _parse_price(text)
                if parsed is not None:
                    prices.append(parsed)

            if not prices:
                logger.warning(
                    "No prices parsed for %s -> %s on %s; Renfe's markup may have "
                    "changed, or there are no trains that day. See renfe.py docstring.",
                    origin,
                    destination,
                    travel_date,
                )
                return None

            cheapest = min(prices)
            return Offer(price=cheapest, currency="EUR", url=page.url)
        except Exception:  # noqa: BLE001 - surfaced as a log, caller treats as "no data"
            logger.exception(
                "Renfe lookup failed for %s -> %s on %s", origin, destination, travel_date
            )
            return None
        finally:
            page.close()

    def _dismiss_cookie_banner(self, page) -> None:
        try:
            page.click(_SELECTORS["accept_cookies"], timeout=3000)
        except Exception:  # noqa: BLE001 - banner may not appear
            pass

    def _fill_station(self, page, input_selector: str, suggestion_selector: str, value: str) -> None:
        page.fill(input_selector, "")
        page.type(input_selector, value, delay=50)
        page.wait_for_selector(suggestion_selector, timeout=self._timeout_ms)
        page.click(suggestion_selector)

    def _set_date(self, page, travel_date: date) -> None:
        page.fill(_SELECTORS["outbound_date_input"], travel_date.strftime("%d/%m/%Y"))

    def close(self) -> None:
        try:
            self._browser.close()
        finally:
            self._playwright.stop()


def _parse_price(text: str) -> Optional[float]:
    cleaned = text.replace("€", "").replace(",", ".").strip()
    digits = "".join(ch for ch in cleaned if ch.isdigit() or ch == ".")
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None
