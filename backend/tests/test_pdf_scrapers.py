"""Parsers for PDF table sources, fed synthetic rows laid out like the real files.

Rows are (x position, word) pairs, the same shape pdf_word_rows() produces. Names are made up.
"""

from datetime import date

from surpay.scrapers import dallas_tx, fortbend_tx, gwinnett_ga
from surpay.scrapers.base import columns, owner_from_style


def words(*cells):
    """cells: (x, "text with spaces") -> row of single words at increasing x."""
    row = []
    for x, text in cells:
        for i, w in enumerate(text.split()):
            row.append((x + i * 12, w))
    return row


def test_owner_from_style():
    assert owner_from_style("DALLAS COUNTY VS JANE Q SAMPLE ETAL") == "JANE Q SAMPLE"
    assert owner_from_style("DALLAS CO ETAL VS. JANE SAMPLE ET AL") == "JANE SAMPLE"
    assert owner_from_style("DALLAS COUNTY OF V JOHN EXAMPLE") == "JOHN EXAMPLE"
    assert owner_from_style("CITY OF X VS JOHN V EXAMPLE") == "JOHN V EXAMPLE"
    assert owner_from_style("Fort Bend County, Et Al Vs. Ann Placeholder, Et Al") == "Ann Placeholder"


def test_columns_by_position():
    c = columns([(10, "a"), (50, "b"), (60, "c"), (200, "d")], {"x": (0, 40), "y": (40, 100), "z": (100, 999)})
    assert c == {"x": "a", "y": "b c", "z": "d"}


def test_dallas_rows():
    rows = [
        words((58, "CASE NO."), (193, "STYLE"), (387, "SALE")),  # header
        words((54, "TX-21-01107"), (85, "DALLAS COUNTY VS JANE SAMPLE ETAL"), (330, "SHERIFF"),
              (370, "$"), (396, "2"), (399, ",945.83"), (425, "10/21/2024"), (462, "1/6/2025"),
              (489, "10/1/2024"), (522, "10/1/2026")),
        words((55, "TX2200051"), (85, "DALLAS CO ETAL VS. JOHN EXAMPLE"), (330, "SHERIFF"),
              (370, "$"), (393, "1"), (396, "2,425.20"), (425, "10/21/2024"), (489, "10/1/2024"),
              (522, "10/1/2026")),
    ]
    recs = dallas_tx.parse_rows(rows, "u")
    assert [(r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("JANE SAMPLE", 294583, date(2024, 10, 1)),
        ("JOHN EXAMPLE", 1242520, date(2024, 10, 1)),
    ]


def test_dallas_layout_shifted_between_months():
    """The October file came out of a different PDF tool: every column 12pt to the left."""
    shift = lambda row: [(x - 12, t) for x, t in row]  # noqa: E731
    rows = [shift(r) for r in [
        words((58, "CASE NO."), (193, "STYLE")),
        words((54, "TX-21-01107"), (85, "DALLAS COUNTY et al vs JANE SAMPLE"), (330, "CITY OF DALLAS"),
              (370, "$"), (393, "2"), (396, "1,839.04"), (425, "10/21/2024"), (462, "1/6/2025"),
              (489, "10/1/2024"), (522, "10/1/2026")),
    ]]
    [r] = dallas_tx.parse_rows(rows, "u")
    assert (r.owner_name, r.amount_cents, r.sale_date) == ("JANE SAMPLE", 2183904, date(2024, 10, 1))


def test_missing_header_is_an_error():
    import pytest

    with pytest.raises(ValueError, match="layout may have changed"):
        dallas_tx.parse_rows([words((54, "TX-21-01107"), (85, "X VS Y"))], "u")


def test_dallas_candidate_urls_walk_back_across_year():
    urls = dallas_tx.candidate_urls(date(2026, 2, 15), months_back=2)
    assert [u.rsplit("-", 1)[1] for u in urls] == ["020126.pdf", "010126.pdf", "120125.pdf"]


def test_fortbend_multiline_entries():
    rows = [
        words((58, "Orig Receipt Date"), (144, "Case Number"), (293, "Style")),  # "Receipt" at x=70
        words((88, "11/3/2009"), (137, "07-DCV-100001"), (219, "Fort Bend County, Et Al"),
              (437, "$388.54"), (477, "Payor"), (585, "240th District"), (711, "240th - Overpayment Refund")),
        words((219, "Vs."), (711, "Account 1")),
        words((219, "Ann Placeholder")),
        # big amount right-aligned so it starts inside the style column
        words((88, "6/18/2012"), (137, "09-DCV-100002"), (219, "Fort Bend County vs Jane"),
              (420, "$19,348.00"), (477, "Payor"), (585, "400th District"), (711, "400th - Excess Proceeds from")),
        words((219, "Sample, AKA Janie Sample,"), (711, "Tax Sale.")),
        words((219, "Et Al")),
    ]
    recs = fortbend_tx.parse_rows(rows, "u")
    assert len(recs) == 1  # the overpayment refund is skipped
    r = recs[0]
    assert r.owner_name == "Jane Sample, AKA Janie Sample"
    assert r.amount_cents == 1934800
    assert r.raw["received"] == "2012-06-18"


def test_gwinnett_rows():
    rows = [
        words((160, "NAME OF BUYER"), (318, "PARCEL NUMBER"), (472, "OWNER")),
        words((42, "3"), (48, "BUYER LLC"), (318, "R5018"), (334, "019A"), (371, "SAMPLE JANE MRS"),
              (595, "187 OAK DR"), (722, "$3,789.69"), (757, "May"), (768, "2021")),
        words((42, "4"), (48, "OTHER BUYER"), (318, "R7047"), (334, "171"), (371, "EXAMPLE JOHN E"),
              (722, "$78,988.96"), (757, "August"), (790, "2021")),
    ]
    recs = gwinnett_ga.parse_rows(rows, "u")
    assert [(r.reference, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("Parcel R5018 019A", "SAMPLE JANE MRS", 378969, date(2021, 5, 1)),
        ("Parcel R7047 171", "EXAMPLE JOHN E", 7898896, date(2021, 8, 1)),
    ]
    assert recs[0].owner_address == "187 OAK DR, Gwinnett County, GA"
    assert recs[1].owner_address == ""


def test_gwinnett_last_first_owner_matches_user(session):
    from surpay.ingest import upsert
    from surpay.matching import STRONG, find_matches
    from surpay.models import PreviousAddress, User

    upsert(session, "gwinnett_ga", gwinnett_ga.parse_rows([
        words((318, "PARCEL NUMBER")),
        words((42, "3"), (48, "BUYER LLC"), (318, "R5018"), (334, "019A"), (371, "SAMPLE JANE MRS"),
              (595, "187 OAK DR"), (722, "$3,789.69"), (757, "May"), (768, "2021")),
    ], "u"), full_snapshot=True)
    u = User(email="j@x.com", password_hash="x", full_name="Jane Sample", other_names=[],
             addresses=[PreviousAddress(street="187 Oak Drive", state="GA")])
    session.add(u)
    session.commit()
    [m] = find_matches(session, u)
    assert m.confidence == STRONG
