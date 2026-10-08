#!/usr/bin/env sh
# Production entry point (used by Render). Starts the API immediately and refreshes
# county data in the background so a cold start isn't slowed down by scraping.
set -e
python -m surpay.cli init-db
python -m surpay.cli sync-counties

if [ "${SURPAY_SEED_DEMO:-false}" = "true" ]; then
  python -m surpay.cli seed-demo
else
  python -m surpay.cli seed-demo --remove
fi

( python -m surpay.cli scrape --all --if-stale 20 || true ) &

exec uvicorn surpay.api:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
