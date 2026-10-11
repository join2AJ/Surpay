#!/usr/bin/env sh
# Production entry point (used by Render). Starts the API immediately and refreshes
# county data in the background so a cold start isn't slowed down by scraping.
set -e
python -m surpay.cli init-db
python -m surpay.cli sync-counties
# Anything still encrypted under an older key (e.g. before SURPAY_ENCRYPTION_KEY was set) moves to the current one.
python -m surpay.cli rotate-keys

if [ "${SURPAY_SEED_DEMO:-false}" = "true" ]; then
  python -m surpay.cli seed-demo
else
  python -m surpay.cli seed-demo --remove
fi

# Housekeeping runs after the scrape: expired offers, retention, and deadline reminders (each sent once).
( python -m surpay.cli scrape --all --if-stale 20 || true; python -m surpay.cli purge || true ) &

exec uvicorn surpay.api:app --host 0.0.0.0 --port "${PORT:-8000}"
