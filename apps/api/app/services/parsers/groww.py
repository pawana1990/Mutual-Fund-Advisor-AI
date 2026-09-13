"""Groww's "Mutual Fund Statement" CSV export uses headers `Scheme Name`,
`Order Date`, `Order Type` (BUY/SELL/SIP), `Amount`, `Units Allotted`,
`NAV`."""
from __future__ import annotations

from app.services.parsers.common import ParsedTransaction
from app.services.parsers.csv_parser import parse_csv_bytes


def parse_groww_statement(content: bytes) -> list[ParsedTransaction]:
    return parse_csv_bytes(content, source_hint="groww")
