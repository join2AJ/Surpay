"""Volusia County, FL tax deed surplus ledger: synthetic rows laid out like the real PDF (names made up)."""

from datetime import date

from surpay.scrapers import volusia_fl


def words(*cells):
    row = []
    for x, text in cells:
        for i, w in enumerate(text.split()):
            row.append((x + i * 30, w))
    return row


def money_row(date_s, owner, cert, deposit, remaining, remit="12/31/2025"):
    cells = [(36, date_s), (122, owner), (427, cert), (488, "$"), (534, deposit), (616, "1"),
             (622, "5.00"), (690, deposit), (826, "380.00"), (885, "X"), (968, remaining)]
    if remit:
        cells.append((1015, remit))
    return words(*cells)


ROWS = [
    words((36, "CLERK OF THE CIRCUIT COURT - VOLUSIA COUNTY")),
    words((55, "Received"), (207, "Property Owner Name"), (429, "CERT #"), (491, "AMT OF DEPOSIT"),
          (919, "Remaining Balance")),
    money_row("7/12/2023", "JANE SAMPLE", "6912-20", "145,004.21", "51,198.66"),
    # Long owner name: the cell is bottom-aligned, so the extra lines come first.
    words((122, "ESTATE OF JOHN EXAMPLE AKA")),
    words((122, "JOHNNY EXAMPLE")),
    money_row("8/23/2023", "JR", "3414-20", "760.96", "4 22.05"),
    money_row("9/20/2023", "PAID IN FULL PERSON", "2993-20", "3,969.39", "-", remit=""),  # nothing left
    words((36, "C:\\Users\\someone\\Tax Deed Surplus FY 26")),  # footer resets pending name lines
    words((36, "CLERK OF THE CIRCUIT COURT - VOLUSIA COUNTY")),
    words((55, "Received"), (207, "Property Owner Name"), (429, "CERT #")),
    money_row("4/10/2024", "ANN PLACEHOLDER", "511-18", "1,440.16", "515.53"),
    money_row("4/10/2024", "BOB PLACEHOLDER", "511-18", "1,440.16", "515.53"),
]


def test_parse_volusia_rows():
    recs = volusia_fl.parse_rows(ROWS, "u")
    assert [(r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("JANE SAMPLE", 5119866, date(2023, 7, 12)),
        ("ESTATE OF JOHN EXAMPLE AKA JOHNNY EXAMPLE JR", 42205, date(2023, 8, 23)),
        ("ANN PLACEHOLDER", 51553, date(2024, 4, 10)),
        ("BOB PLACEHOLDER", 51553, date(2024, 4, 10)),
    ]
    assert recs[0].reference == "Tax Certificate 6912-20"
    assert recs[0].raw["remit_to_state"] == "12/31/2025"
    keys = [r.source_key for r in recs]
    assert keys[0] == "6912-20|2023-07-12"
    assert len(set(keys)) == len(keys)
    assert all(r.state == "FL" and r.county == "Volusia" for r in recs)
