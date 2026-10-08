# Deploying Surpay (no local server needed)

Everything runs in the cloud on free tiers:

| Piece | Where | Cost |
|---|---|---|
| API (FastAPI) | **Render** free web service | $0. Sleeps after 15 min idle; first request takes ~1 min to wake |
| Database | **Neon** free Postgres | $0. Render's free Postgres is deleted after 30 days, so it isn't used |
| Daily scraping + county list checks | **GitHub Actions** (`.github/workflows/scrape.yml`) | $0 |
| Landing page (optional) | **Netlify** or GitHub Pages | $0 |

Netlify can't run the Python API: it only hosts static sites and short serverless
functions. Use it for `index.html` only.

## 1. Database (Neon): 3 minutes

1. Sign up at https://neon.tech and create a project (any region near Render's, e.g. US East).
2. Copy the **connection string**. It looks like
   `postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`

## 2. API (Render): 5 minutes

1. Click **Deploy to Render**:
   https://render.com/deploy?repo=https://github.com/join2AJ/Surpay
2. Render reads `render.yaml` and asks for `SURPAY_DATABASE_URL`. Paste the Neon string.
3. Wait for the first deploy, then open `https://<your-service>.onrender.com/coverage`.
   You should see JSON with the counties tracked.

On every start, the server:
- creates its tables;
- loads the county database (`backend/data/county_sources.csv`);
- adds the demo records while `SURPAY_SEED_DEMO=true`;
- refreshes any county scraped more than 20 hours ago, in the background.

**The app expects `https://surpay-api.onrender.com/`.** If Render gave your service a
different address (the name may be taken), either:
- open the app → **Server settings** (bottom of the sign-in screen) → paste your URL, or
- rebuild the app with `./gradlew assembleDebug -PsurpayApiUrl=https://your-url.onrender.com/`.

## 3. Daily scraping (GitHub Actions): 2 minutes

Without this, data refreshes only when the server wakes up. In the GitHub repo, go to
**Settings → Secrets and variables → Actions**:

- Secret `SURPAY_DATABASE_URL`: the same Neon string
- Secret `SURPAY_SECRET_KEY`: copy it from Render (Environment tab)
- Variable `SURPAY_SCRAPE_ENABLED`: `true`

The "Daily scrape" workflow then runs every day. It scrapes all counties, and its log lists any
county whose published list changed. You can also run it by hand from the Actions tab.

## 4. Install the app

Download `app-debug.apk` from the latest CI run (Actions → CI → artifacts), or build it with
`cd android && ./gradlew assembleDebug`. On the phone, allow "install unknown apps" for
your browser or file manager.

To test, tap **Try the demo account (testing)** on the sign-in screen. It signs you in with
one tap as the fictional Jordan Testwell, with two demo matches. Testers share this account, and
it resets on every demo sign-in. It only works while `SURPAY_SEED_DEMO=true`.

If the app can't reach a Surpay server (for example, before you've deployed), the demo button
falls back to an **offline demo** that runs on the phone with the same made-up data. A yellow
banner says so. Real sign-up and sign-in always need the server.

## Before real users

- Set `SURPAY_SEED_DEMO=false` in Render. The fake Demo County disappears and the demo sign-in is switched off.
- Free Render sleeps. Upgrade to the $7/month Starter plan when people depend on it.
- Read "Before real users" in `backend/README.md`: fees, ID verification, rate limits.
