"""Zerodha Coin's "Mutual Fund Report" CSV export uses headers `Fund`,
`Trade Date`, `Transaction Type`, `Amount`, `Units`, `NAV`, `ISIN`."""
from __future__ import annotations

from app.services.parsers.common import ParsedTransaction
from app.services.parsers.csv_parser import parse_csv_bytes


def parse_zerodha_coin_statement(content: bytes) -> list[ParsedTransaction]:
    return parse_csv_bytes(content, source_hint="zerodha_coin")
