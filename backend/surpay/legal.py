"""Why the money belongs to the claimant, what they must prove, and the deadline, by state.

General information for claimants, not legal advice. Sources are listed per state; have an
attorney in each state confirm before launch, and update when statutes change.
"""

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
        "deadline": "The petition must be filed before the 2nd anniversary of the sale date. After that, "
                    "the money goes to the taxing units.",
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
        "deadline": "Claims are accepted until the funds are awarded. Money unclaimed 5 years after the "
                    "sale is paid over to the state.",
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
        "deadline": "The county pays the owner on demand within 3 years of receiving the funds. After "
                    "that they are transferred (for example, to the county land bank).",
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
    "sources": ["https://www.supremecourt.gov/opinions/22pdf/22-166_668c.pdf"],
}


def legal_basis(state: str) -> dict:
    info = LEGAL.get(state.upper(), _DEFAULT)
    return {
        **info,
        "proof": [*_COMMON_PROOF, _HEIR_PROOF],
        "note": GENERAL_NOTE,
        "constitutional": "Tyler v. Hennepin County (U.S. Supreme Court, 2023): keeping surplus beyond "
                          "the debt owed is an unconstitutional taking.",
    }
