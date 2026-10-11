"""Denton County, TX parser, fed the word stream pdf_stream_words() yields. Names are made up."""

from surpay.scrapers import denton_tx

WORDS = (
    "David Trantham Denton County District Clerk Excess Fund Cause Number Name Amt Deposit Date "
    "23-0495-393 Sample, Jane S & Example, John J $220,537.18 4/7/2026 "
    "22-0377-16 Placeholder Properties LLC $1,584.00 2/13/2024 "
    "2012-0756-16 Roe, Richard R $43,020.92 5/5/2021 "
    "21-7030-431 Tester, Ann, Et Al $892.97 5/28/2025 "
    "21-2000-442 Ann Example, Bob Example - (In Rem Only) $250.00 6/25/2025 "
    # a name that overprints the amount column on the page still streams before the amount
    "25-11783-442 A.B. Sample as Trustee for Church of Example, C.D. Sample as Trustee for Church of Example "
    "$9,454.60 9/25/2026 "
    "Current as of 10/01/2026 $230,000.00"
).split()


def test_denton_words():
    recs = denton_tx.parse_words(WORDS, "u")
    assert [(r.reference, r.owner_name, r.amount_cents) for r in recs] == [
        ("Cause 23-0495-393", "Sample, Jane S & Example, John J", 22053718),
        ("Cause 22-0377-16", "Placeholder Properties LLC", 158400),
        ("Cause 2012-0756-16", "Roe, Richard R", 4302092),
        ("Cause 21-7030-431", "Tester, Ann", 89297),
        ("Cause 21-2000-442", "Ann Example, Bob Example", 25000),
        ("Cause 25-11783-442",
         "A.B. Sample as Trustee for Church of Example, C.D. Sample as Trustee for Church of Example", 945460),
    ]
    assert recs[0].raw["deposited"] == "2026-04-07"
    assert len({r.source_key for r in recs}) == len(recs)
    assert all(r.state == "TX" and r.county == "Denton" and r.sale_type == "tax_sale" for r in recs)
