"""Why the money belongs to the claimant, what they must prove, the deadline, what happens if it
is missed, and (for attorneys) how a claim is filed, by state.

General information for claimants, not legal advice. Sources are listed per state; have an
attorney in each state confirm before launch, and update when statutes change.
"""

from datetime import date

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


def deadline_for(state: str, sale_date: date | None) -> date | None:
    """Approximate last day to claim, counted from the sale date. None if unknown."""
    years = LEGAL.get(state.upper(), _DEFAULT).get("deadline_years")
    if not years or sale_date is None:
        return None
    try:
        return sale_date.replace(year=sale_date.year + years)
    except ValueError:  # Feb 29
        return sale_date.replace(year=sale_date.year + years, day=28)


def legal_basis(state: str) -> dict:
    info = {k: v for k, v in LEGAL.get(state.upper(), _DEFAULT).items() if k != "deadline_years"}
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
