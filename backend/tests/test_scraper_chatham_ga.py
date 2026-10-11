"""Chatham County, GA parser, fed synthetic rows laid out like the real PDF. Names are made up."""

from datetime import date

from surpay.scrapers import chatham_ga


def words(*cells):
    return [(x + i * 12, w) for x, text in cells for i, w in enumerate(text.split())]


TITLE = [words((327, "OFFICE OF THE TAX COMMISSIONER")), words((333, "Jane Doe, Tax Commissioner")),
         words((299, "Excess Funds as of August 31, 2026"))]
HEADER = words((55, "PIN"), (291, "File Name"), (535, "Sale Date"), (615, "Bidder"), (682, "Remaining Balance"))


def test_chatham_entries():
    rows = TITLE + [
        HEADER,
        words((28, "10046 03008"), (100, "SAMPLE JANE Q"), (584, "FRED D BIDDER")),
        words((537, "5/4/2021"), (584, "JR"), (701, "$18,265.70")),
        words((28, "10115 01059"), (100, "IN REM AGAINST THE PROPERTY KNOWN AS LOT 1 OAK SUB SAID"), (584, "ANN BUYER")),
        words((100, "PROPERTY BEING FORMERLY IN THE NAME OF EXAMPLE JOHN, DECEASED"), (537, "1/2/2024"),
              (703, "$1,884.08")),
        words((28, "10378 02021"), (100, "ROE ANN & ROE"), (584, "BOB")),
        words((100, "BETTY*"), (537, "6/7/2022"), (704, "$4,911.19")),
        words((28, "10520 03009"), (100, "PLACEHOLDER ANN, BOB TESTER,")),
        words((22, "Updated 8/31/2026")),
    ] + TITLE + [
        HEADER,
        words((100, "AND CAROL EXAMPLE"), (535, "12/5/2023"), (703, "$4,463.60")),
        words((28, "80010N13004"), (100, "IN REM AGAINST THE PROPERTY KNOWN AS TR 2, SAID PROPERTY BEING"),
              (584, "SAM BUYER &")),
        words((100, "FORMERYL IN THE NAME OFSAMPLE ALMA, DECEASED"), (537, "12/3/2024"), (584, "PAT"), (703, "$63,087.91")),
        words((584, "BUYER")),
    ]
    recs = chatham_ga.parse_rows(rows, "u")
    assert [(r.reference, r.owner_name, r.amount_cents, r.sale_date) for r in recs] == [
        ("PIN 10046 03008", "SAMPLE JANE Q", 1826570, date(2021, 5, 4)),
        ("PIN 10115 01059", "EXAMPLE JOHN", 188408, date(2024, 1, 2)),
        ("PIN 10378 02021", "ROE ANN & ROE BETTY", 491119, date(2022, 6, 7)),
        ("PIN 10520 03009", "PLACEHOLDER ANN, BOB TESTER, AND CAROL EXAMPLE", 446360, date(2023, 12, 5)),
        ("PIN 80010N13004", "SAMPLE ALMA", 6308791, date(2024, 12, 3)),
    ]
    assert recs[0].raw["bidder"] == "FRED D BIDDER JR"
    assert recs[-1].raw["bidder"] == "SAM BUYER & PAT BUYER"
    assert len({r.source_key for r in recs}) == 5


def test_chatham_owner_from_file_name():
    assert chatham_ga.owner_from_file_name("IN REM SAMPLE JANE, DECEASED") == "SAMPLE JANE"
    assert chatham_ga.owner_from_file_name("IN REM AGAINST ... FORMERLY IN THE NAME COASTAL LLC") == "COASTAL LLC"


def test_chatham_find_list_url():
    html = """<a href="https://cms.example/api/assets/taxcommissioner/f8fe?download=0" title="Request for Excess Funds PDF">
    Click Here to Download<br />Excess Funds Request Form</a>
    <ul class="pdf"><li><a href="https://cms.example/api/assets/taxcommissioner/9ce8?download=0">Excess Funds Report
    <span class="smaller">(Updated 08.31.2026)</span></a></li></ul>"""
    assert chatham_ga.find_list_url(html) == "https://cms.example/api/assets/taxcommissioner/9ce8?download=0"
