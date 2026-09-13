"""Shared types + normalization helpers for every statement parser
(CAMS, KFin, Groww, Zerodha Coin, ET Money, Kuvera, generic CSV/Excel/PDF).

Every parser's job is the same regardless of source format: turn whatever
the RTA/platform exports into a list of `ParsedTransaction`. The detector
(`detector.py`) picks which parser runs; the caller (an `import-worker`
Celery task) is responsible for matching `ParsedTransaction.isin` against
`funds.isin` and creating/updating `Holding`/`Transaction` rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class ParserError(Exception):
    """Raised when a file cannot be parsed at all (wrong format, corrupt).
    Row-level ambiguity should NOT raise this — it should be surfaced as a
    `needs_review` row instead (see `ParsedTransaction.needs_review`)."""


class TxnType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    SIP = "sip"
    SWITCH_IN = "switch_in"
    SWITCH_OUT = "switch_out"
    DIVIDEND = "dividend"
    STT = "stt"


@dataclass(slots=True)
class ParsedTransaction:
    scheme_name: str
    date: date
    type: TxnType
    units: float
    nav: float
    amount: float  # signed: +inflow to the fund, -redemption
    folio_number: str | None = None
    isin: str | None = None
    amc_hint: str | None = None
    needs_review: bool = False
    review_reason: str | None = None
    raw: dict = field(default_factory=dict)


# --- Free-text -> TxnType classification, shared across RTA-style parsers ---

_TYPE_KEYWORDS: list[tuple[str, TxnType]] = [
    ("systematic investment", TxnType.SIP),
    ("sip", TxnType.SIP),
    ("purchase", TxnType.BUY),
    ("subscription", TxnType.BUY),
    ("additional purchase", TxnType.BUY),
    ("switch in", TxnType.SWITCH_IN),
    ("switch-in", TxnType.SWITCH_IN),
    ("switch out", TxnType.SWITCH_OUT),
    ("switch-out", TxnType.SWITCH_OUT),
    ("redemption", TxnType.SELL),
    ("sell", TxnType.SELL),
    ("dividend", TxnType.DIVIDEND),
    ("idcw", TxnType.DIVIDEND),  # Income Distribution cum Capital Withdrawal
    ("stamp duty", TxnType.STT),
    ("stt", TxnType.STT),
]


def classify_transaction_type(description: str) -> TxnType | None:
    text = description.strip().lower()
    for keyword, txn_type in _TYPE_KEYWORDS:
        if keyword in text:
            return txn_type
    return None


def normalize_column_name(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


# Canonical column -> accepted header spellings across AMCs/platforms.
COLUMN_ALIASES: dict[str, list[str]] = {
    "date": [
        "date", "transactiondate", "trandate", "txndate", "trxndate",
        "orderdate", "tradedate",
    ],
    "scheme_name": ["schemename", "scheme", "fundname", "fund", "particulars"],
    "type": [
        "transactiontype", "type", "trantype", "trxndesc", "description",
        "ordertype",
    ],
    "amount": ["amount", "trnamount", "transactionamount", "value"],
    "units": ["units", "unit", "unitbal", "unitschanged", "unitsallotted"],
    "nav": ["nav", "purchasenav", "navrs", "rate"],
    "folio_number": ["folionumber", "foliono", "folio"],
    "isin": ["isin", "isincode"],
}


def build_column_map(headers: list[str]) -> dict[str, str]:
    """Map each canonical field to whichever actual header spelling is
    present, so every downstream parser can do `row[column_map["amount"]]`
    regardless of the exporting platform's exact header text."""
    normalized_headers = {normalize_column_name(h): h for h in headers}
    column_map: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized_headers:
                column_map[canonical] = normalized_headers[alias]
                break
    return column_map
