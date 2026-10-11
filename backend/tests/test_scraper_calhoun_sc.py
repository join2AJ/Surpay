"""Calhoun County, SC overage lists: synthetic lines laid out like the real PDFs (made-up names)."""

from datetime import date

from surpay.scrapers.calhoun_sc import find_list_urls, parse_lines

PAGE = """
<a href="/sites/calhouncounty/files/Documents/Calhoun%20County/Departments/Tax%20Collector/CCTC-Tax_Sale_Overage_Claim_Form_v2.pdf">Agreement and Release Form</a>
<a href="/sites/calhouncounty/files/Documents/Calhoun%20County/Departments/Tax%20Collector/Overages/CALHOUN-TaxColOvr_2022.pdf">2022</a>
<a href="/sites/calhouncounty/files/Documents/Calhoun%20County/Departments/Tax%20Collector/Overages/CALHOUN-TaxColOvr_2023.pdf">2023</a>
"""

LINES_2023 = [
    "                         TAX SALE DATE: NOVEMBER 13, 2023                           ",
    "             Sale#            Taxpayer             Map#       Overage               ",
    "           202300005 Sample, Robert Jr.        167-00-00-039  $  982.02              ",
    "           202300037 Example, Jane Ferril      106-00-02-056.01 $ 1,914.34           ",
    "           202300262 Virginia Placeholder Life Est 151-00-00-012 $ 7,483.87             ",
    "                                    1",
]
# The 2021 file has no sale date and uses Unicode hyphens in map numbers.
LINES_2021 = [
    "Sale Number Taxpayer Map Number Overage",
    "202100004 Mockperson, Romeo Jr. 074‐00‐02‐018 $ 736.47",
]


def test_find_list_urls():
    urls = find_list_urls(PAGE)
    assert [u.rsplit("_", 1)[1] for u in urls] == ["2022.pdf", "2023.pdf"]
    assert urls[0].startswith("https://calhouncounty.sc.gov/sites/")


def test_parse_calhoun_lines():
    recs = parse_lines(LINES_2023, "u")
    assert [(r.source_key, r.owner_name, r.amount_cents) for r in recs] == [
        ("202300005", "Sample, Robert Jr.", 98202),
        ("202300037", "Example, Jane Ferril", 191434),
        ("202300262", "Virginia Placeholder Life Est", 748387),
    ]
    assert all(r.sale_date == date(2023, 11, 13) and r.state == "SC" and r.county == "Calhoun" for r in recs)
    assert recs[1].reference == "Tax sale #202300037, Map 106-00-02-056.01"


def test_parse_calhoun_unicode_hyphens_and_no_sale_date():
    [r] = parse_lines(LINES_2021, "u")
    assert (r.source_key, r.owner_name, r.amount_cents, r.sale_date) == ("202100004", "Mockperson, Romeo Jr.", 73647, None)
    assert r.raw["map_number"] == "074-00-02-018" and r.raw["sale_year"] == 2021
