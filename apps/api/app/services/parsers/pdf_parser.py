"""Parser for consolidated CAS (Consolidated Account Statement) PDFs — the
combined-RTA PDF format issued by CAMS/KFin covering all folios across AMCs.
Layout (per folio block):

    Folio No: 1234567 / 0                       PAN: ABCDE1234F
    ISIN: INF090I01239 - Axis Bluechip Fund - Growth
    01-Apr-2024  Purchase                       5,000.00    45.2300   110.5670  500.7891
    15-Apr-2024  SIP Purchase                   5,000.00    46.1000   108.4600  605.7891

Text-based extraction via `pdfplumber`; a scanned/image-only PDF (no text
layer) is out of scope for Phase 1 and raises `ParserError` with a message
directing the user to CSV/Excel export instead (OCR is a documented Phase 2
enhancement — see docs/ARCHITECTURE.md §5 on the Lambda-based pipeline this
would run in).
"""
from __future__ import annotations

import io
import re

from app.services.parsers.common import ParsedTransaction, ParserError, TxnType, classify_transaction_type
from app.services.parsers.tabular import _normalize_sign, _parse_date, _parse_float

_ISIN_LINE = re.compile(r"ISIN:\s*([A-Z0-9]{12})\s*-\s*(.+)")
_FOLIO_LINE = re.compile(r"Folio No[:.]?\s*([\w/ -]+)")
_TXN_LINE = re.compile(
    r"^(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s+"
    r"(?P<desc>[A-Za-z][A-Za-z /\-*]+?)\s+"
    r"(?P<amount>-?[\d,]+\.\d{2})\s+"
    r"(?P<units>-?[\d,]+\.\d{2,4})\s+"
    r"(?P<nav>[\d,]+\.\d{2,4})"
    r"(?:\s+(?P<balance>-?[\d,]+\.\d{2,4}))?\s*$"
)


def parse_cas_pdf(content: bytes) -> list[ParsedTransaction]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dependency always installed in prod image
        raise ParserError("PDF parsing dependency not available") from exc

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise ParserError(f"Could not open PDF: {exc}") from exc

    if not full_text.strip():
        raise ParserError(
            "No extractable text found in PDF — this looks like a scanned/image-only "
            "statement, which is not yet supported. Please export CSV/Excel instead."
        )

    results: list[ParsedTransaction] = []
    current_isin: str | None = None
    current_scheme: str | None = None
    current_folio: str | None = None

    for line in full_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        isin_match = _ISIN_LINE.search(stripped)
        if isin_match:
            current_isin, current_scheme = isin_match.group(1), isin_match.group(2).strip()
            continue

        folio_match = _FOLIO_LINE.search(stripped)
        if folio_match:
            current_folio = folio_match.group(1).strip()
            continue

        txn_match = _TXN_LINE.match(stripped)
        if not txn_match:
            continue
        if current_scheme is None:
            continue  # transaction line before any scheme header — skip defensively

        groups = txn_match.groupdict()
        needs_review = False
        review_reason = None

        try:
            txn_date = _parse_date(groups["date"])
        except ParserError as exc:
            needs_review, review_reason, txn_date = True, str(exc), None

        txn_type = classify_transaction_type(groups["desc"])
        if txn_type is None:
            needs_review = True
            review_reason = review_reason or f"Could not classify transaction type from {groups['desc']!r}"
            txn_type = TxnType.BUY

        amount = _parse_float(groups["amount"])
        units = _parse_float(groups["units"])
        amount, units = _normalize_sign(txn_type, amount, units)
        nav = _parse_float(groups["nav"])

        if txn_date is None:
            continue

        results.append(
            ParsedTransaction(
                scheme_name=current_scheme,
                date=txn_date,
                type=txn_type,
                units=units,
                nav=nav,
                amount=amount,
                folio_number=current_folio,
                isin=current_isin,
                amc_hint="pdf",
                needs_review=needs_review,
                review_reason=review_reason,
                raw={"line": stripped},
            )
        )

    if not results:
        raise ParserError("No recognizable transaction lines found in PDF statement")

    return results
