# Surpay backend

FastAPI + SQLAlchemy. SQLite by default; set `SURPAY_DATABASE_URL` for Postgres
(`postgresql+psycopg://user:pass@host/db`).

| Env var | Purpose |
|---|---|
| `SURPAY_DATABASE_URL` | Database (default `sqlite:///./surpay.db`) |
| `SURPAY_SECRET_KEY` | Signs login tokens. **Required in production**: a long random string |
| `SURPAY_USER_AGENT` | How the scraper identifies itself to county sites |

## Commands

```sh
python -m surpay.cli sources            # list scrapers
python -m surpay.cli scrape --all       # run every scraper (cron this daily)
python -m surpay.cli import-file list.xlsx --state FL --county Lee --sale-type tax_sale \
    --name "Owner Name" --amount "Surplus" --reference "Case Number" \
    --address "Mailing Address" --sale-date "Sale Date"
python -m surpay.cli stats
python -m surpay.cli seed-demo          # fictional "Demo County" records
```

## API

| Method | Path | |
|---|---|---|
| GET | `/coverage` | Public totals: record count, dollars tracked, counties. No names |
| POST | `/auth/signup`, `/auth/login` | Returns a bearer token |
| GET/PUT | `/me` | Profile: name, other names, phone, previous addresses |
| GET | `/me/matches` | Records matching the signed-in user, with amount, fee and estimated net |
| POST/GET | `/me/claims` | Start a claim on one of *your* matches; list your claims |

Interactive docs at `/docs` while the server runs.

## How matching works

1. **Names** are normalized: `SMITH, JOHN A. JR` and `John Smith` both become `john a smith`.
   Suffixes, "et al", "estate of" and joint owners ("John & Mary Smith") are handled.
2. The user's first and last name must **both** fuzzy-match tokens in the owner field.
   Other names (maiden names) are tried too.
3. **Confidence:**
   - `strong`: name matches and a previous address the user entered matches the record's
     house number and street.
   - `likely`: a near-exact name match, but no address confirmation.
   - `possible`: a fuzzier name match.
4. Only records still on the county's list (`status = listed`) are shown. When a record drops
   off the list (usually paid out), the next scrape marks it `delisted`.

## Adding a county

1. Write `surpay/scrapers/<county>.py` with a `Source` subclass whose `fetch()` returns
   `RecordIn`s. See `adams_oh.py`: it finds the current document link on the county's page,
   downloads it, and parses PDF or Word.
2. Register it in `surpay/scrapers/__init__.py`.
3. Add a parser test with **made-up names** in the county's exact layout. Don't commit real
   county files; they contain people's names and home addresses.

Safety rails already in place:
- A scrape that returns zero records counts as a failure, so a changed page layout can't
  wipe out a county's records.
- Each record keeps the raw lines it was parsed from, for auditing.

Be a good citizen: run once a day, identify the bot honestly (`SURPAY_USER_AGENT`), and
follow each site's terms. Prefer official downloads over scraping when a county offers them.

## Before real users

- **Fee percentage** in `config.py` is a placeholder (15%). Set it per state from your
  attorney's memo, and never above the legal cap.
- **Identity verification** is not built yet. Today a claim is a request your team follows up
  on by hand. Add ID verification (e.g. Stripe Identity) before any money moves.
- **Rate limiting** on `/auth/*` and `/me/matches` (e.g. at the reverse proxy) to stop people
  using the app to look up other people.
- Run behind HTTPS. Keep `SURPAY_SECRET_KEY` secret.
