"""Manual Excel (.xlsx) statement parser — the common path for users who
maintain their own tracker spreadsheet or export from a broker to Excel."""
from __future__ import annotations

import io

from openpyxl import load_workbook

from app.services.parsers.common import ParsedTransaction, ParserError
from app.services.parsers.tabular import parse_rows


def parse_excel_bytes(content: bytes, *, source_hint: str = "excel", sheet_name: str | None = None) -> list[ParsedTransaction]:
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:  # openpyxl raises several exception types for corrupt files
        raise ParserError(f"Could not open workbook: {exc}") from exc

    sheet = workbook[sheet_name] if sheet_name else workbook.active
    rows_iter = sheet.iter_rows(values_only=True)

    header_row: tuple | None = None
    for candidate in rows_iter:
        cells = [str(c).strip().lower() if c is not None else "" for c in candidate]
        if "date" in cells and any(c in cells for c in ("amount", "units", "unit")):
            header_row = candidate
            break

    if header_row is None:
        raise ParserError("Could not locate a header row containing Date/Amount/Units columns")

    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(header_row)]
    rows: list[dict] = []
    for values in rows_iter:
        if values is None or all(v is None for v in values):
            continue
        row = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
        rows.append(row)

    if not rows:
        raise ParserError("Excel file contained no data rows below the header")

    return parse_rows(rows, source_hint=source_hint)
