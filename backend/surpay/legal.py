"""Why the money belongs to the claimant, what they must prove, the deadline, what happens if it
is missed, and (for attorneys) how a claim is filed, by state.

General information for claimants, not legal advice. Sources are listed per state; have an
attorney in each state confirm before launch, and update when statutes change.
"""

from datetime import date, timedelta

GENERAL_NOTE = (
    "This is general information, not legal advice. Requirements differ by county and can change; "
    "the partner attorney confirms what your county needs before filing."
)

_COMMON_PROOF = [
    "A government photo ID (driver’s license, state ID or passport)",
    "Proof you owned the property when it was sold: the deed, a property tax bill, or the county "
    "record showing your name",
    "Proof you lived at or received mail at the property: utility bills, bank statements, "
    "insurance or tax records",
    "An IRS Form W-9 with your Social Security number, so the county can issue the payment",
]

_HEIR_PROOF = (
    "If the owner has died: a death certificate and proof you are an heir or the estate’s "
    "representative (letters of administration, or an affidavit of heirship where accepted)"
)

LEGAL: dict[str, dict] = {
    "TX": {
        "law": "Texas Tax Code §§ 34.03 and 34.04",
        "right": "When property sells at a tax sale for more than the taxes, costs and liens owed, the "
                 "district clerk holds the excess in the court registry. The former owner (and anyone "
                 "with a recorded interest, such as a lienholder) may ask the court to release it.",
        "process": "A petition is filed in the same court that ordered the sale, usually under the "
                   "original case number. The judge decides who is entitled and signs an order telling "
                   "the clerk to pay.",
        "deadline": "The petition must be filed before the 2nd anniversary of the sale date.",
        "deadline_years": 2,
        "if_missed": "If nobody files in time, the court releases the money to the taxing units that were "
                     "owed the taxes (county, city, school district). The former owner's right to it "
                     "generally ends.",
        "sources": ["https://codes.findlaw.com/tx/tax-code/tax-sect-34-04/"],
    },
    "GA": {
        "law": "O.C.G.A. § 48-4-5",
        "right": "Excess funds from a tax sale belong to the record owner at the time of sale, then to "
                 "holders of security deeds and other recorded interests, in order of priority.",
        "process": "A notarized claim is filed with the officer who holds the funds (tax commissioner or "
                   "sheriff). If several people claim, the county may ask the superior court to decide "
                   "(interpleader). Many Georgia counties accept claims only from the owner or a "
                   "Georgia-licensed attorney, which is why our partner attorney files.",
        "deadline": "Claims are accepted until the funds are awarded, for up to 5 years after the sale.",
        "deadline_years": 5,
        "if_missed": "Money still unclaimed after 5 years is turned over to the Georgia Department of "
                     "Revenue as unclaimed property. A claim there may still be possible, but it is slower "
                     "and needs the same proof.",
        "sources": ["https://www.gwinnetttaxcommissioner.com/property-tax/tax-sale-excess-funds",
                    "https://law.justia.com/codes/georgia/2006/48/48-4-5.html"],
    },
    "OH": {
        "law": "Ohio Revised Code § 5721.20",
        "right": "Money left after a tax foreclosure sale pays the taxes, costs and liens belongs to the "
                 "former owner. The county holds it in the owner’s name.",
        "process": "A signed, notarized application is sent to the county auditor or treasurer with "
                   "supporting documents. The county decides whether the proof is sufficient. Some "
                   "Ohio counties do not accept applications from professional finders, only from the "
                   "owner, their legal representative or attorney.",
        "deadline": "The county pays the owner on request within 3 years of receiving the funds.",
        "deadline_years": 3,
        "if_missed": "After 3 years the county moves the money into its own funds (in some counties, the "
                     "land bank). It is then usually no longer recoverable.",
        "sources": ["https://codes.ohio.gov/ohio-revised-code/section-5721.20",
                    "https://adamsoh-auditor.schneidergis.com/media/13898/instructions-surplus-tax-sales-funds.pdf"],
    },
    "OH:mortgage_foreclosure": {
        "law": "Ohio Revised Code § 2329.44",
        "right": "When a sheriff's sale in a foreclosure brings more than the judgment, costs and liens, the "
                 "clerk of courts holds the excess for the former owner (the judgment debtor) and anyone else "
                 "the court finds entitled to it.",
        "process": "A motion to release the excess funds is filed in the foreclosure case at the Court of "
                   "Common Pleas, with proof of identity and ownership. The court orders the clerk to pay.",
        "deadline": "There is no fixed claim period for foreclosure surplus, but money left with the clerk is "
                    "eventually handled as unclaimed court funds. Claim as soon as possible.",
        "deadline_years": None,
        "if_missed": "Excess the owner doesn't collect is treated as unclaimed money held by the court and later "
                     "the county or state. It can usually still be claimed, but it takes longer and needs the "
                     "same proof.",
        "sources": ["https://codes.ohio.gov/ohio-revised-code/section-2329.44",
                    "https://codes.ohio.gov/ohio-revised-code/section-2335.34"],
    },
    "FL": {
        "law": "Fla. Stat. § 197.582 (tax deed surplus) and §§ 45.032-45.033 (mortgage foreclosure surplus)",
        "right": "When a tax deed sale brings more than the opening bid, the clerk pays government liens and holds "
                 "the rest for those who had an interest in the property: mortgage and lien holders in order of "
                 "priority, then the former owner.",
        "process": "The clerk mails a notice of surplus funds. The claimant files a notarized claim to receive "
                   "surplus proceeds with the clerk. If claims conflict, the clerk asks the circuit court to "
                   "decide (interpleader); otherwise the clerk pays by priority.",
        "deadline": "Lienholders must claim within 120 days of the clerk's notice. The owner should claim within "
                    "about one year: after that the clerk sends unclaimed surplus to the state.",
        "deadline_years": 1,
        "if_missed": "The clerk reports the money to the Florida Department of Financial Services as unclaimed "
                     "property. The former owner (or an heir) can still claim it from the state at "
                     "FLTreasureHunt.gov, but it takes longer and needs the same proof.",
        "sources": ["https://www.flsenate.gov/Laws/Statutes/2026/197.582",
                    "https://www.flsenate.gov/Laws/Statutes/2026/45.032",
                    "https://www.flsenate.gov/Laws/Statutes/2026/45.033"],
    },
    "AZ": {
        "law": "Arizona Revised Statutes § 33-812",
        "right": "When a trustee's sale under a deed of trust brings more than the debt, costs and junior liens, "
                 "the rest belongs to the former owner (the trustor). The trustee may deposit it with the county "
                 "treasurer, who holds it until the superior court orders it paid.",
        "process": "An application for distribution is filed in the court case the trustee started, and mailed "
                   "to the treasurer and every interested party. Others have 45 days to respond; then the court "
                   "orders payment. A finder's agreement must be written and notarized, can't be signed within "
                   "30 days after the sale, and a fee over $2,500 (not counting attorney fees and costs) is "
                   "presumed unreasonable.",
        "deadline": "Apply within 2 years of the date the money was deposited with the county treasurer.",
        "deadline_years": 2,
        "if_missed": "After 2 years the money is presumed abandoned. Amounts over $50 go to the Arizona "
                     "Department of Revenue as unclaimed property, where a slower claim is still possible; "
                     "smaller amounts go to the county and can't be claimed.",
        "sources": ["https://www.azleg.gov/ars/33/00812.htm",
                    "https://www.mohave.gov/departments/treasurer/general-use/excess-proceeds-list/"],
    },
    "SC": {
        "law": "S.C. Code § 12-51-130",
        "right": "When a tax sale brings more than the taxes, penalties and costs, the overage belongs to the "
                 "owner of record just before the 12-month redemption period ended.",
        "process": "After the tax deed is issued, the owner files a signed (often notarized) claim form with the "
                   "county's delinquent tax collector, with ID and proof of ownership. The overage is paid about "
                   "90 days after the tax deed unless someone else goes to court over it. The county charges no fee.",
        "deadline": "Claim within 5 years of the tax sale.",
        "deadline_years": 5,
        "if_missed": "Overage not claimed within 5 years goes to the county's general fund and can no longer be "
                     "claimed.",
        "sources": ["https://www.scstatehouse.gov/code/t12c051.php",
                    "https://calhouncounty.sc.gov/departments/tax-collector"],
    },
    "CA": {
        "law": "California Revenue and Taxation Code §§ 4674-4676",
        "right": "Money left from a tax-defaulted property sale goes first to lienholders of record in order of "
                 "priority, then to whoever held title before the tax deed was recorded: the former owner or "
                 "their heirs.",
        "process": "A written claim (usually form SCO 8-21) with proof of interest is filed with the county tax "
                   "collector. The board of supervisors decides and pays no sooner than one year after the deed "
                   "is recorded. Anyone filing for the owner must show the owner was told the amount and that "
                   "they can claim directly with the county for free.",
        "deadline": "File within one year after the tax deed to the buyer is recorded.",
        "deadline_years": 1,
        "if_missed": "Excess proceeds not claimed in time go to the county general fund, and the former owner's "
                     "right to them ends.",
        "sources": ["https://california.public.law/codes/ca_rev_and_tax_code_section_4675",
                    "https://www.sco.ca.gov/Files-ARD-Tax-Info/Tax-Collector-Ref-Man/sco8-21.pdf"],
    },
}

_DEFAULT = {
    "law": "State surplus-funds statute; Tyler v. Hennepin County, 598 U.S. 631 (2023)",
    "right": "The U.S. Supreme Court held that a government may not keep more than the tax debt it is "
             "owed; the surplus belongs to the former owner.",
    "process": "A claim is filed with the county or court holding the funds, with proof of identity "
               "and ownership.",
    "deadline": "Deadlines vary by state, from a few months to several years. Claim as early as possible.",
    "deadline_years": None,
    "if_missed": "Most states then pass unclaimed surplus to the county, the taxing units or the state's "
                 "unclaimed property program. After that it may be much harder, or impossible, to recover.",
    "sources": ["https://www.supremecourt.gov/opinions/22pdf/22-166_668c.pdf"],
}


FACILITATOR = (
    "Surpay is a technology platform, not a law firm. It connects you with an independent licensed "
    "attorney and tracks your case. The claim is made by you, through the attorney you choose, who is "
    "responsible for the legal work. Surpay does not give legal advice and is not responsible for the "
    "outcome of any claim."
)

FAMILY_PROOF = {
    "heir": [
        "The death certificate of the former owner",
        "Proof of your relationship: birth certificate(s) linking you to them, or a marriage certificate",
        "Proof you are entitled to inherit: the will and probate letters, letters of administration, or an "
        "affidavit of heirship / small-estate affidavit where the county accepts one",
        "If there are other heirs, their details; the county may require all heirs to sign or be notified",
    ],
    "power_of_attorney": [
        "A signed, notarized durable power of attorney that covers financial claims",
        "The owner's photo ID",
        "Note: some counties (for example Gwinnett County, GA) do not accept claims made under a power of "
        "attorney; the owner may need to sign the claim personally",
    ],
    "guardian": [
        "The court order appointing you guardian or conservator (letters of guardianship)",
        "The owner's photo ID or other proof of identity",
    ],
}


def rules(state: str, sale_type: str = "") -> dict:
    """The state's rules, or its separate rules for this kind of sale where they differ
    (for example "OH:mortgage_foreclosure")."""
    return LEGAL.get(f"{state.upper()}:{sale_type}") or LEGAL.get(state.upper(), _DEFAULT)


def deadline_for(state: str, sale_date: date | None, sale_type: str = "") -> date | None:
    """Approximate last day to claim, counted from the sale date. None if unknown."""
    years = rules(state, sale_type).get("deadline_years")
    if not years or sale_date is None:
        return None
    if years != int(years):  # e.g. 0.5 for six months
        return sale_date + timedelta(days=round(years * 365.25))
    years = int(years)
    try:
        return sale_date.replace(year=sale_date.year + years)
    except ValueError:  # Feb 29
        return sale_date.replace(year=sale_date.year + years, day=28)


# Days before the deadline by which the attorney should have the claim filed: time to collect
# documents, get the affidavit notarized and for the clerk to docket it.
FILE_BY_MARGIN_DAYS = 45
URGENT_DAYS = 60
SOON_DAYS = 180
MET_STATUSES = ("filed", "hearing_pending", "approved", "paid")

_COLORS = {"safe": "#15803d", "soon": "#b45309", "urgent": "#b91c1c", "expired": "#6b7280",
           "met": "#1d4ed8", "unknown": "#64748b"}


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def today() -> date:
    """Today's date; tests pin it so deadlines counted from fixed sale dates don't drift."""
    return date.today()


def deadline_info(state: str, sale_date: date | None, claim_status: str | None = None,
                  as_of: date | None = None, sale_type: str = "") -> dict:
    """Where a record stands against its legal deadline, for every screen that shows it.

    urgency: safe (> 6 months left), soon (2-6 months), urgent (60 days or less), expired,
    met (the claim was filed in time) or unknown (no sale date or no fixed statutory period).
    """
    as_of = as_of or today()
    info = rules(state, sale_type)
    deadline = deadline_for(state, sale_date, sale_type)
    base = {"deadline": deadline, "sale_date": sale_date, "file_by": None, "days_left": None,
            "total_days": None, "elapsed_pct": None, "rule": info["deadline"], "if_missed": info["if_missed"],
            "can_claim": True}
    if claim_status in MET_STATUSES:
        return {**base, "urgency": "met", "color": _COLORS["met"], "label": "Filed in time",
                "message": "Your claim was filed before the deadline, so the deadline no longer applies. "
                           "The court or county now decides."}
    if deadline is None:
        return {**base, "urgency": "unknown", "color": _COLORS["unknown"], "label": "Claim as soon as possible",
                "message": "We can't work out an exact deadline for this one. " + info["deadline"]}
    days_left = (deadline - as_of).days
    total = max((deadline - sale_date).days, 1)
    file_by = deadline - timedelta(days=FILE_BY_MARGIN_DAYS)
    out = {**base, "file_by": file_by, "days_left": days_left, "total_days": total,
           "elapsed_pct": max(0, min(100, round(100 * (total - days_left) / total)))}
    if days_left < 0:
        return {**out, "urgency": "expired", "color": _COLORS["expired"], "can_claim": False,
                "label": f"Deadline passed {deadline:%b %-d, %Y}",
                "message": f"The deadline to claim this money passed {_plural(-days_left, 'day')} ago. "
                           + info["if_missed"]}
    if days_left <= URGENT_DAYS:
        urgency = "urgent"
        message = (f"Only {_plural(days_left, 'day')} left. The claim must be filed by {deadline:%B %-d, %Y}. "
                   "Act today: verify your ID and sign so the attorney can file in time.")
    elif days_left <= SOON_DAYS:
        urgency = "soon"
        message = (f"{_plural(days_left, 'day')} left. Start now so the attorney can file by "
                   f"{file_by:%B %-d, %Y}, comfortably before the {deadline:%B %-d, %Y} deadline.")
    else:
        urgency = "safe"
        message = (f"{_plural(days_left, 'day')} left to claim, until {deadline:%B %-d, %Y}. "
                   "Plenty of time, but money is paid in the order claims are proven, so don't wait.")
    label = "Last day to claim" if days_left == 0 else f"{_plural(days_left, 'day')} left"
    return {**out, "urgency": urgency, "color": _COLORS[urgency], "label": label, "message": message}


def record_deadline(r, claim_status: str | None = None, as_of: date | None = None) -> dict:
    """deadline_info for a SurplusRecord."""
    return deadline_info(r.state, r.sale_date, claim_status, as_of=as_of, sale_type=r.sale_type)


def legal_basis(state: str, sale_type: str = "") -> dict:
    info = {k: v for k, v in rules(state, sale_type).items() if k != "deadline_years"}
    return {
        **info,
        "proof": [*_COMMON_PROOF, _HEIR_PROOF],
        "family_proof": FAMILY_PROOF,
        "note": GENERAL_NOTE,
        "facilitator": FACILITATOR,
        "constitutional": "Tyler v. Hennepin County (U.S. Supreme Court, 2023): keeping surplus beyond "
                          "the debt owed is an unconstitutional taking.",
    }


# --- For partner attorneys: how a claim is filed, step by step ---------------------------------

FILING: dict[str, dict] = {
    "TX": {
        "where": "District court that ordered the tax sale (district clerk's registry)",
        "online": "Online. Attorneys must e-file civil filings in Texas district courts through eFileTexas.",
        "steps": [
            "Confirm the cause number and the excess-proceeds balance with the district clerk.",
            "Prepare a Petition for Withdrawal of Excess Proceeds under Tax Code § 34.04, filed in the "
            "original tax suit.",
            "Attach the claimant's sworn affidavit of identity and ownership, a copy of the deed or "
            "other ownership proof, and the claimant's photo ID. For heirs, add the death certificate "
            "and heirship evidence.",
            "E-file through eFileTexas and request a hearing date.",
            "Serve a copy on every party to the underlying tax suit at least 20 days before the "
            "hearing (Tax Code § 34.04(b); TRCP 21a).",
            "Attend the hearing (some courts rule on submission). Obtain the signed order directing "
            "the clerk to pay.",
            "Give the district clerk the signed order and the payee's W-9. The clerk issues the check.",
            "Update the case in Surpay at each step: Filed, Waiting for court, Approved, Money released.",
        ],
        "print": ["Claimant affidavit for notarized signature (remote online notarization is "
                  "permitted in Texas)", "W-9 for the district clerk"],
    },
    "GA": {
        "where": "The officer holding the funds: county tax commissioner or sheriff",
        "online": "Mostly offline. Most Georgia counties require the county's paper claim form, "
                  "notarized, delivered by mail or in person.",
        "steps": [
            "Download the county's excess-funds claim form (for example from the tax commissioner's "
            "website) and confirm the amount still held.",
            "Have the claimant sign the claim form before a notary.",
            "Attach the claimant's photo ID, proof of ownership at the time of the sale and, for "
            "heirs, the death certificate and estate documents.",
            "Deliver the packet by mail or in person and get a dated receipt.",
            "If more than one person claims the funds, the county may file an interpleader in "
            "superior court (O.C.G.A. § 48-4-5); appear for the claimant.",
            "On approval the county issues the check. Record each step in Surpay.",
        ],
        "print": ["County claim form (notarized, wet signature)", "Copies of ID and ownership documents",
                  "W-9"],
    },
    "OH": {
        "where": "Tax foreclosure surplus: county auditor or treasurer (R.C. 5721.20). Sheriff's sale "
                 "surplus in a court foreclosure: clerk of courts, by motion in the case (R.C. 2329.44).",
        "online": "Mixed. County auditor applications are usually paper and notarized, sent by mail. "
                  "Motions in a foreclosure case can be e-filed where the court of common pleas offers "
                  "e-filing.",
        "steps": [
            "Confirm which office holds the money and the amount (auditor, treasurer or clerk of courts).",
            "Prepare the county's application for excess funds, or a motion for distribution of excess "
            "proceeds in the foreclosure case.",
            "Have the claimant sign the notarized affidavit; attach photo ID, deed or tax bill, and a W-9. "
            "For heirs, add the death certificate and probate or heirship documents.",
            "File: mail or deliver to the auditor or treasurer, or e-file the motion with the clerk.",
            "Respond to any request for more documents; attend the hearing if the court sets one.",
            "On approval the county or clerk issues payment. Record each step in Surpay.",
        ],
        "print": ["County application or affidavit (notarized)", "W-9", "Copies of ID and ownership "
                  "documents"],
    },
}

_FILING_DEFAULT = {
    "where": "The county office or court holding the surplus funds",
    "online": "Varies by county. Court filings are usually e-filed; county claim forms are often paper "
              "and notarized.",
    "steps": [
        "Confirm with the county which office holds the funds, the amount, and its claim procedure.",
        "Prepare the claim (county form or court motion) under the state's surplus statute.",
        "Have the claimant sign any affidavit before a notary; attach ID, ownership proof and a W-9.",
        "File it, serve anyone the law requires, and attend any hearing.",
        "On approval, collect the payment for the claimant. Record each step in Surpay.",
    ],
    "print": ["Notarized claimant affidavit", "W-9", "Copies of ID and ownership documents"],
}


def filing_guide(state: str) -> dict:
    return FILING.get(state.upper(), _FILING_DEFAULT)
