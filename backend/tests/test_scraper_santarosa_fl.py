"""Santa Rosa County, FL tax deed surplus list: synthetic rows laid out like the real PDF (names made up)."""

from datetime import date

from surpay.scrapers import santarosa_fl


def words(*cells):
    row = []
    for x, text in cells:
        for i, w in enumerate(text.split()):
            row.append((x + i * 12, w))
    return row


ROWS = [
    words((56, "FILE# SURPLUS"), (115, "SALE DATE"), (151, "PAYEE"), (272, "ADDRESS"), (407, "CITY"),
          (484, "ST"), (545, "ZIP")),
    words((62, "2020192"), (83, "$"), (91, "17,743.83"), (121, "11/2/2020"), (151, "SAMPLE HOLDINGS INC"),
          (271, "C/O JANE SAMPLE")),
    words((271, "100 TEST DR"), (407, "MILTON"), (484, "FL"), (539, "32583")),
    # A long amount pushes the sale date left, right up against it.
    words((62, "2025127"), (83, "$"), (88.6, "187,210.63"), (118.2, "10/27/2025"), (151, "JOHN EXAMPLE"),
          (271, "1 MAIN ST"), (407, "PACE"), (484, "FL"), (528, "32571-0000")),
    words((151, "MARY EXAMPLE")),
    # One file split between two heirs.
    words((62, "2024289"), (83, "$"), (94, "1"), (96, ",732.89"), (123, "6/9/2025"), (151, "ANN PLACEHOLDER"),
          (271, "2 OAK WAY"), (407, "PENSACOLA"), (484, "FL"), (539, "32504")),
    words((62, "2024289"), (83, "$"), (94, "1"), (96, ",732.88"), (123, "6/9/2025"), (151, "BOB PLACEHOLDER"),
          (271, "2 OAK WAY"), (407, "PENSACOLA"), (484, "FL"), (539, "32504")),
]


def test_parse_santarosa_rows():
    recs = santarosa_fl.parse_rows(ROWS, "u")
    assert [(r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("SAMPLE HOLDINGS INC", 1774383, date(2020, 11, 2)),
        ("JOHN EXAMPLE & MARY EXAMPLE", 18721063, date(2025, 10, 27)),
        ("ANN PLACEHOLDER", 173289, date(2025, 6, 9)),
        ("BOB PLACEHOLDER", 173288, date(2025, 6, 9)),
    ]
    assert recs[0].owner_address == "C/O JANE SAMPLE, 100 TEST DR, MILTON, FL 32583"
    assert recs[1].owner_address == "1 MAIN ST, PACE, FL 32571-0000"
    assert len({r.source_key for r in recs}) == 4
    assert all(r.state == "FL" and r.county == "Santa Rosa" for r in recs)


def test_find_santarosa_list_url():
    html = """
      <a href="http://santarosaclerk.com/uploads/2025/11/surplus-formwip_tagged.pdf">Tax Deed Surplus Claim Forms</a>
      <a href="/uploads/2026/09/santa-rosa-county-tax-deed-surplus-rev-09-03-2026_ADA.pdf">Tax Deed Surplus Money</a>
    """
    assert santarosa_fl.find_list_url(html) == (
        "https://santarosaclerk.com/uploads/2026/09/santa-rosa-county-tax-deed-surplus-rev-09-03-2026_ADA.pdf"
    )
