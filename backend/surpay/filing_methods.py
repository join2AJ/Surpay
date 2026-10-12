"""How a surplus claim is filed in each county we cover: e-filing in court or an administrative claim
by mail, email or in person; the forms; notarization; who may file. Researched 2026-10-12 from the
counties' own pages (sources listed). Re-check before relying on any entry, and phone the office
where an entry says "unknown".

"court" means the claim is a petition or motion in a court case (the attorney e-files it);
"administrative" means a claim form sent to the office holding the money.
"""

STATE_EFILING = {
    "FL": {"portal": "Florida Courts E-Filing Portal", "url": "https://www.myflcourtaccess.com", "mandatory_for_attorneys": True,
           "notes": "Tax-deed surplus claims go to the Clerk by mail or email, not through the Portal."},
    "GA": {"portal": "PeachCourt or eFileGA (by county)", "url": "https://www.peachcourt.com", "mandatory_for_attorneys": True,
           "notes": "Excess-funds claims go to the Tax Commissioner; the portal is used only if the funds are interpleaded."},
    "TX": {"portal": "eFileTexas", "url": "https://www.efiletexas.gov", "mandatory_for_attorneys": True,
           "notes": "The petition is e-filed in the original tax suit's cause number (Tax Code § 34.04)."},
    "OH": {"portal": "County e-filing (Cuyahoga Clerk e-Filing; Montgomery efiling.mcohio.org)",
           "url": "https://cuyahogacounty.gov/coc/services/e-filing", "mandatory_for_attorneys": True,
           "notes": "Foreclosure excess is claimed by motion in the case; tax surplus by application to the auditor."},
    "AZ": {"portal": "AZTurboCourt / eFileAZ", "url": "https://www.azturbocourt.gov", "mandatory_for_attorneys": True,
           "notes": "The application is filed in the trustee's existing superior court case."},
    "SC": {"portal": "SC Judicial Branch E-Filing", "url": "https://www.sccourts.org/efiling/", "mandatory_for_attorneys": True,
           "notes": "Overage claims themselves are paper forms to the Delinquent Tax Collector."},
    "CA": {"portal": "None (administrative claim)", "url": "https://www.sco.ca.gov/Files-ARD-Tax-Info/Tax-Collector-Ref-Man/sco8-21.pdf",
           "mandatory_for_attorneys": False, "notes": "Claims go by mail or in person to the county tax collector."},
}

_TX_COURT = {"kind": "court", "method": "E-file (eFileTexas)", "url": "https://www.efiletexas.gov", "forms": [],
             "notarized": "Unknown (an assignment needs a sworn statement)", "fee": "County civil filing fee",
             "who_may_file": "Owner, lienholder or qualifying assignee (Tax Code § 34.04)",
             "processing": "Hearing after at least 20 days' notice, then a court order"}

FILING_METHODS: dict[tuple[str, str], dict] = {
    ("FL", "Collier"): {
        "kind": "administrative", "method": "Mail", "where": "Collier Clerk, Recording Dept, Tax Deeds",
        "address": "Attn: Tax Deeds, 3315 Tamiami Trail East, Ste. 102, Naples, FL 34112-5324",
        "url": "https://www.collierclerk.com/tax-deed-sales/tax-deed-surplus/",
        "forms": [{"name": "Surplus Claim Form", "url": "https://collierclerk.com/wp-content/uploads/SURPLUS-CLAIM-FORM-1.pdf"},
                  {"name": "Instructions", "url": "https://collierclerk.com/wp-content/uploads/SURPLUS-INSTRUCTIONS-1.pdf"}],
        "notarized": "Yes", "fee": "None", "who_may_file": "Owner, mortgagor or lienholder",
        "processing": "Not stated", "notes": "Notarized claim with photo ID, W-9 and, for estates, probate documents."},
    ("FL", "Volusia"): {
        "kind": "administrative", "method": "Unknown: call the Tax Deed Department", "where": "Volusia Clerk, Tax Deed Department",
        "address": "P.O. Box 6043, DeLand, FL 32721; (386) 736-5919", "url": "https://www.clerk.org/tax-deeds.aspx",
        "forms": [], "notarized": "Unknown", "fee": "The clerk deducts a small fee from the surplus",
        "who_may_file": "Unknown", "processing": "Unknown", "notes": "No published claim form; phone before filing."},
    ("FL", "Santa Rosa"): {
        "kind": "administrative", "method": "Mail", "where": "Santa Rosa County Clerk of Court",
        "address": "6495 Caroline St., Ste. A, Milton, FL 32570", "url": "https://santarosaclerk.com/?p=91",
        "forms": [{"name": "Claim to Surplus Proceeds of a Tax Deed Sale",
                   "url": "http://santarosaclerk.com/uploads/2025/11/surplus-formwip_tagged.pdf"}],
        "notarized": "Yes", "fee": "Unknown", "who_may_file": "Lienholder or titleholder", "processing": "Not stated",
        "notes": "Mail only."},
    ("FL", "Marion"): {
        "kind": "administrative", "method": "Mail", "where": "Marion County Clerk & Comptroller, Attn: Tax Deeds",
        "address": "P.O. Box 1030, Ocala, FL 34478-1030",
        "url": "https://www.marioncountyclerk.org/departments/records-recording/tax-deeds-and-lands-available-for-taxes/unclaimed-funds/",
        "forms": [{"name": "Tax Deeds Surplus Claim Form", "url": "https://www.marioncountyclerk.org/uploads/2024/12/Surplus-claim-form-PDF.pdf"}],
        "notarized": "Yes (in person or online notarization)", "fee": "None stated",
        "who_may_file": "Lienholder or titleholder", "processing": "Not stated",
        "notes": "Photo ID and proof of address; funds go to the state one year after the sale."},
    ("FL", "Manatee"): {
        "kind": "administrative", "method": "Mail or email", "where": "Manatee County Clerk, Tax Deeds",
        "address": "P.O. Box 25400, Bradenton, FL 34206; taxdeeds@manateeclerk.com",
        "url": "https://www.manateeclerk.com/departments/tax-deeds/",
        "forms": [{"name": "Statement of Claim for Surplus Proceeds", "url": "https://www.manateeclerk.com/media/1924/surplus-blank-form.pdf"}],
        "notarized": "Yes", "fee": "Unknown", "who_may_file": "Lienholder or titleholder", "processing": "Unknown", "notes": ""},
    ("FL", "Taylor"): {
        "kind": "administrative", "method": "Mail", "where": "Taylor County Clerk of Court, Tax Deed Dept.",
        "address": "P.O. Box 620, Perry, FL 32348", "url": "https://taylorclerk.com/departments/tax-deeds-surplus/",
        "forms": [{"name": "Claim to Surplus Proceeds", "url": "https://taylorclerk.com/uploads/2025/06/Claim-To-Surplus-REVISED-10-25-23_tagged.pdf"},
                  {"name": "Checklist", "url": "https://taylorclerk.com/uploads/2026/02/Checklist-Surplus-Claim_ada.pdf"}],
        "notarized": "Yes", "fee": "None stated",
        "who_may_file": "Owner or lienholder; a third party needs a power of attorney and an assignment",
        "processing": "Not stated", "notes": "Photo ID and W-9; heirs need probate documents."},
    ("GA", "Gwinnett"): {
        "kind": "administrative", "method": "Mail", "where": "Gwinnett Tax Commissioner, Property Tax",
        "address": "P.O. Box 372, Lawrenceville, GA 30046", "url": "https://gwinnetttaxcommissioner.com/property-tax/tax-sale-excess-funds",
        "forms": [{"name": "Excess Funds Claim Packet", "url": "https://www.gwinnetttaxcommissioner.com/documents/d/egov/excessfundspacket?download=true"}],
        "notarized": "Yes", "fee": "None stated",
        "who_may_file": "Owner or lienholder; an attorney may represent them, but the owner signs the affidavit",
        "processing": "May go to legal review or interpleader", "notes": "Incomplete or altered forms are rejected."},
    ("GA", "DeKalb"): {
        "kind": "administrative", "method": "Mail or in person", "where": "DeKalb Tax Commissioner, Delinquent Collections Claims",
        "address": "4380 Memorial Dr., Suite 100, Decatur, GA 30032", "url": "https://dekalbtaxga.gov/property-tax/delinquent-taxes/",
        "forms": [{"name": "Claim Form for Excess Bid", "url": "https://dekalbtaxga.gov/wp-content/uploads/EXCESS-FUNDS-CLAIM-FORM-FILLABLE-2021_0.pdf"}],
        "notarized": "Yes", "fee": "None stated",
        "who_may_file": "The entitled person or their Georgia-licensed attorney; no powers of attorney",
        "processing": "May be interpleaded to Superior Court", "notes": ""},
    ("GA", "Clayton"): {
        "kind": "administrative", "method": "Unknown: likely mail or in person", "where": "Clayton County Tax Commissioner",
        "address": "121 S. McDonough St., Annex 3, Jonesboro, GA 30236",
        "url": "https://publicaccess.claytoncountyga.gov/content/home_commissioner.htm",
        "forms": [{"name": "Official Claim for Excess Funds", "url": "https://publicaccess.claytoncountyga.gov/content/PDF/OfficialClaimforExcessFund.pdf"}],
        "notarized": "Unknown", "fee": "Unknown", "who_may_file": "Owner, lienholder, or estate executor/administrator",
        "processing": "Unknown", "notes": "Owner claims need the deed and a certificate of title dated within 60 days."},
    ("GA", "Cobb"): {
        "kind": "court", "method": "Email the request; then Superior Court interpleader",
        "where": "Cobb Tax Commissioner Levy Dept, then Cobb Superior Court", "address": "levy@cobbtax.gov; P.O. Box 100127, Marietta, GA 30061",
        "url": "https://www.cobbtax.gov/property/delinquent_taxes/index.php",
        "forms": [{"name": "Excess Funds Request Packet", "url": "https://cms9files.revize.com/cobbcounty/Forms/Property%20Tax/ExcessFundsPacket.pdf"}],
        "notarized": "No", "fee": "None to request; court costs come out of the funds",
        "who_may_file": "Owner or lienholder; an attorney may appear at the hearing; no recovery firms or powers of attorney",
        "processing": "Acknowledged in about 72 hours, then the court timeline", "notes": "Every claim is interpleaded."},
    ("GA", "Forsyth"): {
        "kind": "administrative", "method": "Mail (signed, notarized letter)", "where": "Forsyth County Tax Commissioner",
        "address": "1092 Tribble Gap Rd., Cumming, GA 30040", "url": "https://forsythcountytax.com/tax-sales-excess-funds/",
        "forms": [], "notarized": "Yes", "fee": "None",
        "who_may_file": "Owner or priority lienholder; paid only to the owner",
        "processing": "Reviewed by counsel", "notes": "No county form; a certified title report is strongly encouraged."},
    ("GA", "Chatham"): {
        "kind": "administrative", "method": "Mail or email", "where": "Chatham County Tax Commissioner, Excess Funds",
        "address": "P.O. Box 8092, Savannah, GA 31412; ExcessFunds@chathamcounty.org", "url": "https://tax.chathamcountyga.gov/ExcessFunds",
        "forms": [{"name": "Excess Funds Request Form",
                   "url": "https://cms.chathamcountyga.gov/api/assets/taxcommissioner/f8fe12cc-9f51-4848-9183-7a73ebc40835?download=0"}],
        "notarized": "A notarized release is needed before payment", "fee": "None stated",
        "who_may_file": "Owner, heir or lienholder; no recovery firms or powers of attorney",
        "processing": "About 3 to 4 weeks", "notes": "Disputed claims go to Superior Court."},
    ("TX", "Dallas"): {**_TX_COURT, "where": "Petition in the original tax suit, Dallas County district court",
                       "address": "Dallas County District Clerk, 600 Commerce St., Suite 103, Dallas, TX 75202",
                       "notes": "File within 2 years of the sale under the tax suit's cause number."},
    ("TX", "Fort Bend"): {**_TX_COURT, "where": "Petition in the original tax suit, Fort Bend County district court",
                          "address": "Fort Bend County District Clerk", "notes": ""},
    ("TX", "Denton"): {**_TX_COURT, "where": "Petition in the original tax suit, Denton County district court",
                       "address": "Denton County District Clerk", "notes": ""},
    ("TX", "Ector"): {**_TX_COURT, "where": "Petition in the original tax suit, Ector County district court",
                      "address": "Ector County District Clerk", "notes": "The list shows expected disbursement dates."},
    ("TX", "Wise"): {**_TX_COURT, "where": "Petition in the original tax suit, 271st District Court",
                     "address": "Wise County District Clerk; districtclerk@co.wise.tx.us", "notes": ""},
    ("OH", "Adams"): {
        "kind": "administrative", "method": "Email or mail", "where": "Adams County Auditor",
        "address": "110 West Main St., Room 104, West Union, OH 45693",
        "url": "https://adamsoh-auditor.schneidergis.com/media/13898/instructions-surplus-tax-sales-funds.pdf",
        "forms": [{"name": "Instructions and application",
                   "url": "https://adamsoh-auditor.schneidergis.com/media/13898/instructions-surplus-tax-sales-funds.pdf"}],
        "notarized": "Yes", "fee": "None stated",
        "who_may_file": "The owner, executor, administrator, guardian or financial power of attorney; no professional finders",
        "processing": "Not stated", "notes": "ID, W-9 and proof of ownership or residence."},
    ("OH", "Cuyahoga"): {
        "kind": "court", "method": "E-file (attorneys)", "where": "Motion to distribute funds in the foreclosure case, Cuyahoga Common Pleas",
        "address": "Clerk of Courts, Justice Center, 1200 Ontario St., Cleveland, OH 44113; (216) 443-7982",
        "url": "https://cuyahogacounty.gov/coc/services/e-filing",
        "forms": [{"name": "Motion to Distribute Funds (owner)", "url": "https://cp.cuyahogacounty.gov/media/2593/motion-to-distribute-funds-property-owner.pdf"},
                  {"name": "Motion of Heir to Intervene", "url": "https://cp.cuyahogacounty.gov/media/2581/motion-of-heir-of-property-owner-to-intervene-to-receive-funds-of-sheriffs-sale.pdf"}],
        "notarized": "No (certificate of service)", "fee": "Unknown",
        "who_may_file": "Owner at the sale date, lienholder, or an heir who intervenes",
        "processing": "No ruling before the 14-day response period",
        "notes": "Tax-foreclosure funds held by the Treasurer: claim process by phone (216) 443-7982."},
    ("OH", "Montgomery"): {
        "kind": "court", "method": "E-file", "where": "Motion in the foreclosure case, Montgomery Common Pleas",
        "address": "Montgomery County Clerk of Courts, Dayton, OH", "url": "https://efiling.mcohio.org",
        "forms": [], "notarized": "Unknown", "fee": "Unknown", "who_may_file": "The party entitled, by motion",
        "processing": "Unknown", "notes": "All General Division civil filings must be e-filed."},
    ("AZ", "Mohave"): {
        "kind": "court", "method": "E-file or in person, plus certified-mail notice",
        "where": "Mohave County Superior Court, in the trustee's existing case",
        "address": "Clerk of Superior Court, 415 E. Spring St., Kingman, AZ 86401",
        "url": "https://www.mohavecourts.com/sites/default/files/Mohave%20Courts/Forms%20and%20Form%20Kits/Docs/CVProcHowFileReleaseExcessProceedsSale2024.pdf",
        "forms": [{"name": "Application for Release of Excess Proceeds by Owner",
                   "url": "https://www.mohavecourts.az.gov/sites/default/files/Mohave%20Courts/Forms%20and%20Form%20Kits/Docs/CVApplReleaseExcessProceeds-sc.pdf"},
                  {"name": "Affidavit of Mailing",
                   "url": "https://www.mohavecourts.az.gov/sites/default/files/Mohave%20Courts/Forms%20and%20Form%20Kits/Docs/CVAffOfMailApplRelExcessProceedsSale-sc.pdf"}],
        "notarized": "The affidavit of mailing is sworn", "fee": "Court appearance fee",
        "who_may_file": "Former owner or their attorney; lienholders per A.R.S. § 33-812",
        "processing": "30-day objection window, then the Treasurer pays on a certified order and W-9", "notes": ""},
    ("SC", "Calhoun"): {
        "kind": "administrative", "method": "Unknown: likely mail or in person", "where": "Calhoun County Delinquent Tax Collector",
        "address": "102 Courthouse Dr., Suite 103, St. Matthews, SC 29135", "url": "https://calhouncounty.sc.gov/departments/tax-collector",
        "forms": [{"name": "Agreement & Release (overage claim)",
                   "url": "https://calhouncounty.sc.gov/sites/calhouncounty/files/Documents/Calhoun%20County/Departments/Tax%20Collector/CCTC-Tax_Sale_Overage_Claim_Form_v2.pdf"}],
        "notarized": "Yes", "fee": "None", "who_may_file": "Every owner of record must sign; no payments to third parties",
        "processing": "Payable 90 days after the tax deed unless a court claim is filed",
        "notes": "Deed or probate record, Social Security card and photo ID of every claimant."},
    ("CA", "Modoc"): {
        "kind": "administrative", "method": "Mail", "where": "Modoc County Tax Collector",
        "address": "204 South Court St., Alturas, CA 96101", "url": "https://www.countyofmodoc.gov/DocumentCenter/View/632/Claim-form-for-Excess-Proceeds-PDF",
        "forms": [{"name": "Claim for Excess Proceeds", "url": "https://www.countyofmodoc.gov/DocumentCenter/View/632/Claim-form-for-Excess-Proceeds-PDF"}],
        "notarized": "Photo ID copy or notarization", "fee": "None stated",
        "who_may_file": "Lienholders, then title holders; agents must prove they disclosed the amount (R&T § 4675)",
        "processing": "After the 1-year claim window; check about 90 days after approval", "notes": ""},
}


def method_for(state: str, county: str) -> dict:
    """The county's filing method, else what's known for the state."""
    key = (state.upper(), county.removesuffix(" County").strip())
    found = FILING_METHODS.get(key)
    efile = STATE_EFILING.get(state.upper())
    if found is None:
        return {"kind": "unknown", "method": "Check with the office holding the funds", "where": "", "address": "",
                "url": "", "forms": [], "notarized": "Unknown", "fee": "Unknown", "who_may_file": "Unknown",
                "processing": "Unknown", "notes": "", "state_efiling": efile, "researched": False}
    return {**found, "state_efiling": efile, "researched": True}
