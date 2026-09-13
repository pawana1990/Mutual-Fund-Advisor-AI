from __future__ import annotations

from datetime import date

import pytest

from app.models.enums import HoldingSource
from app.services.parsers.common import ParserError, TxnType
from app.services.parsers.csv_parser import parse_csv_bytes
from app.services.parsers.detector import detect_source, parse_statement

CAMS_LIKE_CSV = """Folio No,Scheme Name,ISIN,Trxn Date,Trxn Desc,Amount,Units,NAV
1234567/0,Axis Bluechip Fund - Growth,INF846K01131,01-Apr-2024,Purchase,5000.00,45.2300,110.5670
1234567/0,Axis Bluechip Fund - Growth,INF846K01131,01-May-2024,SIP Purchase,5000.00,44.8000,111.6000
1234567/0,Axis Bluechip Fund - Growth,INF846K01131,15-Jun-2024,Redemption,-2000.00,-17.5000,114.2000
"""

GROWW_LIKE_CSV = """Scheme Name,Order Date,Order Type,Amount,Units,NAV
Parag Parikh Flexi Cap Fund,2024-02-10,BUY,10000.00,120.5000,83.00
Parag Parikh Flexi Cap Fund,2024-03-10,SIP,10000.00,118.2000,84.60
"""

MALFORMED_CSV = """Not,A,Real,Statement
foo,bar,baz,qux
"""


class TestCsvParsing:
    def test_parses_cams_like_statement(self):
        txns = parse_csv_bytes(CAMS_LIKE_CSV.encode(), source_hint="cams")
        assert len(txns) == 3
        assert txns[0].type == TxnType.BUY
        assert txns[0].amount == pytest.approx(5000.00)
        assert txns[0].units == pytest.approx(45.23)
        assert txns[0].date == date(2024, 4, 1)
        assert txns[1].type == TxnType.SIP

        redemption = txns[2]
        assert redemption.type == TxnType.SELL
        assert redemption.amount < 0  # normalized to negative regardless of source sign
        assert redemption.units < 0

    def test_parses_groww_like_statement(self):
        txns = parse_csv_bytes(GROWW_LIKE_CSV.encode(), source_hint="groww")
        assert len(txns) == 2
        assert all(t.amount > 0 for t in txns)
        assert txns[1].type == TxnType.SIP

    def test_raises_on_missing_required_columns(self):
        with pytest.raises(ParserError):
            parse_csv_bytes(MALFORMED_CSV.encode())

    def test_raises_on_empty_content(self):
        with pytest.raises(ParserError):
            parse_csv_bytes(b"")


class TestDetector:
    def test_detects_cams_from_content_fingerprint(self):
        content = b"CAMSOnline Consolidated Statement\n" + CAMS_LIKE_CSV.encode()
        assert detect_source(content) == HoldingSource.CAMS

    def test_detects_groww_from_content_fingerprint(self):
        content = b"Groww Mutual Fund Statement\n" + GROWW_LIKE_CSV.encode()
        assert detect_source(content) == HoldingSource.GROWW

    def test_falls_back_to_generic_csv(self):
        assert detect_source(CAMS_LIKE_CSV.encode()) == HoldingSource.CSV

    def test_detects_pdf_by_magic_bytes(self):
        assert detect_source(b"%PDF-1.4 rest of file") == HoldingSource.PDF

    def test_end_to_end_parse_statement_dispatches_correctly(self):
        content = b"CAMSOnline Consolidated Statement\n" + CAMS_LIKE_CSV.encode()
        source, txns = parse_statement(content)
        assert source == HoldingSource.CAMS
        assert len(txns) == 3

    def test_needs_review_flag_set_for_unclassifiable_type(self):
        csv_bytes = (
            "Scheme Name,Date,Type,Amount,Units,NAV\n"
            "Some Fund,2024-01-01,Mystery Transaction,1000,10,100\n"
        ).encode()
        txns = parse_csv_bytes(csv_bytes)
        assert txns[0].needs_review is True
        assert txns[0].review_reason is not None
