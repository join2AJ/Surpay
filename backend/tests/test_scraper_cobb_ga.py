"""Cobb County, GA parser, fed synthetic rows laid out like the real PDF. Names are made up."""

from datetime import date

from surpay.scrapers import cobb_ga


def words(*cells):
    return [(x + i * 12, w) for x, text in cells for i, w in enumerate(text.split())]


def test_cobb_rows():
    rows = [
        words((287, "Excess Funds")),
        words((41, "Date of Sale"), (101, "Purchaser"), (283, "Owner"), (485, "Parcel ID"), (580, "Excess Funds")),
        words((665, "Claim")),
        words((61, "9/1/2020"), (101, "BUYER 21 LLC"), (283, "Sample Jane Q"), (485, "17-0297-0-086-0"),
              (580, "$1,077.03"), (665, "Yes")),
        words((56, "11/4/2025"), (101, "OTHER BUYER"), (283, "EXAMPLE, JOHN"), (485, "16-0375-0-035-0"),
              (580, "$4,915.95"), (665, "No")),
        # long owner name runs into the parcel with no space
        [(56, "10/5/2021"), (101, "BIDDER,"), (139, "ONE"), (283, "ROE,"), (320, "B"), (338, "AKA"),
         (359, "ROE,"), (395, "BOBBY"), (440, "A/K/A"), (466, "RO19-0928-0-074-0"), (580, "$32,508.71"), (665, "Yes")],
        words((39, "(770) 528-8600"), (354, "www.cobbtax.gov")),
    ]
    recs = cobb_ga.parse_rows(rows, "u")
    assert [(r.reference, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("Parcel 17-0297-0-086-0", "Sample Jane Q", 107703, date(2020, 9, 1)),
        ("Parcel 16-0375-0-035-0", "EXAMPLE, JOHN", 491595, date(2025, 11, 4)),
        ("Parcel 19-0928-0-074-0", "ROE, B AKA ROE, BOBBY A/K/A RO", 3250871, date(2021, 10, 5)),
    ]
    assert recs[0].raw["pending"] == "Yes"
    assert len({r.source_key for r in recs}) == 3


def test_cobb_find_list_url_prefers_current_body_link():
    html = """<base href="https://www.cobbtax.gov/" />
    <a href="Excess Funds for web site Excel Template Seal_September.pdf">Excess Funds List</a>
    <a href="https://cms9files.revize.com/cobbcounty/Forms/Property%20Tax/ExcessFundsPacket.pdf">Request</a>
    <a href= "Excess Funds for web site Excel Template Seal_October.pdf?t=1">View Current Excess Funds List</a>"""
    assert cobb_ga.find_list_url(html) == (
        "https://www.cobbtax.gov/Excess%20Funds%20for%20web%20site%20Excel%20Template%20Seal_October.pdf?t=1")
