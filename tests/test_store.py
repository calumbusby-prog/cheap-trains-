from datetime import date

from cheaptrains.store import AlertStore


def test_alert_dedup_and_price_drop_retrigger(tmp_path):
    store = AlertStore(tmp_path / "state.sqlite3")
    outbound, inbound = date(2026, 10, 2), date(2026, 10, 4)

    assert store.should_alert("Route", outbound, inbound, 50.0) is True
    store.record_alert("Route", outbound, inbound, 50.0)

    assert store.should_alert("Route", outbound, inbound, 55.0) is False
    assert store.should_alert("Route", outbound, inbound, 50.0) is False
    assert store.should_alert("Route", outbound, inbound, 45.0) is True

    store.close()


def test_different_routes_are_independent(tmp_path):
    store = AlertStore(tmp_path / "state.sqlite3")
    outbound, inbound = date(2026, 10, 2), date(2026, 10, 4)

    store.record_alert("Route A", outbound, inbound, 50.0)
    assert store.should_alert("Route B", outbound, inbound, 50.0) is True

    store.close()
