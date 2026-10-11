"""Forsyth County, GA parser, fed a synthetic page shaped like the real listing. Names are made up."""

from datetime import date

from surpay.scrapers import forsyth_ga

PAGE = """<html><body><h1>Excess Funds Listing</h1><figure><table><tbody>
<tr><td>DATE SOLD</td><td>PARCEL ID</td><td>DEFENDANT IN FIFA</td><td>DEFENDANT IN FIFA ADDRESS</td>
<td>PROPERTY ADDRESS</td><td>PURCHASE PRICE</td><td>TOTAL AMOUNT DUE</td><td>EXCESS FUNDS</td></tr>
<tr><td>6/1/2021</td><td>225&nbsp;&nbsp; 190</td><td>JANE Q SAMPLE ESTATE</td>
<td>APT 2 100 EXAMPLE BLVD NORCROSS GA 30071</td><td>1 OAK RD</td><td>$21,000.00</td><td>$1,638.28</td><td>$19,361.72</td></tr>
<tr><td>6/6/2023</td><td>225   190</td><td>JOHN EXAMPLE</td><td>2 ELM ST DACULA GA 30019</td><td>1 OAK RD</td>
<td>$2,500.00</td><td>$535.65</td><td>$1,964.35</td></tr>
<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</tbody></table></figure><p>Please direct all claim correspondence to the Tax Commissioner</p></body></html>"""


def test_forsyth_table():
    recs = forsyth_ga.parse_table(PAGE, "u")
    assert [(r.reference, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("Parcel 225 190", "JANE Q SAMPLE ESTATE", 1936172, date(2021, 6, 1)),
        ("Parcel 225 190", "JOHN EXAMPLE", 196435, date(2023, 6, 6)),
    ]
    assert recs[0].owner_address == "APT 2 100 EXAMPLE BLVD NORCROSS GA 30071"
    assert len({r.source_key for r in recs}) == 2  # same parcel sold twice
    assert all(r.state == "GA" and r.county == "Forsyth" for r in recs)


def test_forsyth_find_list_url():
    html = '<a href="https://forsythcountytax.com/excess-funds-listing-2/" data-type="page">here</a>'
    assert forsyth_ga.find_list_url(html) == "https://forsythcountytax.com/excess-funds-listing-2/"
