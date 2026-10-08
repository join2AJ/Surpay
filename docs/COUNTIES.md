# County research: who publishes surplus lists, and how

*Researched 2026-10-08. The database is `backend/data/county_sources.csv` (every county) and
`backend/data/state_rules.csv` (state rules). Edit `county_research.csv` and rebuild with
`python scripts/build_county_registry.py`.*

## How many counties?

**3,143** counties and county equivalents in the 50 states + DC (US Census 2020 list).
Texas alone has 254 and Georgia 159. Each one handles surplus its own way. There is no
national database, which is the gap Surpay fills.

## How they publish

| Style | What it looks like | Effort to track | Examples |
|---|---|---|---|
| **PDF table** on a stable or predictable URL | Spreadsheet printed to PDF | **Easy.** Scraper in a day | Dallas TX (monthly), Fort Bend TX, Gwinnett GA |
| **Word/PDF list** linked from a page | Typed list, link changes on update | **Easy.** Find the link each run | Adams OH |
| **HTML page/table** | List on the website | Easy–medium | Cuyahoga OH, Will IL |
| **Annual or periodic notices** | Newspaper-style legal notices, yearly PDFs | Medium. Manual import | Alachua FL (July), Lake OH |
| **Per-claim board/court documents** | Amounts appear only in hearing packets | Hard | Riverside CA |
| **On request only** | Email or open-records request; sometimes a fee | Hard. Manual, then `import-file` | Harris TX, Tarrant TX, Fulton GA |
| **Blocks bots** | Site returns 403 to scripts | Medium. Needs a browser-based scraper or manual download | Baltimore Co. MD, Madera CA, Laurens SC |

CSV and Excel files are rare: most counties print their spreadsheet to PDF. For any file
someone downloads or receives by email, `python -m surpay.cli import-file` loads CSV/XLSX.

## Which are easiest, and also legal to monetize

Easy to scrape is not enough. Some states **ban fees** or **ban commercial use** of the lists:

| State | Rule found | Impact |
|---|---|---|
| **Colorado** | "No one may charge a fee to help you collect" (Denver, Weld). Funds go to the state after 6 months | ❌ Don't target |
| **Washington** | King County lists may not be used commercially (RCW 42.56.070) | ❌ Don't scrape |
| **Georgia** | Gwinnett deals only with the owner or **the owner's attorney**, not recovery firms | ⚠️ OK only via partner attorneys |
| **Indiana** | Locator fees capped at **10%** | ⚠️ Thin margin |
| **Michigan** | Claim notice due **before** the auction (by July 1) | ⚠️ Different product: pre-sale alerts |
| **Texas, Florida, Ohio, California** | Active surplus markets with lists published. Fee caps **not yet verified** | ✅ Best first targets |

## Status today

| Status | Counties |
|---|---|
| Scraper live | 4: Adams OH, Dallas TX, Fort Bend TX, Gwinnett GA (~350 records, ~$8.6M on 2026-10-08) |
| List online, scraper not built | 14 |
| Request only | 4 |
| Do not use | 3 (King WA, Denver CO, Arapahoe CO) |
| Other (notices only, closed, special process) | 3 |
| **Not researched yet** | **3,115** |

## Suggested order

1. **Texas.** 254 counties. Large counties publish PDFs (Dallas, Fort Bend; check Bexar,
   Travis, Collin, Denton). Request Harris and Tarrant lists by email.
2. **Florida.** 67 clerks, most with a "Tax Deed Surplus" page. Claims are time-limited
   (120 days after notice), so fast alerts are valuable.
3. **Ohio and Georgia.** Many auditor, clerk and tax commissioner lists.
4. Work down the most populous counties first: a few hundred large counties hold most of
   the population, and so most of the surplus.

For each new county: add a row to `county_research.csv`. If it's an easy PDF or HTML list,
copy the closest existing scraper (`dallas_tx.py` for PDF tables, `adams_oh.py` for
link-discovery documents). The daily `check-sources` job flags lists that change, so you know
when to look.
