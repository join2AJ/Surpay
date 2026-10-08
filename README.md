# Surpay

Find and reclaim foreclosure and tax-sale surplus funds. Free search, contingency fee only.

## What's here

| Path | What |
|---|---|
| `backend/` | Python API, county scrapers, database, name/address matching |
| `android/` | Android app (Kotlin + Jetpack Compose): sign up, add past addresses, see what you may be owed, start a claim |
| `index.html`, `styles.css`, `app.js` | Marketing landing page with an intake form |
| `docs/STRATEGY.md` | Market, compliance constraints, and the roadmap |

## How it fits together

```
county websites ──(scrapers, daily)──▶ database ◀──(matching)── API ◀──── Android app
   PDF / Word / CSV / XLSX                surplus_records           /me/matches
```

Scraping runs **on the server**, never on the phone. The app only ever sees the records that
match the signed-in person.

## Quick start

```sh
# 1. Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m surpay.cli seed-demo        # fictional records for development
.venv/bin/python -m surpay.cli scrape --all     # real county data (Adams County, OH so far)
.venv/bin/uvicorn surpay.api:app --host 0.0.0.0 --port 8000

# 2. Android app (needs the Android SDK; Android Studio works too)
cd android
./gradlew assembleDebug                         # app/build/outputs/apk/debug/app-debug.apk
```

The debug app talks to `http://10.0.2.2:8000/`, which is your computer as seen from the
Android emulator. To use a phone or a deployed server, build with
`./gradlew assembleDebug -PsurpayApiUrl=https://your-server/`. Production must use HTTPS.

To try it, sign up as **Jordan Testwell** and add the address **412 Maple Ridge Rd, OH**.
You'll see two demo matches.

## Tests

```sh
cd backend && .venv/bin/python -m pytest -q
cd android && ./gradlew testDebugUnitTest -Pe2eUrl=http://127.0.0.1:8000/ -Proborazzi.test.record=true
```

The Android end-to-end test drives the real app against a running backend with demo data
(sign up → add address → see matches → start claim) and saves screenshots to
`android/app/build/outputs/roborazzi/`. CI runs all of this and uploads the APK.

See `backend/README.md` for adding counties and deploying.
