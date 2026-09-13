"""AMFI bulk NAV file parsing + fund NAV upsert. The AMFI daily NAV file
(https://www.amfiindia.com/spages/NAVAll.txt) is a semicolon-delimited text
file with AMC name banner lines, category banner lines, a header line, and
data lines of the form:

    Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Blank lines separate AMC sections; lines with fewer than 6 fields (banners,
category headers) are skipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundNavHistory


@dataclass(frozen=True, slots=True)
class NavRow:
    scheme_code: str
    isin_growth: str | None
    isin_div_reinvestment: str | None
    scheme_name: str
    nav: float
    nav_date: date


def parse_amfi_nav_file(text: str) -> list[NavRow]:
    rows: list[NavRow] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("scheme code"):
            continue
        fields = [f.strip() for f in stripped.split(";")]
        if len(fields) < 6:
            continue  # AMC banner or category header line
        scheme_code, isin_growth, isin_div, scheme_name, nav_str, date_str = fields[:6]
        try:
            nav = float(nav_str)
        except ValueError:
            continue  # NAV can be "N.A." for suspended/non-trading schemes
        try:
            nav_date = datetime.strptime(date_str, "%d-%b-%Y").date()
        except ValueError:
            continue

        rows.append(
            NavRow(
                scheme_code=scheme_code,
                isin_growth=isin_growth or None,
                isin_div_reinvestment=isin_div or None,
                scheme_name=scheme_name,
                nav=nav,
                nav_date=nav_date,
            )
        )
    return rows


async def upsert_fund_navs(session: AsyncSession, rows: list[NavRow]) -> int:
    """Matches each row to a `Fund` by ISIN (growth or div-reinvestment
    variant), updates its denormalized `current_nav`, and appends to
    `fund_nav_history` (idempotent on `(fund_id, nav_date)` via the table's
    unique constraint — a re-run for the same date is a no-op upsert)."""
    isin_to_row: dict[str, NavRow] = {}
    for row in rows:
        if row.isin_growth:
            isin_to_row[row.isin_growth] = row
        if row.isin_div_reinvestment:
            isin_to_row[row.isin_div_reinvestment] = row

    if not isin_to_row:
        return 0

    result = await session.execute(select(Fund).where(Fund.isin.in_(isin_to_row.keys())))
    funds = list(result.scalars().all())

    updated = 0
    for fund in funds:
        row = isin_to_row.get(fund.isin)
        if row is None:
            continue
        fund.current_nav = row.nav
        fund.current_nav_date = row.nav_date

        existing = await session.execute(
            select(FundNavHistory).where(
                FundNavHistory.fund_id == fund.id, FundNavHistory.nav_date == row.nav_date
            )
        )
        if existing.scalar_one_or_none() is None:
            session.add(FundNavHistory(fund_id=fund.id, nav_date=row.nav_date, nav=row.nav))
        updated += 1

    return updated
