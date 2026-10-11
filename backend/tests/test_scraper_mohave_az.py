"""Mohave County, AZ Treasurer excess proceeds page: a synthetic copy of its table (made-up names)."""

from datetime import date

import pytest

from surpay.scrapers.mohave_az import parse_page

PAGE = """
<html><body><div>
<p>Data provided as of 10/2/2026</p>
<p>Listed below are the Excess Proceeds on properties sold for more than the amount owed ...</p>
<table>
<tr><th>Case Number</th><th>Trustor</th><th>Deposit Date</th><th>Deposit Amount</th><th>Current Balance</th></tr>
<tr><td>2023-01682</td><td>JANE R. SAMPLE</td><td>12/8/2023</td><td>$54,834.27</td><td>$54,834.27</td></tr>
<tr><td>2023-01814</td><td>PAULA EXAMPLE</td><td>12/14/2023</td><td>$47,157.28</td><td>$126.00</td></tr>
<tr><td>2024-00118</td><td>FRANK T. PLACEHOLDER AND CINDY M. PLACEHOLDER</td><td>3/6/2024</td><td>$13,965.42</td><td>$0.00</td></tr>
</table></div></body></html>
"""


def test_parse_mohave_page():
    recs = parse_page(PAGE, "u")
    assert [(r.source_key, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("2023-01682", "JANE R. SAMPLE", 5483427, date(2023, 12, 8)),
        ("2023-01814", "PAULA EXAMPLE", 12600, date(2023, 12, 14)),  # current balance, not the deposit
    ]
    assert recs[1].raw["deposit_amount"] == "$47,157.28"
    assert recs[0].raw["list_as_of"] == "2026-10-02"
    assert all(r.state == "AZ" and r.county == "Mohave" and r.sale_type == "mortgage_foreclosure" for r in recs)


def test_missing_table_is_an_error():
    with pytest.raises(ValueError, match="layout may have changed"):
        parse_page("<html><table><tr><td>x</td></tr></table></html>", "u")
