"""CAMS (Computer Age Management Services) is India's largest mutual-fund
RTA. Their "Detailed Transaction Statement" CSV export uses headers such as
`Folio No`, `Scheme Name`, `Trxn Date`, `Trxn Desc`, `Amount`, `Units`,
`NAV`, `ISIN`. Column-name variance across CAMS export versions is handled
generically by `tabular.build_column_map`; this module just tags the
source and applies the one CAMS-specific quirk noted below.
"""
from __future__ import annotations

from app.services.parsers.common import ParsedTransaction
from app.services.parsers.csv_parser import parse_csv_bytes


def parse_cams_statement(content: bytes) -> list[ParsedTransaction]:
    # CAMS statements report redemption `Units` as already negative but
    # `Amount` as positive — `tabular._normalize_sign` re-derives both from
    # the classified transaction type regardless, so no extra handling is
    # needed here beyond tagging provenance for audit/debugging.
    return parse_csv_bytes(content, source_hint="cams")
