"""Recommendation accept/dismiss endpoints — accepting NEVER executes a
trade (Phase 1 has no broker integration); it only records investor intent
for audit and future model feedback. See docs/API_DESIGN.md, docs/SECURITY.md."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_tenant_session
from app.core.security import Principal, get_current_principal
from app.models.enums import RecommendationStatus
from app.models.portfolio import Portfolio
from app.models.recommendation import Recommendation
from app.schemas.portfolio import RecommendationFeedback, RecommendationOut

router = APIRouter()


def _to_out(r: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=r.id, holding_id=r.holding_id, action=r.action.value,
        switch_target_fund_id=r.switch_target_fund_id, reason=r.reason,
        supporting_metrics=r.supporting_metrics, risk=r.risk,
        expected_benefit=r.expected_benefit, confidence=float(r.confidence),
        status=r.status.value, generated_by_agent=r.generated_by_agent,
    )


async def _get_owned_recommendation(
    recommendation_id: UUID, principal: Principal, session: AsyncSession
) -> Recommendation:
    stmt = (
        select(Recommendation)
        .join(Portfolio, Portfolio.id == Recommendation.portfolio_id)
        .where(Recommendation.id == recommendation_id, Portfolio.organization_id == principal.organization_id)
    )
    result = await session.execute(stmt)
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")
    return rec


@router.get("/{recommendation_id}", response_model=RecommendationOut)
async def get_recommendation(
    recommendation_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> RecommendationOut:
    return _to_out(await _get_owned_recommendation(recommendation_id, principal, session))


@router.post("/{recommendation_id}/accept", response_model=RecommendationOut)
async def accept_recommendation(
    recommendation_id: UUID,
    payload: RecommendationFeedback,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> RecommendationOut:
    rec = await _get_owned_recommendation(recommendation_id, principal, session)
    rec.status = RecommendationStatus.ACCEPTED
    await session.commit()
    await session.refresh(rec)
    return _to_out(rec)


@router.post("/{recommendation_id}/dismiss", response_model=RecommendationOut)
async def dismiss_recommendation(
    recommendation_id: UUID,
    payload: RecommendationFeedback,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> RecommendationOut:
    rec = await _get_owned_recommendation(recommendation_id, principal, session)
    rec.status = RecommendationStatus.DISMISSED
    await session.commit()
    await session.refresh(rec)
    return _to_out(rec)
