# Surpay — Strategy & Roadmap

Surpay = **Surplus + Pay**. A consumer-facing service that finds people who are owed
foreclosure or tax-sale surplus funds and connects them with licensed attorneys to claim it,
for a contingency fee.

> ⚠️ Items marked **VERIFY** are claims taken from early research notes that have not been
> confirmed against current statutes. Confirm each with a licensed attorney in the target
> state before using it in contracts, marketing, or financial models.

---

## 1. The problem

When a property sells at a tax or mortgage foreclosure auction for more than the debt owed,
the excess (the "surplus" or "overage") belongs to the former owner, and then to junior
lienholders depending on state law. Counties hold the funds but do not search for owners.
If nobody files a valid claim in time, the money can revert to the government.

- **Tax-sale surplus:** *Tyler v. Hennepin County* (U.S. Supreme Court, May 2023) held that
  a government keeping more than the tax debt owed is an unconstitutional taking. States that
  previously kept tax-sale surplus have been changing their laws in response.
- **Mortgage foreclosure surplus:** the surplus has generally always belonged to the owner,
  after junior liens.

## 2. Competitive landscape (US)

| Segment | Who's there | Gap |
|---|---|---|
| State unclaimed property (dormant bank accounts, uncashed checks) | Free government search (MissingMoney.com), directory apps | Low value-add, and many states cap finder fees or ban them. **Not our focus.** |
| Foreclosure / tax surplus | Fragmented offline "asset recovery agencies" plus B2B tools (e.g. SurplusFunds Pro, Skipify.ai) | Cold calls and letters to people who just lost a home look like scams. Trust is low and conversions are poor. **No trusted consumer brand exists.** |

**Surpay's angle:** inbound trust instead of outbound spam. Run targeted ads ("Lost a home
to foreclosure in Florida 2020–2025? Check if you're owed a surplus."), let people check
themselves, be fully transparent about fees and the DIY option, and use tech to cut cost per claim.

## 3. Fees: a compliance constraint, not a pricing choice

Many states regulate what third parties may charge for surplus recovery. Some cap the fee,
some require specific contract language or waiting periods, and some restrict paid assignment
of claims. Rules differ between **mortgage foreclosure surplus** and **tax-deed surplus**,
even in the same state.

Figures from research notes, all **VERIFY**:

- Florida: a cap around 12–20% depending on surplus type and contract terms (see Fla. Stat.
  §45.032–45.033 for mortgage foreclosure surplus and §197.582 for tax-deed surplus).
- Maryland: ~10%.
- Illinois: ~15%.

The "30–40% industry standard" figure in early notes conflicts with these caps. **Model unit
economics at 15% or below** until the target state is confirmed.

**Action:** choose one launch state, get a written memo from a local attorney on the fee cap,
required contract disclosures, and notice and timing rules, then build the contract template
from that memo.

## 4. Phase A: Concierge MVP (prove unit economics manually)

Goal: recover real funds and get paid, with almost no tech.

1. **Pick one state** (FL, OH, or TX are good candidates for data availability), then 2–3 counties.
2. **Source leads after the auction, not before.** Ignore pre-foreclosure and missed payments.
   That's wholesaler territory and no surplus exists yet. Use the county clerk's published
   "Tax Deed Surplus List", "Excess Proceeds" or "Court Registry Funds" reports, which give
   name, case number, old address and amount.
3. **Partner with 1–2 local attorneys** who file the claims. Surpay handles intake, documents
   and status updates. The attorney handles legal work and holds funds in trust where required.
4. **Intake through the landing page** (`index.html`). A person runs the lookup and emails results.
5. **Measure:** leads → matches → signed agreements → filed → paid, plus days to payout,
   cost per acquisition, and fee per claim.

Exit criteria: at least 10 paid recoveries with positive contribution margin.

## 5. Phase 2: Tech platform (replace manual labor)

### 5.1 Surplus identification pipeline
Data tiers, cheapest and most scalable first:

1. **Auction vendor portals:** RealAuction, Bid4Assets and Grant Street Group host sales for
   hundreds of counties. Scrape or use pre-built Apify actors. Compute
   `surplus = winning_bid − judgment/debt − costs`, and flag records above a threshold such as $10k.
2. **County clerk and sheriff surplus lists:** HTML tables, PDFs and Excel files. Use an OCR
   pipeline (e.g. AWS Textract) for PDFs.
3. **Commercial data:** ATTOM, Bridge (Zillow), TaxLienSimple. Expensive but fast for coverage.
4. **Public records requests and bulk FTP:** for counties that publish nothing online.
   Automate the request emails and ingest the replies.

Respect each site's terms of service and robots rules. Prefer official exports where they exist.

### 5.2 Locating the owner
The foreclosed address is usually stale. Skip-tracing providers (LexisNexis, TLOxp and others)
return current contact data, **but**:

- Access requires a **permissible purpose** under GLBA and DPPA (and FCRA if data is used for
  eligibility decisions). Vendors will audit you.
- **TCPA:** no autodialed or prerecorded calls or texts to cell phones without prior express
  consent. Mail is the safest first touch.
- Contacting **relatives** to pass on messages raises privacy and harassment risk. Avoid it at launch.
- Many states regulate surplus-recovery solicitations (required disclosures, cooling-off
  periods, "you can claim this yourself for free" notices). **VERIFY per state.**

### 5.3 Outreach & intake
- Automated personalized letters (e.g. Lob.com) showing the case number and amount, pointing
  to Surpay's portal. Include the case number so recipients can verify it with the county
  themselves. That's the strongest trust signal.
- Identity verification (e.g. Stripe Identity), then e-sign the contingency agreement.

### 5.4 Legal handoff
On signature, bundle the contract, ID and case number and send them to the partner attorney's
intake through an API. Track status: filed → hearing → order → disbursed.

### 5.5 Getting paid
Disbursement mechanics vary: the clerk may issue a check to the claimant, to the attorney's
trust account, or split per the agreement. Paying out through the attorney's trust account is
the cleanest way to collect the fee. Design the contract around how the target county actually
disburses funds. **VERIFY.**

## 6. Landing page messaging principles

The biggest hurdle is that "free money" sounds too good to be true. The page should read like
a consumer-protection utility, not a pitch.

- Lead with the mechanism (why the money exists) and a worked example.
- State the fee, the cap, and "no fee if we don't recover" up front.
- **Say plainly that people can claim it themselves for free.** It's often legally required,
  and it builds more trust than any badge.
- Show the case number so people can verify it independently.
- Only show trust badges that are true on launch day. Don't claim attorney representation until
  engagement agreements are signed, and don't use "bank-level security" without a security
  posture to back it up.
- Avoid "Surpay is not a scam." Show evidence instead (FAQ, verifiable case numbers).
- Footer: not a law firm, not a government agency.

## 7. Later: India expansion (separate product)

Different asset classes and regulators: dormant bank deposits (RBI UDGAM), unclaimed
shares and dividends (IEPF, form IEPF-5), provident fund (EPFO), and insurance (IRDAI / Bima
Bharosa). Notes:

- Most of these portals already offer free self-service search. Value-add is paperwork,
  follow-up and form generation.
- Aadhaar e-KYC is restricted to authorised entities. DigiLocker consent flows are the
  practical route. Design for the DPDP Act from day one (consent, purpose limitation, minimisation).
- Collecting a contingency fee through e-NACH for an amount debited after disbursement needs
  careful mandate design and clear consent. **VERIFY** with an NPCI/RBI-compliant payments partner.
- "Blurred results" paywall: only show what can be verified, and never show a specific amount
  you have not confirmed.

Treat India as a separate go-to-market after the US model is proven.
