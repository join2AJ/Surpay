"""Collier County, FL excess proceeds list: synthetic rows laid out like the real PDF (names made up)."""

from datetime import date

from surpay.scrapers import collier_fl


def words(*cells):
    """cells: (x, "text with spaces") -> row of single words at increasing x."""
    row = []
    for x, text in cells:
        for i, w in enumerate(text.split()):
            row.append((x + i * 6, w))
    return row


HEADER = words((10, "Sale Date"), (37, "TDA #"), (90, "Claim Pending"), (194, "Claims Filed"),
               (294, "Legal Titleholder (prior to sale)"), (433, "Address"), (513, "City"),
               (554, "State / Zip"), (589, "Property ID#"), (670, "Legal Description"))


def rows(shift=0.0):
    data = [
        HEADER,
        words((9, "09/23/2024"), (41, "24076"), (61, "$18,838.46"), (124, "1/26/2025"),
              (264, "JANE Q SAMPLE"), (388, "100 TEST ST"), (494, "NAPLES"), (541, "FL 34101"),
              (586, "00000000001"), (615, "GOLDEN GATE EST")),
        words((9, "09/23/2024"), (41, "24094"), (96, "$43,165.98"), (124, "1/26/2025"),
              (189, "1st claim John Example"), (264, "JOHN EXAMPLE"), (388, "% ANN EXAMPLE 2 MAIN ST"),
              (494, "BROOKLYN"), (541, "NY 11235"), (586, "00000000002")),
        words((191, "2nd claim Placeholder Bank")),
        words((9, "02/24/2025"), (41, "24144"), (58, "$"), (64, "1"), (66, "9,474.38"), (124, "6/27/2025"),
              (264, "EXAMPLE HOLDINGS LLC"), (388, "PO BOX 1"), (494, "MIAMI"), (541, "FL 33101"),
              (586, "00000000003")),
        words((58, "$80,313.84"), (89, "$"), (99, "4"), (101, "3,165.98")),  # totals row
    ]
    return [[(x + shift, t) for x, t in r] for r in data]


def test_parse_collier_rows():
    recs = collier_fl.parse_rows(rows(), "u")
    assert [(r.source_key, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("24076", "JANE Q SAMPLE", 1883846, date(2024, 9, 23)),
        ("24094", "JOHN EXAMPLE", 4316598, date(2024, 9, 23)),
        ("24144", "EXAMPLE HOLDINGS LLC", 1947438, date(2025, 2, 24)),
    ]
    assert recs[0].owner_address == "100 TEST ST, NAPLES, FL 34101"
    assert recs[0].raw["status"] == "unclaimed"
    assert recs[1].raw["status"] == "claim pending"
    assert recs[1].raw["claims"] == ["1st claim John Example", "2nd claim Placeholder Bank"]
    assert all(r.state == "FL" and r.county == "Collier" and r.sale_type == "tax_sale" for r in recs)


def test_collier_layout_shift():
    recs = collier_fl.parse_rows(rows(shift=-5), "u")
    assert [r.amount_cents for r in recs] == [1883846, 4316598, 1947438]
