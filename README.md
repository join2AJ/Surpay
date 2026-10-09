# Surpay

Find and reclaim foreclosure and tax-sale surplus funds. Free search, contingency fee only.

## What's here

| Path | What |
|---|---|
| `backend/` | Python API, county scrapers, database, name/address matching |
| `android/` | Android app (Kotlin + Jetpack Compose). Claimants: verify ID, list homes, see what they're owed and the law behind it, sign, follow their claim. Attorneys: apply, get verified, accept cases in their counties, report progress |
| `index.html`, `styles.css`, `app.js` | Marketing landing page with an intake form |
| `docs/STRATEGY.md` | Market, compliance constraints, and the roadmap |
| `docs/COUNTIES.md` | Which counties publish surplus lists, in what format, and which are worth tracking |
| `docs/DEPLOY.md` | Hosting on Render + Neon + GitHub Actions (no local server) |
| `docs/AUDIT.md` | October 2026 audit: security, product and legal findings and what was fixed |
| `docs/COMPLIANCE.md` | Encryption, audit trail, consent and data rights; DPDP / ISO 27001 / NIST CSF mapping |
| `backend/data/county_sources.csv` | The county database: all 3,143 US counties and their research status |

## How it fits together

```
county websites ──(scrapers, daily)──▶ database ◀──(matching)── API ◀──── Android app
   PDF / Word / CSV / XLSX                surplus_records           /me/matches
```

Scraping runs **on the server**, never on the phone. The app only ever sees the records that
match the signed-in person.

## Deploy (recommended)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/join2AJ/Surpay)

Full steps, including the free Neon database and daily scraping, are in [`docs/DEPLOY.md`](docs/DEPLOY.md).
The app connects to `https://surpay-api.onrender.com/` by default; change it in the app
under **Server settings**.

## Local development

```sh
# 1. Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m surpay.cli seed-demo        # fictional records for development
.venv/bin/python -m surpay.cli scrape --all     # real data: Adams OH, Dallas TX, Fort Bend TX, Gwinnett GA
.venv/bin/uvicorn surpay.api:app --host 0.0.0.0 --port 8000

# 2. Android app (needs the Android SDK; Android Studio works too)
cd android
./gradlew assembleDebug                         # app/build/outputs/apk/debug/app-debug.apk
```

To point the emulator at a local backend, build with
`./gradlew assembleDebug -PsurpayApiUrl=http://10.0.2.2:8000/` (10.0.2.2 is your computer as
seen from the emulator), or set it in the app under **Server settings**.

To try it, tap **Try the demo account (testing)** on the sign-in screen (needs
`SURPAY_SEED_DEMO=true` on the server). You'll see two demo matches.

## Tests

```sh
cd backend && .venv/bin/python -m pytest -q
cd android && ./gradlew testDebugUnitTest -Pe2eUrl=http://127.0.0.1:8000/ -Proborazzi.test.record=true
```

The Android end-to-end test drives the real app against a running backend with demo data
(sign up → add address → see matches → start claim) and saves screenshots to
`android/app/build/outputs/roborazzi/`. CI runs all of this and uploads the APK.

See `backend/README.md` for adding counties and deploying.
