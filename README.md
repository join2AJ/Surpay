# Surpay

Find and reclaim foreclosure and tax-sale surplus funds. Free search, contingency fee only.

## What's here

| Path | What |
|---|---|
| `index.html`, `styles.css`, `app.js` | Phase A landing page: hero, explainer, how it works, fees, FAQ, and an intake form |
| `docs/STRATEGY.md` | Market, compliance constraints, Phase A (concierge MVP) and Phase 2 (automation) roadmap |

## Run locally

It's a static site with no build step:

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

## Wiring up the intake form

Set `SURPAY_INTAKE_URL` at the top of `app.js` to any endpoint that accepts a JSON POST
(Formspree, a Google Apps Script web app, or your own API). Until it's set, submissions are
logged to the browser console only.

## Before going live

Read the **VERIFY** items in `docs/STRATEGY.md`, especially state fee caps, solicitation
disclosure rules, and attorney partnership terms. The trust badges and fee copy on the
landing page must match what's actually true in your launch state.
