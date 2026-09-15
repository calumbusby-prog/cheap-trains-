# cheap-trains

Weekend cheap-train-ticket alert service for Spain. Configure routes and a
price threshold, and get a Telegram/email notification when a weekend
round trip (Fri/Sat out, Sun/Mon back) drops below your target price.

## How it works

1. `dates.py` figures out which Friday/Saturday and Sunday/Monday dates
   fall in each of the next N weekends.
2. For each configured route, a **price provider** looks up the cheapest
   fare for each candidate outbound/return date.
3. If the cheapest round trip found is at or under the route's
   `max_total_price`, and it's cheaper than the last price we alerted on
   for those exact dates, a notification is sent (Telegram and/or email).
4. Sent alerts are recorded in a small SQLite file so re-running the check
   doesn't spam you about the same fare -- only genuine price drops
   re-trigger.

Everything is pluggable: swap the price provider or add a new notifier
without touching the scheduling/dedup logic.

## Providers

- **`mock`** (default) -- deterministic fake prices, no network access
  needed. Good for trying the service out and for tests.
- **`renfe`** -- drives the real renfe.com search with Playwright and
  scrapes the cheapest fare shown. **Renfe has no public pricing API**, so
  this is a best-effort scraper (the same approach community tools like
  renfe-bot use) and can break when Renfe changes their site. See the
  docstring in `src/cheaptrains/providers/renfe.py` for setup and how to
  fix the CSS selectors if it stops working. If you have access to a
  licensed data source instead (e.g. a distributor/partner rail API),
  implement `PriceProvider` against that and point `provider:` at it --
  nothing else needs to change.

## Setup

```bash
pip install -r requirements.txt
# only if you're using provider: renfe
pip install playwright && playwright install chromium

cp config.example.yaml config.yaml   # already done in this repo; edit routes/thresholds
cp .env.example .env                 # fill in secrets, then `export $(cat .env | xargs)`
```

Edit `config.yaml`:

```yaml
provider: mock   # or "renfe"

weekend:
  outbound_days: [FRI, SAT]
  return_days: [SUN, MON]
  lookahead_weekends: 8

routes:
  - name: "Madrid -> Barcelona"
    origin: "Madrid"
    destination: "Barcelona"
    max_total_price: 60
    currency: EUR

notifications:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
```

`origin`/`destination` are plain city/station names as you'd type them
into renfe.com's search box (only relevant for the `renfe` provider; the
`mock` provider just uses them as opaque labels).

### Telegram setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram, `/newbot`,
   grab the token it gives you -> `TELEGRAM_BOT_TOKEN`.
2. Message your new bot once (anything), then visit
   `https://api.telegram.org/bot<token>/getUpdates` and read `chat.id`
   from the response -> `TELEGRAM_CHAT_ID`.

### Email setup

Use an app password (Gmail: Google Account -> Security -> App passwords),
not your real password, for `SMTP_PASSWORD`.

## Running

```bash
# one-off dry run, prints to stdout instead of sending notifications
python -m cheaptrains.cli --config config.yaml --dry-run

# real run, uses whatever notifiers are enabled in config.yaml
python -m cheaptrains.cli --config config.yaml
```

Each run checks all routes once and exits -- it's meant to be triggered on
a schedule (cron, systemd timer, or CI), not left running as a daemon.

## Running on a schedule for free via GitHub Actions

`.github/workflows/check-prices.yml` runs the checker every 3 hours using
GitHub's free scheduled Actions runners, so you don't need to host
anything. Set these repo secrets (Settings -> Secrets and variables ->
Actions):

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (if using Telegram)
- `SMTP_USERNAME`, `SMTP_PASSWORD` (if using email)

Alert history (`state.sqlite3`) is persisted between runs via
`actions/cache` so you don't get re-notified about a fare you've already
seen.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests run entirely against the `mock` provider -- no network access or
Renfe availability required.

## Design notes / limitations

- The outbound and return legs are priced independently (cheapest outbound
  day x cheapest return day), not as a single combined fare search. This
  is a reasonable proxy for "is this weekend cheap" but Renfe's actual
  round-trip pricing can differ slightly (e.g. return-fare promotions).
- `max_total_price` is a simple threshold, not a "% below average" signal.
  If you want the latter, `store.py` already keeps price history you could
  extend to compute a running baseline per route.
