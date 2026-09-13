"""Portfolio endpoints — see docs/API_DESIGN.md `Portfolio`.

`GET /snapshot` and `GET /health-score` read from the materialized
`portfolio_snapshots`/`health_scores` tables (the hot dashboard read path —
see docs/ARCHITECTURE.md §2 CQRS-lite note); `POST /recompute` is what
actually invokes the LangGraph refresh pipeline and writes new rows.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.health_score_aggregator import explain_health_score
from app.agents.orchestrator import build_refresh_graph
from app.api.v1.deps import get_owned_portfolio, get_tenant_session
from app.core.security import Principal, get_current_principal
from app.models.enums import RecommendationStatus
from app.models.fund import Fund
from app.models.portfolio import Holding, Portfolio
from app.models.recommendation import Recommendation
from app.models.snapshot import HealthScore, PortfolioSnapshot
from app.schemas.portfolio import (
    HealthScoreOut,
    HoldingOut,
    PortfolioCreate,
    PortfolioOut,
    RecommendationOut,
    SnapshotOut,
)
from app.services.holding_view import load_holding_views

router = APIRouter()


@router.get("", response_model=list[PortfolioOut])
async def list_portfolios(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[Portfolio]:
    stmt = select(Portfolio).where(Portfolio.organization_id == principal.organization_id)
    if principal.role.value == "client_viewer":
        stmt = stmt.where(Portfolio.owner_user_id == principal.user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: PortfolioCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> Portfolio:
    portfolio = Portfolio(
        organization_id=principal.organization_id,
        owner_user_id=principal.user_id,
        name=payload.name,
        base_currency=payload.base_currency,
    )
    session.add(portfolio)
    await session.commit()
    await session.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio(portfolio: Portfolio = Depends(get_owned_portfolio)) -> Portfolio:
    return portfolio


@router.get("/{portfolio_id}/holdings", response_model=list[HoldingOut])
async def list_holdings(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[HoldingOut]:
    stmt = (
        select(Holding, Fund)
        .join(Fund, Fund.id == Holding.fund_id)
        .where(Holding.portfolio_id == portfolio.id)
    )
    result = await session.execute(stmt)
    out = []
    for holding, fund in result.all():
        gain = float(holding.current_value) - float(holding.invested_value)
        gain_pct = (gain / float(holding.invested_value) * 100) if holding.invested_value else 0.0
        out.append(
            HoldingOut(
                id=holding.id,
                fund_id=fund.id,
                fund_name=fund.name,
                amc=fund.amc,
                category=fund.category,
                units=f"{holding.units:.4f}",
                avg_cost_nav=f"{holding.avg_cost_nav:.4f}",
                invested_value=f"{holding.invested_value:.2f}",
                current_value=f"{holding.current_value:.2f}",
                unrealized_gain=f"{gain:.2f}",
                unrealized_gain_pct=f"{gain_pct:.2f}",
            )
        )
    return out


@router.get("/{portfolio_id}/snapshot", response_model=SnapshotOut)
async def get_latest_snapshot(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> SnapshotOut:
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio.id)
        .order_by(PortfolioSnapshot.as_of.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No snapshot yet — import a statement or call POST /recompute first",
        )
    return SnapshotOut(
        as_of=snapshot.as_of,
        invested_value=f"{snapshot.invested_value:.2f}",
        current_value=f"{snapshot.current_value:.2f}",
        xirr=f"{snapshot.xirr:.2f}" if snapshot.xirr is not None else "0.00",
        absolute_return_pct=f"{snapshot.absolute_return_pct:.2f}" if snapshot.absolute_return_pct is not None else "0.00",
        asset_allocation=snapshot.asset_allocation,
        sector_allocation=snapshot.sector_allocation,
        amc_allocation=snapshot.amc_allocation,
        top_holdings=snapshot.top_holdings,
    )


@router.get("/{portfolio_id}/health-score", response_model=HealthScoreOut)
async def get_health_score(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> HealthScoreOut:
    stmt = (
        select(HealthScore)
        .where(HealthScore.portfolio_id == portfolio.id)
        .order_by(HealthScore.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No health score yet — call POST /recompute first")
    return HealthScoreOut(
        overall_score=score.overall_score,
        diversification_score=score.diversification_score,
        risk_score=score.risk_score,
        returns_score=score.returns_score,
        fees_score=score.fees_score,
        fund_quality_score=score.fund_quality_score,
        tax_efficiency_score=score.tax_efficiency_score,
        asset_allocation_score=score.asset_allocation_score,
        goal_readiness_score=score.goal_readiness_score,
        explanation=score.explanation,
    )


@router.get("/{portfolio_id}/recommendations", response_model=list[RecommendationOut])
async def list_recommendations(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
    status_filter: str | None = None,
) -> list[RecommendationOut]:
    stmt = select(Recommendation).where(Recommendation.portfolio_id == portfolio.id)
    if status_filter:
        stmt = stmt.where(Recommendation.status == status_filter)
    result = await session.execute(stmt.order_by(Recommendation.created_at.desc()))
    return [
        RecommendationOut(
            id=r.id, holding_id=r.holding_id, action=r.action.value,
            switch_target_fund_id=r.switch_target_fund_id, reason=r.reason,
            supporting_metrics=r.supporting_metrics, risk=r.risk,
            expected_benefit=r.expected_benefit, confidence=float(r.confidence),
            status=r.status.value, generated_by_agent=r.generated_by_agent,
        )
        for r in result.scalars().all()
    ]


@router.post("/{portfolio_id}/recompute", response_model=HealthScoreOut)
async def recompute_portfolio(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> HealthScoreOut:
    """Synchronously runs the full LangGraph refresh pipeline (Portfolio
    Analysis -> Fund Research/Overlap/Risk/Tax -> Recommendation -> Goal
    Planning -> Health Score) and persists the resulting snapshot, health
    score, and recommendations. In production this is also triggered
    asynchronously by the `import.completed` event — see
    docs/ARCHITECTURE.md §6 — this endpoint exists for an explicit
    user-triggered "refresh now"."""
    holdings = await load_holding_views(session, portfolio.id)
    graph = build_refresh_graph()
    final_state = graph.invoke({"portfolio_id": str(portfolio.id), "holdings": holdings, "goals": [], "fund_metrics": {}})

    pm = final_state.get("portfolio_metrics", {})
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio.id,
        as_of=datetime.now(timezone.utc),
        invested_value=pm.get("invested_value", 0.0),
        current_value=pm.get("current_value", 0.0),
        xirr=pm.get("xirr", 0.0),
        absolute_return_pct=pm.get("absolute_return_pct", 0.0),
        asset_allocation=pm.get("asset_allocation", {}),
        sector_allocation=pm.get("sector_allocation", {}),
        amc_allocation=pm.get("amc_allocation", {}),
        top_holdings=[],
    )
    session.add(snapshot)
    await session.flush()  # get snapshot.id without a full commit yet

    hs = final_state.get("health_score", {})
    if hs:
        try:
            explanation = explain_health_score(hs)
        except Exception:
            # LLM outage/network failure must never block persisting the
            # (deterministically computed) score itself — see
            # docs/MONITORING.md "OpenAI API outage" graceful degradation.
            explanation = (
                "Your Portfolio Health Score reflects diversification, risk, returns, fees, "
                "fund quality, tax efficiency, asset allocation, and goal readiness."
            )
        health_score_row = HealthScore(
            portfolio_id=portfolio.id,
            snapshot_id=snapshot.id,
            overall_score=hs["overall_score"],
            diversification_score=hs["diversification_score"],
            risk_score=hs["risk_score"],
            returns_score=hs["returns_score"],
            fees_score=hs["fees_score"],
            fund_quality_score=hs["fund_quality_score"],
            tax_efficiency_score=hs["tax_efficiency_score"],
            asset_allocation_score=hs["asset_allocation_score"],
            goal_readiness_score=hs["goal_readiness_score"],
            explanation=explanation,
            created_at=datetime.now(timezone.utc),
        )
        session.add(health_score_row)

    # Supersede prior open recommendations, then persist this run's
    # evidence-backed recommendations (guardrail-enforced by the agent
    # before they ever reach here — see agents/guardrails.py).
    await session.execute(
        update(Recommendation)
        .where(Recommendation.portfolio_id == portfolio.id, Recommendation.status == RecommendationStatus.OPEN)
        .values(status=RecommendationStatus.SUPERSEDED)
    )
    for rec in final_state.get("recommendations", []):
        session.add(
            Recommendation(
                portfolio_id=portfolio.id,
                holding_id=UUID(rec["holding_id"]) if rec.get("holding_id") else None,
                action=rec["action"],
                switch_target_fund_id=UUID(rec["switch_target_fund_id"]) if rec.get("switch_target_fund_id") else None,
                reason=rec["reason"],
                supporting_metrics=rec["supporting_metrics"],
                risk=rec["risk"],
                expected_benefit=rec["expected_benefit"],
                confidence=rec["confidence"],
                status=RecommendationStatus.OPEN,
                generated_by_agent=rec["generated_by_agent"],
            )
        )

    await session.commit()

    if not hs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Portfolio has no holdings to analyze")

    return HealthScoreOut(**{k: hs[k] for k in hs}, explanation=health_score_row.explanation)
