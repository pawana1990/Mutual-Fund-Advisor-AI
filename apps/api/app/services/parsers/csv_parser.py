"""Generic CSV parser — also the base I/O layer for Groww, Zerodha Coin,
ET Money, and Kuvera exports, which are all comma/tab-separated with minor
header differences already handled by `tabular.build_column_map`."""
from __future__ import annotations

import csv
import io

from app.services.parsers.common import ParsedTransaction, ParserError
from app.services.parsers.tabular import parse_rows


def parse_csv_bytes(content: bytes, *, source_hint: str = "csv") -> list[ParsedTransaction]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Some AMC/RTA exports prepend a few banner lines before the real header
    # row (folio summary, statement period, etc.) — find the first line that
    # looks like a header (contains "date" and at least one of amount/units).
    lines = text.splitlines()
    header_idx = 0
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if "date" in lowered and ("amount" in lowered or "units" in lowered or "unit" in lowered):
            header_idx = idx
            break

    cleaned_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(cleaned_text))
    rows = [row for row in reader if any((v or "").strip() for v in row.values())]
    if not rows:
        raise ParserError("CSV file contained no parsable data rows")
    return parse_rows(rows, source_hint=source_hint)
