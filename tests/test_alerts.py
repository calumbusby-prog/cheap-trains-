from datetime import date

from cheaptrains.alerts import RoundTripDeal, format_alert, run_once
from cheaptrains.config import Config, EmailConfig, RouteConfig, TelegramConfig, WeekendConfig
from cheaptrains.notifiers import Notifier
from cheaptrains.providers import Offer
from cheaptrains.providers.mock import MockProvider
from cheaptrains.store import AlertStore


class RecordingNotifier(Notifier):
    def __init__(self):
        self.sent = []

    def send(self, subject, message, html=None):
        self.sent.append((subject, message, html))


def _make_config(max_total_price: float) -> Config:
    return Config(
        provider="mock",
        weekend=WeekendConfig(outbound_days=["FRI", "SAT"], return_days=["SUN", "MON"], lookahead_weekends=2),
        routes=[
            RouteConfig(
                name="Test Route",
                origin="Madrid",
                destination="Barcelona",
                max_total_price=max_total_price,
            )
        ],
        telegram=TelegramConfig(enabled=False),
        email=EmailConfig(enabled=False),
        state_file="unused",
    )


def test_run_once_sends_alerts_and_dedupes_on_rerun(tmp_path):
    config = _make_config(max_total_price=1_000_000)  # always under threshold
    provider = MockProvider()
    notifier = RecordingNotifier()
    store = AlertStore(tmp_path / "state.sqlite3")

    sent_first = run_once(config, provider, [notifier], store, today=date(2026, 9, 16))
    assert sent_first > 0
    assert len(notifier.sent) == sent_first

    sent_second = run_once(config, provider, [notifier], store, today=date(2026, 9, 16))
    assert sent_second == 0

    store.close()


def test_run_once_respects_price_threshold(tmp_path):
    config = _make_config(max_total_price=-1)  # nothing is ever cheap enough
    provider = MockProvider()
    notifier = RecordingNotifier()
    store = AlertStore(tmp_path / "state.sqlite3")

    sent = run_once(config, provider, [notifier], store, today=date(2026, 9, 16))
    assert sent == 0
    assert notifier.sent == []

    store.close()


def test_format_alert_shows_date_journey_price_and_time():
    route = RouteConfig(
        name="Madrid -> Barcelona", origin="Madrid", destination="Barcelona", max_total_price=60
    )
    deal = RoundTripDeal(
        outbound_date=date(2026, 10, 10),
        outbound_offer=Offer(price=32.82, currency="EUR", departure_time="11:00"),
        return_date=date(2026, 10, 12),
        return_offer=Offer(price=23.80, currency="EUR", departure_time="18:00"),
    )

    subject, text, html = format_alert(route, deal)

    assert "Madrid -> Barcelona" in subject
    assert "56.62" in subject

    # Plain text: journey name, and each leg's date, time and price.
    assert "Madrid -> Barcelona" in text
    assert "Sat 10 Oct 2026" in text
    assert "11:00" in text
    assert "32.82 EUR" in text
    assert "Mon 12 Oct 2026" in text
    assert "18:00" in text
    assert "23.80 EUR" in text

    # HTML: same data points, rendered as a table.
    assert "Madrid -> Barcelona" in html
    assert "Sat 10 Oct 2026" in html
    assert "Mon 12 Oct 2026" in html
    assert "32.82 EUR" in html
    assert "23.80 EUR" in html
    assert "<table" in html
