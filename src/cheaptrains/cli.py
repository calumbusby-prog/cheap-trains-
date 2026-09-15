from __future__ import annotations

import argparse
import logging
import sys

from .alerts import run_once
from .config import load_config
from .notifiers import Notifier
from .notifiers.console import ConsoleNotifier
from .notifiers.email_notifier import EmailNotifier
from .notifiers.telegram_notifier import TelegramNotifier
from .providers import PriceProvider
from .store import AlertStore


def _build_provider(name: str) -> PriceProvider:
    if name == "mock":
        from .providers.mock import MockProvider

        return MockProvider()
    if name == "renfe":
        from .providers.renfe import RenfeProvider

        return RenfeProvider()
    raise ValueError(f"Unknown provider: {name!r} (expected 'mock' or 'renfe')")


def _build_notifiers(config, dry_run: bool) -> list[Notifier]:
    if dry_run:
        return [ConsoleNotifier()]

    notifiers: list[Notifier] = []
    if config.telegram.enabled:
        notifiers.append(TelegramNotifier(config.telegram.bot_token, config.telegram.chat_id))
    if config.email.enabled:
        notifiers.append(
            EmailNotifier(
                smtp_host=config.email.smtp_host,
                smtp_port=config.email.smtp_port,
                username=config.email.username,
                password=config.email.password,
                from_addr=config.email.from_addr,
                to_addrs=config.email.to_addrs,
            )
        )
    if not notifiers:
        logging.warning("No notifiers enabled in config; falling back to console output")
        notifiers.append(ConsoleNotifier())
    return notifiers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cheaptrains", description=__doc__)
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print alerts to stdout instead of sending via configured notifiers",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    provider = _build_provider(config.provider)
    notifiers = _build_notifiers(config, args.dry_run)
    store = AlertStore(config.state_file)

    try:
        alerts_sent = run_once(config, provider, notifiers, store)
        logging.info("Done. %d alert(s) sent.", alerts_sent)
    finally:
        provider.close()
        store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
