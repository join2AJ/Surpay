"""Clayton County, GA parser. Rows are in PDF content-stream order, as pdf_stream_rows() yields them.
Names are made up."""

from datetime import date

from surpay.scrapers import clayton_ga


def words(*cells):
    return [(x + i * 12, w) for x, text in cells for i, w in enumerate(text.split())]


def test_clayton_rows():
    rows = [
        words((297, "CLAYTON COUNTY TAX COMMISSIONER")),
        words((370, "JUNE 2026")),
        # the "$" comes after the figure in the content stream
        words((57, "JANE Q SAMPLE"), (346, "05015 017010"), (530, "1,914.41"), (472, "$"), (615, "02/02/21")),
        words((57, "EXAMPLE, JOHN"), (346, "05213 214013 A07"), (523, "44,134.74"), (472, "$"), (615, "11/05/24")),
        # a long owner name overprints the parcel column but is a separate run, before the parcel
        [(57, "ANN"), (100, "PLACEHOLDER"), (190, "&"), (200, "BOB"), (271, "(ROE,"), (322, "TESTER"),
         (360, "EXAMPLE)"), (346, "06062C"), (395, "B006"), (472, "$"), (530, "2,521.93"), (615, "02/02/21")],
        words((347, "Total Excess Funds"), (472, "$"), (506, "2,545,971.54")),
        words((55, "Page 1")),
    ]
    recs = clayton_ga.parse_rows(rows, "u")
    assert [(r.reference, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("Parcel 05015 017010", "JANE Q SAMPLE", 191441, date(2021, 2, 2)),
        ("Parcel 05213 214013 A07", "EXAMPLE, JOHN", 4413474, date(2024, 11, 5)),
        ("Parcel 06062C B006", "ANN PLACEHOLDER & BOB (ROE, TESTER EXAMPLE)", 252193, date(2021, 2, 2)),
    ]
    assert len({r.source_key for r in recs}) == 3
    assert all(r.state == "GA" and r.county == "Clayton" for r in recs)


def test_clayton_find_list_url():
    html = ('<a href="../content/PDF/OfficialClaimforExcessFund.pdf"><u>Office Claim for Excess Funds</u></a>'
            '<a href="../content/PDF/DQ759GA.pdf"><u>Excess Funds Listing</u></a>')
    assert clayton_ga.find_list_url(html) == "https://publicaccess.claytoncountyga.gov/content/PDF/DQ759GA.pdf"
