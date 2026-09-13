"""Format auto-detection: given raw upload bytes (+ optional filename/
declared content-type), pick the right parser. This is the single entry
point the `import-worker` Celery task calls — see docs/ARCHITECTURE.md §6.
"""
from __future__ import annotations

from app.models.enums import HoldingSource
from app.services.parsers.cams import parse_cams_statement
from app.services.parsers.common import ParsedTransaction, ParserError
from app.services.parsers.csv_parser import parse_csv_bytes
from app.services.parsers.etmoney import parse_etmoney_statement
from app.services.parsers.excel_parser import parse_excel_bytes
from app.services.parsers.groww import parse_groww_statement
from app.services.parsers.kfin import parse_kfin_statement
from app.services.parsers.kuvera import parse_kuvera_statement
from app.services.parsers.pdf_parser import parse_cas_pdf
from app.services.parsers.zerodha import parse_zerodha_coin_statement

_PDF_MAGIC = b"%PDF-"
_XLSX_MAGIC = b"PK\x03\x04"  # xlsx is a zip archive

# Header/content fingerprints, checked in order — first match wins.
_CONTENT_FINGERPRINTS: list[tuple[str, HoldingSource]] = [
    ("camsonline", HoldingSource.CAMS),
    ("cams service", HoldingSource.CAMS),
    ("kfintech", HoldingSource.KFIN),
    ("karvy", HoldingSource.KFIN),
    ("groww", HoldingSource.GROWW),
    ("zerodha coin", HoldingSource.ZERODHA_COIN),
    ("coin by zerodha", HoldingSource.ZERODHA_COIN),
    ("et money", HoldingSource.ETMONEY),
    ("etmoney", HoldingSource.ETMONEY),
    ("kuvera", HoldingSource.KUVERA),
]

_PARSER_DISPATCH = {
    HoldingSource.CAMS: parse_cams_statement,
    HoldingSource.KFIN: parse_kfin_statement,
    HoldingSource.GROWW: parse_groww_statement,
    HoldingSource.ZERODHA_COIN: parse_zerodha_coin_statement,
    HoldingSource.ETMONEY: parse_etmoney_statement,
    HoldingSource.KUVERA: parse_kuvera_statement,
}


def detect_source(content: bytes, *, filename: str = "") -> HoldingSource:
    if content.startswith(_PDF_MAGIC):
        return HoldingSource.PDF
    if content.startswith(_XLSX_MAGIC) or filename.lower().endswith((".xlsx", ".xlsm")):
        return HoldingSource.EXCEL

    sample = content[:20_000].decode("utf-8", errors="ignore").lower()
    for fingerprint, source in _CONTENT_FINGERPRINTS:
        if fingerprint in sample:
            return source

    return HoldingSource.CSV  # generic fallback — the tabular parser's column-alias
    # matching handles unrecognized-but-well-formed CSVs.


def parse_statement(
    content: bytes, *, filename: str = "", declared_source: HoldingSource | None = None
) -> tuple[HoldingSource, list[ParsedTransaction]]:
    """Detect (unless `declared_source` is given by the user at upload time)
    and parse a statement. Returns the source actually used plus the parsed
    transactions."""
    source = declared_source or detect_source(content, filename=filename)

    if source == HoldingSource.PDF:
        return source, parse_cas_pdf(content)
    if source == HoldingSource.EXCEL:
        return source, parse_excel_bytes(content)
    if source == HoldingSource.MANUAL or source == HoldingSource.CSV:
        return source, parse_csv_bytes(content, source_hint=source.value)
    if source in _PARSER_DISPATCH:
        return source, _PARSER_DISPATCH[source](content)

    raise ParserError(f"Unsupported statement source: {source}")
