"""Cuyahoga County, OH Clerk of Courts excess funds spreadsheets: synthetic rows (made-up names)."""

import io
from datetime import date, datetime

import openpyxl

from surpay.scrapers.cuyahoga_oh import (
    find_list_url,
    parse_foreclosure_rows,
    parse_released_rows,
    sheet_rows,
)

PAGE = """
<a href="https://cuyahogacms.blob.core.windows.net/home/docs/default-source/coc/excessfunds-foreclosure.xlsx?sfvrsn=1_11">Excess Funds - Foreclosure</a>
<a href="https://cuyahogacms.blob.core.windows.net/home/docs/default-source/coc/excessfunds-nonforeclosure.xlsx?sfvrsn=2_11">Excess Funds - Non-Foreclosure</a>
<a href="https://cuyahogacms.blob.core.windows.net/home/docs/default-source/coc/excesstaxforeclosurefunds-released.xlsx?sfvrsn=3_2">Released</a>
"""

FORECLOSURE = [
    ("Case Number", "Disp Date", "Deposit", "Bond", "Plaintiff/Last", "Plaintiff/First", "Plaintiff/Middle",
     "Defendant/Last", "Defendant/First", "Defendant/Middle", "Defendant/Suffix"),
    ("CV02471284", datetime(2006, 10, 23), 0, 7000, "EXAMPLE BANK", None, None, "SAMPLE", "JANE", None, None),
    ("CV23974986", datetime(2025, 4, 15), 48600.05, 0, "EXAMPLE 22 LLC", None, None, "DOE", "JOHN", "E.", "JR"),
    ("BR19019226", "//", 140, 0, "TREASURER OF CUYAHOGA COUNTY OH", None, None, "PLACEHOLDER HOLDINGS LLC",
     None, None, None),
    ("CV09000001", datetime(2009, 1, 1), 0, 0, "BANK", None, None, "ZERO", "ZED", None, None),
]

RELEASED = [
    ("CASE NUMBER", "CAPTION", "DATE", "AMOUNT"),
    ("CV18894942", "TREASURER OF CUYAHOGA COUNTY  OHIO VS JANE SAMPLE  ET AL", datetime(2026, 1, 27), 57.14),
    ("CV18894942", "TREASURER OF CUYAHOGA COUNTY  OHIO VS JANE SAMPLE  ET AL", datetime(2026, 1, 27), 20),
    ("CV25111743", "TREASURER OF CUYAHOGA COUNTY  OHIO VS UNKNOWN HEIRS  ETC. OF JOHN EXAMPLE  ET AL",
     datetime(2026, 8, 25), 15399.64),
]


def test_find_list_urls():
    assert "excessfunds-foreclosure.xlsx" in find_list_url(PAGE, "excessfunds-foreclosure")
    assert "excesstaxforeclosurefunds-released" in find_list_url(PAGE, "excesstaxforeclosurefunds")


def test_parse_foreclosure_rows():
    recs = parse_foreclosure_rows(FORECLOSURE, "u")
    assert [(r.source_key, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("CV02471284", "JANE SAMPLE", 700000, date(2006, 10, 23)),
        ("CV23974986", "JOHN E. DOE JR", 4860005, date(2025, 4, 15)),
        ("BR19019226", "PLACEHOLDER HOLDINGS LLC", 14000, None),
    ]
    assert recs[1].raw["plaintiff"] == "EXAMPLE 22 LLC"
    assert all(r.state == "OH" and r.county == "Cuyahoga" and r.sale_type == "mortgage_foreclosure" for r in recs)


def test_parse_released_rows_sums_deposits_per_case():
    recs = parse_released_rows(RELEASED, "u")
    assert [(r.source_key, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("CV18894942", "JANE SAMPLE", 7714, date(2026, 1, 27)),
        ("CV25111743", "UNKNOWN HEIRS ETC. OF JOHN EXAMPLE", 1539964, date(2026, 8, 25)),
    ]
    assert all(r.sale_type == "tax_sale" for r in recs)


def test_xlsx_roundtrip():
    wb = openpyxl.Workbook()
    for row in FORECLOSURE:
        wb.active.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    recs = parse_foreclosure_rows(sheet_rows(buf.getvalue()), "u")
    assert sum(r.amount_cents for r in recs) == 700000 + 4860005 + 14000
