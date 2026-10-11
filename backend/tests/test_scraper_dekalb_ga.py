"""DeKalb County, GA parser, fed synthetic rows laid out like the real PDF. Names are made up."""

from datetime import date

import pytest

from surpay.scrapers import dekalb_ga


def words(*cells):
    """cells: (x, "text with spaces") -> row of single words at increasing x."""
    return [(x + i * 12, w) for x, text in cells for i, w in enumerate(text.split())]


HEADER = words((33, "PARCEL ID"), (86, "EXCESS AMOUNT"), (159, "SALEDATE"), (344, "FIRST NAME"),
               (540, "MIDDLE"), (628, "LAST NAME"), (747, "SITUS ADDRESS"), (878, "CITY"), (948, "ZIP CODE"))


def test_dekalb_rows():
    rows = [
        words((445, "EXCESS FUNDS")),
        HEADER,
        words((28, "15"), (38, "093"), (51, "11"), (60, "101"), (96, "$10,014.47"), (161, "5/4/2021"),
              (328, "SAMPLE HOLDINGS LLC"), (722, "12 HARVEST WAY"), (871, "DECATUR"), (953, "30034")),
        words((28, "18"), (38, "014"), (51, "06"), (60, "065"), (98, "$8,625.61"), (161, "6/1/2021"),
              (321, "ESTATE OF JOHN L EXAMPLE"), (633, "EXAMPLE"), (745, "5 S OAK ROAD"),
              (855, "STONE MOUNTAIN"), (953, "30083")),
        words((28, "15"), (38, "156"), (51, "03"), (60, "001"), (98, "$6,002.57"), (161, "9/7/2021"),
              (352, "JANE"), (536, "QUINN"), (637, "SAMPLE"), (734, "9 TITAN DRIVE"), (871, "DECATUR"), (953, "30035")),
        words((975, "Page 1")),
    ]
    recs = dekalb_ga.parse_rows(rows, "u")
    assert [(r.reference, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("Parcel 15 093 11 101", "SAMPLE HOLDINGS LLC", 1001447, date(2021, 5, 4)),
        ("Parcel 18 014 06 065", "ESTATE OF JOHN L EXAMPLE", 862561, date(2021, 6, 1)),
        ("Parcel 15 156 03 001", "JANE QUINN SAMPLE", 600257, date(2021, 9, 7)),
    ]
    assert recs[1].owner_address == "5 S OAK ROAD, STONE MOUNTAIN, GA 30083"
    assert len({r.source_key for r in recs}) == 3
    assert all(r.state == "GA" and r.county == "DeKalb" and r.sale_type == "tax_sale" for r in recs)


def test_dekalb_layout_shift_and_missing_header():
    shift = lambda row: [(x + 9, t) for x, t in row]  # noqa: E731
    rows = [shift(HEADER), shift(words((28, "16"), (38, "121"), (51, "03"), (60, "016"), (101, "$727.52"),
                                       (161, "7/7/2026"), (333, "UNKNOWN OWNER"), (736, "1 MAIN ST"),
                                       (871, "LITHONIA"), (953, "30058")))]
    [r] = dekalb_ga.parse_rows(rows, "u")
    assert (r.owner_name, r.amount_cents) == ("UNKNOWN OWNER", 72752)
    with pytest.raises(ValueError, match="layout may have changed"):
        dekalb_ga.parse_rows(rows[1:], "u")


def test_dekalb_find_list_url():
    html = ('<a href="https://dekalbtaxga.gov/wp-content/uploads/EXCESS-FUNDS-CLAIM-FORM-FILLABLE-2021_0.pdf">Form</a>'
            '<a href="/wp-content/uploads/Excess-Funds-List.pdf">Excess Funds List</a>')
    assert dekalb_ga.find_list_url(html) == "https://dekalbtaxga.gov/wp-content/uploads/Excess-Funds-List.pdf"
