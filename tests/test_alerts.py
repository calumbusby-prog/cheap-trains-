from datetime import date

from cheaptrains.alerts import run_once
from cheaptrains.config import Config, EmailConfig, RouteConfig, TelegramConfig, WeekendConfig
from cheaptrains.notifiers import Notifier
from cheaptrains.providers.mock import MockProvider
from cheaptrains.store import AlertStore


class RecordingNotifier(Notifier):
    def __init__(self):
        self.sent = []

    def send(self, subject, message):
        self.sent.append((subject, message))


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
