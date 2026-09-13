"""Kuvera's transaction export uses headers `Fund Name`, `Order Date`,
`Order Type`, `Amount`, `Units`, `NAV`, `Folio`."""
from __future__ import annotations

from app.services.parsers.common import ParsedTransaction
from app.services.parsers.csv_parser import parse_csv_bytes


def parse_kuvera_statement(content: bytes) -> list[ParsedTransaction]:
    return parse_csv_bytes(content, source_hint="kuvera")
