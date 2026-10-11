"""Wise County, TX parser, fed text lines laid out like the real registry report. Names are made up."""

from surpay.scrapers import wise_tx

LINES = """
      Registry & Trust Accounts With Balances                                                  TXWISEPROD2022
      As of Date: 09/01/2026 Sorted Order: Case Number
             271st Judicial District Court
      TAX REGISTY
      Case Number        Party Name                               Increases       Decreases   Net Credit Balance
      TX12906            SAMPLE, JANE J.                           $319.83                          $319.83
      TX13214            UNKNOWN HEIRS AND/OR DEVISEES OF JOHN B. $8,767.67                        $8,767.67
      TX13340            PLACEHOLDER INVESTMENTS, INC             $5,700.96       $700.96          $5,000.00
      TX13341            EXAMPLE, PAID OUT                        $1,000.00     $1,000.00              $0.00
      Subtotals                                                  $15,788.46         $0.00       $15,788.46
      Totals                                                     $15,788.46         $0.00       $15,788.46
""".splitlines()


def test_wise_lines():
    recs = wise_tx.parse_lines(LINES, "u")
    assert [(r.reference, r.owner_name, r.amount_cents) for r in recs] == [
        ("Case TX12906", "SAMPLE, JANE J.", 31983),
        ("Case TX13214", "UNKNOWN HEIRS AND/OR DEVISEES OF JOHN B.", 876767),
        ("Case TX13340", "PLACEHOLDER INVESTMENTS, INC", 500000),  # net balance, not the deposit
    ]
    assert recs[0].raw["as_of"] == "2026-09-01"
    assert all(r.state == "TX" and r.county == "Wise" for r in recs)


def test_wise_find_list_url():
    html = ('<a href="/453/Excess-Proceeds">Excess Proceeds</a>'
            '<a href="/DocumentCenter/View/7930/AUGUST-2026-EXCESS-PROCEEDS-REPORT-PDF">AUGUST 2026 EXCESS PROCEEDS REPORT (PDF)</a>')
    assert wise_tx.find_list_url(html) == (
        "https://www.co.wise.tx.us/DocumentCenter/View/7930/AUGUST-2026-EXCESS-PROCEEDS-REPORT-PDF")
