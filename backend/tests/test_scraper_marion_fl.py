"""Marion County, FL tax deeds surplus report: synthetic rows laid out like the real PDF (names made up)."""

from surpay.scrapers import marion_fl


def words(*cells):
    row = []
    for x, text in cells:
        for i, w in enumerate(text.split()):
            row.append((x + i * 20, w))
    return row


def num(sale, cert, parcel, amount, owner=None):
    cells = [(41, sale), (161, cert), (219, parcel), (293, amount)]
    if owner:
        cells.append((348, owner))
    return words(*cells)


def name(text):
    return words((348, text))


ROWS = [
    words((211, "Tax Deeds Surplus Funds Report")),
    words((41, "Sale number"), (160, "Tax number"), (218, "Parcel number"), (281, "Current balance"),
          (348, "Assessed_name")),
    num("295336", "83442014", "1814-026-017", "5,778.69", "JANE SAMPLE"),
    # Centred cells: 3 lines -> one above, one on the row, one below.
    name("ANN EXAMPLE AND BOB"),
    num("295681", "71682019", "1808-017-033", "17,199.33", "EXAMPLE AND CAROL"),
    name("EXAMPLE"),
    # 2 lines -> one above, one below, none on the row.
    name("DAVID PLACEHOLDER AND"),
    num("295860", "248852019", "9012-0185-12", "11,965.08"),
    name("ERIN PLACEHOLDER"),
    num("297006 B", "191622021", "5069-394-000", "5,003.67", "FRANK SAMPLE"),
    words((41, "Grand Total:"), (284, "$39,946.77")),
]


def test_parse_marion_rows():
    recs = marion_fl.parse_rows(ROWS, "u")
    assert [(r.source_key, r.owner_name, r.amount_cents) for r in recs] == [
        ("295336", "JANE SAMPLE", 577869),
        ("295681", "ANN EXAMPLE AND BOB EXAMPLE AND CAROL EXAMPLE", 1719933),
        ("295860", "DAVID PLACEHOLDER AND ERIN PLACEHOLDER", 1196508),
        ("297006B", "FRANK SAMPLE", 500367),
    ]
    assert recs[0].reference == "Tax Deed Sale 295336, Certificate 83442014, Parcel 1814-026-017"
    assert all(r.state == "FL" and r.county == "Marion" and r.sale_date is None for r in recs)


def test_find_marion_list_url():
    html = """
      <a href="https://www.marioncountyclerk.org/uploads/2024/12/Surplus-claim-form-PDF.pdf">Claim form</a>
      <a href="https://www.marioncountyclerk.org/uploads/2026/10/Copy-of-Tax-Deeds-Surplus-Funds-2026-10-02.pdf">List</a>
    """
    assert marion_fl.find_list_url(html).endswith("/2026/10/Copy-of-Tax-Deeds-Surplus-Funds-2026-10-02.pdf")
