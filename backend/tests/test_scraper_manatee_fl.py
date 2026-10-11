"""Manatee County, FL unclaimed tax deed surplus table: synthetic page shaped like the real one (names made up)."""

from datetime import date

from surpay.scrapers import manatee_fl

PAGE = """
<table border="1"><thead>
<tr><td><strong>Case Number</strong></td><td><strong>Sale Date</strong></td><td><strong>Property Owner</strong></td>
<td><strong> </strong></td><td><strong>Surplus Funds</strong></td><td><strong> </strong></td>
<td><strong>1 Year from Sale Date</strong></td></tr></thead>
<tbody>
<tr><td>2025TD000103</td><td>9/15/2025</td><td>Jane Sample II</td><td></td><td>$98,991.49</td><td></td><td>9/15/2026</td></tr>
<tr><td>2025TD000130</td><td>10/27/2025</td><td>Example Holdings Inc., Example Inc.</td><td></td><td>$998.38</td><td></td>
<td>10/27/2026</td></tr>
<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</tbody></table>
"""


def test_parse_manatee_table():
    recs = manatee_fl.parse_html(PAGE, "u")
    assert [(r.source_key, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("2025TD000103", "Jane Sample II", 9899149, date(2025, 9, 15)),
        ("2025TD000130", "Example Holdings Inc., Example Inc.", 99838, date(2025, 10, 27)),
    ]
    assert recs[0].raw["one_year_from_sale"] == "9/15/2026"
    assert all(r.state == "FL" and r.county == "Manatee" for r in recs)
