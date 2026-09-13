from __future__ import annotations

from datetime import date

from app.services.market_data import parse_amfi_nav_file

SAMPLE_AMFI_FILE = """Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

HDFC Mutual Fund

100001;INF179K01YV8;INF179K01YW6;HDFC Top 100 Fund - Growth;950.1234;30-Aug-2025
100002;-;-;HDFC Top 100 Fund - IDCW;120.5678;30-Aug-2025

Axis Mutual Fund

100050;INF846K01EW2;-;Axis Bluechip Fund - Growth;65.4321;30-Aug-2025
100051;N.A.;-;Suspended Scheme;N.A.;30-Aug-2025
"""


class TestAmfiParsing:
    def test_parses_valid_rows_with_nav_and_date(self):
        rows = parse_amfi_nav_file(SAMPLE_AMFI_FILE)
        codes = {r.scheme_code for r in rows}
        assert "100001" in codes
        assert "100050" in codes

    def test_extracts_correct_nav_and_date(self):
        rows = {r.scheme_code: r for r in parse_amfi_nav_file(SAMPLE_AMFI_FILE)}
        hdfc = rows["100001"]
        assert hdfc.nav == 950.1234
        assert hdfc.nav_date == date(2025, 8, 30)
        assert hdfc.isin_growth == "INF179K01YV8"

    def test_skips_rows_with_na_nav(self):
        rows = {r.scheme_code: r for r in parse_amfi_nav_file(SAMPLE_AMFI_FILE)}
        assert "100051" not in rows

    def test_skips_banner_and_blank_lines(self):
        rows = parse_amfi_nav_file(SAMPLE_AMFI_FILE)
        # 4 valid data lines total minus 1 suspended (N.A.) = 3
        assert len(rows) == 3

    def test_empty_file_returns_empty_list(self):
        assert parse_amfi_nav_file("") == []
