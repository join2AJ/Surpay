"""Modoc County, CA notice of excess proceeds: synthetic lines laid out like the real PDF (made-up names)."""

from datetime import date

import pytest

from surpay.scrapers.modoc_ca import find_notice_urls, parse_lines

LINES = [
    "                     Excess proceeds have resulted from the sale of tax-defaulted property on May 15-18,",
    "                    2026. The parties listed below may be parties of interest as defined by California Revenue",
    "                      Parcel # Date of Deed Parties of Interest Amount              ",
    "                     002-073-001-000; 06/02/26 EXAMPLE REAL ESTATE SERVICES LLC 1,570.41",
    "                     002-073-008-000                                                ",
    "                     002-075-006-000 06/02/26 SAMPLE FERD & DOE MILO (ESTATE) 12,797.28",
    "                                              Milo Doe                             ",
    "                                             Aleta Sample                          ",
    "                                                                1",
    "                     021-260-020-000 06/02/26 PLACEHOLDER, TENG   14,205.39                ",
    "                                                           28,573.08",
    "                    I certify or declare, under penalty of perjury, that the foregoing is true and correct.",
    "                    June 25th, July 2nd and July 9th, 2026",
]

OLD_STYLE = [
    "Excess proceeds have resulted from the sale of tax-defaulted property on May 17-20,",
    "2024. The parties listed below ...",
    "005-291-028-000 May 31, 2024 MOCKPERSON, MYRLE V. 8,949.12",
    "011-260-024-000 & May 31, 2024 EXAMPLE, EDWARD 65,138.68",
    "                011-260-029-000",
]


def test_parse_modoc_notice():
    recs = parse_lines(LINES, "u", today=date(2026, 10, 11))
    assert [(r.source_key, r.owner_name, r.amount_cents) for r in recs] == [
        ("002-073-001-000|2026-06-02", "EXAMPLE REAL ESTATE SERVICES LLC", 157041),
        ("002-075-006-000|2026-06-02", "SAMPLE FERD & DOE MILO (ESTATE)", 1279728),
        ("021-260-020-000|2026-06-02", "PLACEHOLDER, TENG", 1420539),
    ]
    assert recs[0].reference == "APN 002-073-001-000, 002-073-008-000"
    assert recs[1].raw["other_parties_of_interest"] == ["Milo Doe", "Aleta Sample"]
    assert recs[1].raw["claim_deadline"] == "2027-06-02"
    assert all(r.sale_date == date(2026, 5, 15) and r.state == "CA" and r.sale_type == "tax_sale" for r in recs)


def test_expired_notice_is_skipped_and_long_dates_parse():
    assert parse_lines(OLD_STYLE, "u", today=date(2026, 10, 11)) == []
    recs = parse_lines(OLD_STYLE, "u", today=None)
    assert [r.reference for r in recs] == ["APN 005-291-028-000", "APN 011-260-024-000, 011-260-029-000"]
    assert recs[0].sale_date == date(2024, 5, 17)


def test_total_mismatch_is_an_error():
    with pytest.raises(ValueError, match="layout may have changed"):
        parse_lines(LINES[:4] + ["   99.99"], "u")


def test_find_notice_urls():
    html = ('<a href="/DocumentCenter/View/664/Publication---Excess-Proceeds-2024-PDF">Publication - Excess '
            'Proceeds 2024 (PDF)</a><a href="/DocumentCenter/View/666/FAQs-PDF">FAQs</a>')
    assert find_notice_urls(html) == [
        "https://www.countyofmodoc.gov/DocumentCenter/View/664/Publication---Excess-Proceeds-2024-PDF"]
