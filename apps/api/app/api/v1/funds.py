"""Fund reference-data endpoints — shared across tenants, no organization
scoping needed. See docs/API_DESIGN.md `Funds`."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.fund import Fund, FundRiskMetrics
from app.schemas.fund import FundComparisonOut, FundDetailOut, FundRiskMetricsOut, FundSearchResult

router = APIRouter()


def _to_detail(fund: Fund) -> FundDetailOut:
    return FundDetailOut(
        id=fund.id,
        isin=fund.isin,
        name=fund.name,
        amc=fund.amc,
        category=fund.category,
        sub_category=fund.sub_category,
        benchmark=fund.benchmark,
        fund_manager=fund.fund_manager,
        expense_ratio=f"{fund.expense_ratio:.2f}" if fund.expense_ratio is not None else None,
        aum_cr=f"{fund.aum_cr:.2f}" if fund.aum_cr is not None else None,
        inception_date=fund.inception_date,
        current_nav=f"{fund.current_nav:.4f}" if fund.current_nav is not None else None,
        current_nav_date=fund.current_nav_date,
    )


@router.get("/search", response_model=list[FundSearchResult])
async def search_funds(
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=20, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> list[FundSearchResult]:
    like = f"%{q}%"
    stmt = (
        select(Fund)
        .where(or_(Fund.name.ilike(like), Fund.isin.ilike(like), Fund.amc.ilike(like)))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [
        FundSearchResult(
            id=f.id, isin=f.isin, name=f.name, amc=f.amc, category=f.category,
            current_nav=f"{f.current_nav:.4f}" if f.current_nav is not None else None,
        )
        for f in result.scalars().all()
    ]


@router.get("/{fund_id}", response_model=FundDetailOut)
async def get_fund(fund_id: UUID, session: AsyncSession = Depends(get_db_session)) -> FundDetailOut:
    fund = await session.get(Fund, fund_id)
    if fund is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fund not found")
    return _to_detail(fund)


@router.get("/{fund_id}/risk-metrics", response_model=FundRiskMetricsOut)
async def get_fund_risk_metrics(
    fund_id: UUID, window: str = Query(default="3y", pattern="^(1y|3y|5y)$"),
    session: AsyncSession = Depends(get_db_session),
) -> FundRiskMetricsOut:
    stmt = select(FundRiskMetrics).where(FundRiskMetrics.fund_id == fund_id, FundRiskMetrics.window == window)
    result = await session.execute(stmt)
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk metrics not yet computed for this fund/window")
    return FundRiskMetricsOut(
        window=m.window, cagr=m.cagr, beta=m.beta, alpha=m.alpha, sharpe_ratio=m.sharpe_ratio,
        sortino_ratio=m.sortino_ratio, std_deviation=m.std_deviation, max_drawdown=m.max_drawdown,
        category_rank=m.category_rank, category_size=m.category_size,
    )


@router.get("/compare", response_model=FundComparisonOut)
async def compare_funds(
    ids: str = Query(description="Comma-separated fund UUIDs, e.g. ?ids=a,b"),
    window: str = Query(default="3y", pattern="^(1y|3y|5y)$"),
    session: AsyncSession = Depends(get_db_session),
) -> FundComparisonOut:
    fund_ids = [UUID(v.strip()) for v in ids.split(",") if v.strip()]
    if len(fund_ids) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide at least two fund ids to compare")

    funds_result = await session.execute(select(Fund).where(Fund.id.in_(fund_ids)))
    funds = list(funds_result.scalars().all())

    metrics_result = await session.execute(
        select(FundRiskMetrics).where(FundRiskMetrics.fund_id.in_(fund_ids), FundRiskMetrics.window == window)
    )
    risk_metrics = {
        str(m.fund_id): FundRiskMetricsOut(
            window=m.window, cagr=m.cagr, beta=m.beta, alpha=m.alpha, sharpe_ratio=m.sharpe_ratio,
            sortino_ratio=m.sortino_ratio, std_deviation=m.std_deviation, max_drawdown=m.max_drawdown,
            category_rank=m.category_rank, category_size=m.category_size,
        )
        for m in metrics_result.scalars().all()
    }

    return FundComparisonOut(funds=[_to_detail(f) for f in funds], risk_metrics=risk_metrics)
