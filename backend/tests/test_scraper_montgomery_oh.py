"""Montgomery County, OH excess funds list: synthetic lines laid out like the real PDF (made-up names)."""

import pytest

from surpay.scrapers.montgomery_oh import defendant, parse_lines

LINES = [
    "                             Montgomery County Clerk of Courts                      ",
    "                                    Excess Funds                                    ",
    "                                   As of September 1, 2026                          ",
    "     Case Number Caption                                              Excess Funds  ",
    "     2005 CV 06202 EXAMPLE BANK NATIONAL ASSOCIATION vs JANE Q SAMPLE $36,249.54",
    "     2012 CV 08977 SAMPLE BANK NA SUCCESSOR BY MERGER WITH OTHER BANK vs MARTHA L $407.47",
    "                MOCKPERSON DECEASED                                                      ",
    "     2016 CV 05989 TAX EASE OHIO LLC vs UNKNOWN DOE UNK HEIRS ETAL OF NORMAN DOE $13,417.33",
    "                                                                              1    ",
    "                             Montgomery County Clerk of Courts                      ",
    "     Case Number Caption                                              Excess Funds  ",
    "     2025 CV 06070 TRUST COMPANY vs ALAN PLACEHOLDER ET AL $1,000.00",
    "     Total: $51,074.34",
]


def test_parse_montgomery_lines():
    recs = parse_lines(LINES, "https://example/Excess-Funds.pdf")
    assert [(r.source_key, r.owner_name, r.amount_cents) for r in recs] == [
        ("2005 CV 06202", "JANE Q SAMPLE", 3624954),
        ("2012 CV 08977", "MARTHA L MOCKPERSON DECEASED", 40747),
        ("2016 CV 05989", "UNKNOWN DOE UNK HEIRS ETAL OF NORMAN DOE", 1341733),
        ("2025 CV 06070", "ALAN PLACEHOLDER", 100000),
    ]
    assert all(r.state == "OH" and r.county == "Montgomery" and r.sale_type == "mortgage_foreclosure" for r in recs)
    assert recs[0].raw["list_as_of"] == "2026-09-01"
    assert recs[1].reference == "Case 2012 CV 08977"


def test_total_mismatch_is_an_error():
    with pytest.raises(ValueError, match="layout may have changed"):
        parse_lines(LINES[:5] + ["Total: $1.00"], "u")


def test_defendant():
    assert defendant("BANK vs JOHN DOE ETAL") == "JOHN DOE"
    assert defendant("BANK VS. JOHN DOE, ET AL.") == "JOHN DOE"
