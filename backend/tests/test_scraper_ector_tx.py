"""Ector County, TX parser, fed text lines laid out like the real registry report. Names are made up."""

from surpay.scrapers import ector_tx

LINES = """
       Registry Accounts with Expected Disbursement  Dates
       Date Range: 01/01/2023 to 01/31/2030 Sorted by: Expected Final Disbursement Date, Case Number
           70th District Court
       Case Number Registry Account Type On Behalf Of  Bank & Investment Type Account#  Disburse Current Balance
       A-21-02-0147-CV Tax - Excess Proceeds SAMPLE, JANE ERIN                          2/4/2027    23,001.84
       Printed on 10/05/2026 at 3:52 PM                                                       Page 1 of 6
           County Court at Law
       A-10,927-T  Tax - Excess Proceeds EXAMPLE, JOHN                                  2/2/2023     847.82
       C-23-199-T  Tax - Excess Proceeds Tester , Ann P.                                2/4/2027    32,572.52
       C24159T     Tax - Excess Proceeds Placeholder Farms, LLC                         2/3/2028    93,329.06
       Grand Total: 4                                                                            150,000.00
""".splitlines()


def test_ector_lines():
    recs = ector_tx.parse_lines(LINES, "u")
    assert [(r.reference, r.owner_name, r.amount_cents) for r in recs] == [
        ("Case A-21-02-0147-CV", "SAMPLE, JANE ERIN", 2300184),
        ("Case A-10,927-T", "EXAMPLE, JOHN", 84782),
        ("Case C-23-199-T", "Tester, Ann P.", 3257252),
        ("Case C24159T", "Placeholder Farms, LLC", 9332906),
    ]
    assert recs[0].raw["court"] == "70th District Court"
    assert recs[1].raw["court"] == "County Court at Law"
    assert recs[2].raw["expected_disbursement"] == "2027-02-04"
    assert len({r.source_key for r in recs}) == 4


def test_ector_find_list_url():
    html = '<a href="/DocumentCenter/View/3352" target="_blank">List of Excess Proceeds (PDF)</a>'
    assert ector_tx.find_list_url(html) == "https://www.ectorcountytx.gov/DocumentCenter/View/3352"
