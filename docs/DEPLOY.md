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

1. Sign up at https://neon.tech and create a project in region **AWS US East 2 (Ohio)**, the
   same region `render.yaml` uses for the API.
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

## 5. Reviewing claims (staff)

Everyone verifies **before** they can see anything. Sign-up is: account → verify ID (details,
ID photo, selfie) → list every home they've owned → wait for review. Until you approve the ID,
they see only *how many* possible records exist, never amounts or details. Searches use the
name on their ID (plus other names declared at submission), and names lock once submitted, so
nobody, including brokers, can look up someone else. After approval, starting a claim goes
straight to e-signing the agreement. Open **`https://<your-service>.onrender.com/admin`** on your phone and
enter the admin token (Render → surpay-api → **Environment** → `SURPAY_ADMIN_TOKEN`, tap the eye
icon to reveal it). For each claim you can:

- **Pending ID reviews** at the top: each person's ID photos, selfie, details, the homes they
  listed and how many records match them;
- see the county record next to the homes the person listed and the ID they submitted;
- **Approve ID**, which unlocks their results (and moves any signed claims to "Identity verified"), or **Reject ID** with a
  note they'll see in the app, asking them to upload again;
- move the claim to **filed → approved → paid** (or denied / withdrawn) as the attorney reports
  progress. Each change updates the timeline and estimated dates the person sees in the app.

### Partner attorneys

Attorneys tap **"Lawyer? Join our attorney network"** on the sign-in screen, create an account
and apply. They give bar state and number, firm, office, the counties they'll take cases in, and
a photo of their bar card, and accept the partner terms (shown with the per-case fee).

On `/admin`, **Attorney applications** come first. Check the license is active on the state
bar's official directory (there's a search link), then **Approve attorney**. Any verified client
claims already waiting in their counties are offered to them immediately.

How cases flow:
1. A claimant's ID is approved and they sign the agreement, so the claim is ready.
2. It's offered to the approved attorney licensed in that state who serves that county and has
   the fewest open cases.
3. The attorney sees county, amount and reference only, and accepts or declines. A decline passes
   it to the next attorney; anyone who declined never gets it again. If nobody serves the county,
   it waits: recruit an attorney there, or use **Offer to attorney** / **Reassign** on the claim.
4. After accepting, the attorney sees the client's details, ID photos, signed agreement, county
   record and the legal basis, and reports **filed → approved → paid** (or denied). Each update
   appears on the client's timeline, and the client sees their attorney's name and firm.
5. When the case closes (paid or denied), the per-case fee shows **due**. Pay the attorney, then
   press **Mark attorney paid**.

6. After accepting, the attorney writes to the client first in the app's messages. Phone numbers, emails and
   links are blocked so the conversation stays in the app. The case screen shows a step-by-step filing guide
   for the state and a printable claim packet (PDF: cover sheet, draft affidavit with notary block, signed
   agreement, documents). The attorney reports **filed → waiting for county/court → approved → money released**;
   the client gets a phone notification at each step.

The fee per case is `SURPAY_ATTORNEY_FEE_CENTS` (default 50000 = $500), a placeholder you set
from your attorney agreements. Per-state amounts can be set in `backend/surpay/config.py`.

### Admin demo (testing)

While `SURPAY_SEED_DEMO=true`, the app's welcome screen has **Claimant**, **Attorney** and **Admin** demo
buttons. **Admin** opens this dashboard with a 2-hour pass that only sees and acts on demo data: Demo County
claims, the fictional demo accounts, and attorneys who serve only Demo County. Real people's records, ID photos
and fee settings stay out of reach, so the button is safe to leave in test builds. Real staff use the
"Surpay staff? Open the review dashboard" link and the real `SURPAY_ADMIN_TOKEN`.

### Fees, family claims, audit (the dropdown at the top of `/admin`)

- **Fee rules**: the client's fee is the average of the county's usual rate and the rate for the amount
  (bands), capped at the legal maximum you enter for the state or county. Users only see the result. You can
  set a different fee for one case before the client signs.
- **Reviews** also lists **family claims**: someone claiming for a relative who died (as heir) or under a
  power of attorney. Check the death certificate and the documents linking them before approving; only then
  do that relative's records appear.
- **Audit trail**: every action with time, IP and device, and a check that no record was altered. Each
  signed claim has an evidence certificate (typed name vs ID, drawn signature, document fingerprint).

See `docs/COMPLIANCE.md` for security and privacy (DPDP, ISO 27001, NIST CSF).

ID photos are encrypted in the database with `SURPAY_ENCRYPTION_KEY`. **Never change or delete
that key** once IDs are stored, or they can't be opened again.

## Before real users

- Set `SURPAY_SEED_DEMO=false` in Render. The fake Demo County disappears and the demo sign-in is switched off.
- Free Render sleeps. Upgrade to the $7/month Starter plan when people depend on it.
- Read "Before real users" in `backend/README.md`: fees, ID verification, rate limits.
- **Ethics review of the attorney arrangement.** In most states lawyers may not share fees
  with non-lawyers or pay for referrals (ABA Model Rules 5.4 and 7.2), and the attorney must
  keep independent judgment. Have ethics counsel in each state approve how Surpay's contingency
  fee and the per-case attorney payment are structured, and the partner terms in
  `backend/surpay/attorney_api.py`, before the first real case.
- Have an attorney replace the agreement template in `backend/surpay/claims.py` (`agreement_text`)
  for each state you operate in. The current text is marked "pending attorney review".
