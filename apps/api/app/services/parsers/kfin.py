"""KFin Technologies (formerly Karvy) is India's second-largest MF RTA.
Their CSV export headers are close to CAMS's but use `Folio`, `Scheme`,
`Date`, `Description`, `Amount`, `Units`, `Rate`/`NAV` — handled by the
shared alias map in `parsers/common.py`."""
from __future__ import annotations

from app.services.parsers.common import ParsedTransaction
from app.services.parsers.csv_parser import parse_csv_bytes


def parse_kfin_statement(content: bytes) -> list[ParsedTransaction]:
    return parse_csv_bytes(content, source_hint="kfin")
