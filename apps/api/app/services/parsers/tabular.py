"""Shared row-level parsing logic for every tabular source (CAMS/KFin CSV
exports, Groww, Zerodha Coin, ET Money, Kuvera, generic CSV/Excel). Each
source module in this package is a thin adapter that gets rows into a
`list[dict]` and hands them to `parse_rows` here — this is where the actual
business logic (type classification, sign normalization, ambiguity
detection) lives, so it is written and tested exactly once.
"""
from __future__ import annotations

from datetime import date, datetime

from app.services.parsers.common import (
    ParsedTransaction,
    ParserError,
    TxnType,
    build_column_map,
    classify_transaction_type,
)

_DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y"]


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ParserError(f"Unrecognized date format: {value!r}")


def _parse_float(value) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", "").replace("₹", "").strip()
    cleaned = cleaned.replace("(", "-").replace(")", "")  # accounting-style negatives
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ParserError(f"Unrecognized numeric value: {value!r}") from exc


def _normalize_sign(txn_type: TxnType, amount: float, units: float) -> tuple[float, float]:
    """RTAs are inconsistent about whether redemption amounts/units are
    already negative. Force our own sign convention: BUY/SIP/SWITCH_IN =
    positive amount (money into the fund) and positive units; SELL/
    SWITCH_OUT = negative amount and negative units; DIVIDEND = positive
    amount, zero units; STT/other charges = negative amount."""
    outflow_from_fund = {TxnType.SELL, TxnType.SWITCH_OUT}
    inflow_to_fund = {TxnType.BUY, TxnType.SIP, TxnType.SWITCH_IN}

    amount_magnitude = abs(amount)
    units_magnitude = abs(units)

    if txn_type in inflow_to_fund:
        return amount_magnitude, units_magnitude
    if txn_type in outflow_from_fund:
        return -amount_magnitude, -units_magnitude
    if txn_type == TxnType.DIVIDEND:
        return amount_magnitude, 0.0
    if txn_type == TxnType.STT:
        return -amount_magnitude, 0.0
    return amount, units


def parse_rows(rows: list[dict], *, source_hint: str = "generic") -> list[ParsedTransaction]:
    if not rows:
        raise ParserError("No data rows found in statement")

    headers = list(rows[0].keys())
    column_map = build_column_map(headers)

    required = {"date", "amount", "units"}
    missing = required - set(column_map)
    if missing:
        raise ParserError(
            f"Could not identify required column(s) {sorted(missing)} in headers {headers} "
            f"(source hint: {source_hint})"
        )

    results: list[ParsedTransaction] = []
    for raw_row in rows:
        needs_review = False
        review_reason: str | None = None

        try:
            txn_date = _parse_date(str(raw_row[column_map["date"]]))
        except ParserError as exc:
            needs_review, review_reason, txn_date = True, str(exc), date.today()

        description = str(raw_row.get(column_map.get("type", ""), ""))
        txn_type = classify_transaction_type(description)
        if txn_type is None:
            needs_review = True
            review_reason = review_reason or f"Could not classify transaction type from {description!r}"
            txn_type = TxnType.BUY  # safest default pending manual review

        try:
            amount = _parse_float(raw_row.get(column_map["amount"]))
            units = _parse_float(raw_row.get(column_map["units"]))
        except ParserError as exc:
            needs_review, review_reason = True, str(exc)
            amount, units = 0.0, 0.0

        amount, units = _normalize_sign(txn_type, amount, units)

        nav_col = column_map.get("nav")
        if nav_col and raw_row.get(nav_col):
            nav = _parse_float(raw_row[nav_col])
        elif units:
            nav = round(abs(amount / units), 4)
        else:
            nav = 0.0

        scheme_name = str(raw_row.get(column_map.get("scheme_name", ""), "")).strip()
        if not scheme_name:
            needs_review, review_reason = True, review_reason or "Missing scheme name"

        results.append(
            ParsedTransaction(
                scheme_name=scheme_name,
                date=txn_date,
                type=txn_type,
                units=units,
                nav=nav,
                amount=amount,
                folio_number=str(raw_row.get(column_map.get("folio_number", ""), "")).strip() or None,
                isin=str(raw_row.get(column_map.get("isin", ""), "")).strip().upper() or None,
                amc_hint=source_hint,
                needs_review=needs_review,
                review_reason=review_reason,
                raw=raw_row,
            )
        )
    return results
