"""Taylor County, FL tax deed surplus table: synthetic page shaped like the real one (names made up)."""

from datetime import date

from surpay.scrapers import taylor_fl

PAGE = """
<p>Current Tax Deeds Surplus as of June 15, 2026.</p>
<table><thead><tr><th>TDA #</th><th>Owner&#8217;s Name</th><th>Parcel Number</th><th>Certificate #</th>
<th>Amount</th><th>Sale Date</th><th>Note</th></tr></thead>
<tbody>
<tr><td>22-034</td><td>Jane W Sample II</td><td>R00000-001</td><td>849 of 2019</td><td>$ 6,793.92</td>
<td>12/12/2022</td><td></td></tr>
<tr><td>23-009</td><td>John O Example Estate</td><td>R00000-002</td><td></td><td>$ 22,263.16</td><td>6/12/2023</td><td></td></tr>
<tr><td>25-036</td><td>Ann &amp; Bob Placeholder</td><td>R00000-003</td><td>1066 of 2023</td><td>$ 4 ,209.12</td>
<td>8/18/2025</td><td></td></tr>
</tbody></table>
"""


def test_parse_taylor_table():
    recs = taylor_fl.parse_html(PAGE, "u")
    assert [(r.source_key, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("22-034", "Jane W Sample II", 679392, date(2022, 12, 12)),
        ("23-009", "John O Example Estate", 2226316, date(2023, 6, 12)),
        ("25-036", "Ann & Bob Placeholder", 420912, date(2025, 8, 18)),
    ]
    assert recs[0].reference == "TDA 22-034, Parcel R00000-001"
    assert all(r.state == "FL" and r.county == "Taylor" for r in recs)
