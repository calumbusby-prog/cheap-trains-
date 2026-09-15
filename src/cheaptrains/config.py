from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass
class RouteConfig:
    name: str
    origin: str
    destination: str
    max_total_price: float
    currency: str = "EUR"


@dataclass
class WeekendConfig:
    outbound_days: list[str] = field(default_factory=lambda: ["FRI", "SAT"])
    return_days: list[str] = field(default_factory=lambda: ["SUN", "MON"])
    lookahead_weekends: int = 8


@dataclass
class TelegramConfig:
    enabled: bool
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class EmailConfig:
    enabled: bool
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)


@dataclass
class Config:
    provider: str
    weekend: WeekendConfig
    routes: list[RouteConfig]
    telegram: TelegramConfig
    email: EmailConfig
    state_file: str = "state.sqlite3"


def _expand_env(value):
    if isinstance(value, str):
        def replace(match: re.Match) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        return _ENV_VAR_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    raw = _expand_env(raw)

    if not raw.get("routes"):
        raise ValueError("config must define at least one route under 'routes'")

    weekend_raw = raw.get("weekend", {})
    weekend = WeekendConfig(
        outbound_days=weekend_raw.get("outbound_days", ["FRI", "SAT"]),
        return_days=weekend_raw.get("return_days", ["SUN", "MON"]),
        lookahead_weekends=weekend_raw.get("lookahead_weekends", 8),
    )

    routes = [
        RouteConfig(
            name=r["name"],
            origin=r["origin"],
            destination=r["destination"],
            max_total_price=float(r["max_total_price"]),
            currency=r.get("currency", "EUR"),
        )
        for r in raw["routes"]
    ]

    notif = raw.get("notifications", {})
    telegram_raw = notif.get("telegram", {})
    telegram = TelegramConfig(
        enabled=bool(telegram_raw.get("enabled", False)),
        bot_token=telegram_raw.get("bot_token", ""),
        chat_id=telegram_raw.get("chat_id", ""),
    )
    email_raw = notif.get("email", {})
    email = EmailConfig(
        enabled=bool(email_raw.get("enabled", False)),
        smtp_host=email_raw.get("smtp_host", ""),
        smtp_port=int(email_raw.get("smtp_port", 587)),
        username=email_raw.get("username", ""),
        password=email_raw.get("password", ""),
        from_addr=email_raw.get("from_addr", ""),
        to_addrs=email_raw.get("to_addrs", []),
    )

    return Config(
        provider=raw.get("provider", "mock"),
        weekend=weekend,
        routes=routes,
        telegram=telegram,
        email=email,
        state_file=raw.get("state_file", "state.sqlite3"),
    )
