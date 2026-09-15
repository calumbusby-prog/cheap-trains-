"""SQLite-backed record of alerts already sent, so we don't spam the same
route/date pair every time the checker runs -- only when the price drops
below what we last alerted on."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path


class AlertStore:
    def __init__(self, path: str | Path) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                route_name TEXT NOT NULL,
                outbound_date TEXT NOT NULL,
                return_date TEXT NOT NULL,
                price REAL NOT NULL,
                alerted_at TEXT NOT NULL,
                PRIMARY KEY (route_name, outbound_date, return_date)
            )
            """
        )
        self._conn.commit()

    def should_alert(
        self, route_name: str, outbound_date: date, return_date: date, price: float
    ) -> bool:
        row = self._conn.execute(
            "SELECT price FROM alerts WHERE route_name = ? AND outbound_date = ? AND return_date = ?",
            (route_name, outbound_date.isoformat(), return_date.isoformat()),
        ).fetchone()
        if row is None:
            return True
        previous_price: float = row[0]
        return price < previous_price - 0.01

    def record_alert(
        self, route_name: str, outbound_date: date, return_date: date, price: float
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO alerts (route_name, outbound_date, return_date, price, alerted_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(route_name, outbound_date, return_date)
            DO UPDATE SET price = excluded.price, alerted_at = excluded.alerted_at
            """,
            (
                route_name,
                outbound_date.isoformat(),
                return_date.isoformat(),
                price,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
