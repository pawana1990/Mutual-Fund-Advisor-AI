"""ET Money's transaction export uses headers `Scheme`, `Date`,
`Transaction Type`, `Amount`, `Units`, `NAV`."""
from __future__ import annotations

from app.services.parsers.common import ParsedTransaction
from app.services.parsers.csv_parser import parse_csv_bytes


def parse_etmoney_statement(content: bytes) -> list[ParsedTransaction]:
    return parse_csv_bytes(content, source_hint="etmoney")
