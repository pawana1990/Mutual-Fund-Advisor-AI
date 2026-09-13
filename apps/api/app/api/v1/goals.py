"""Goal endpoints, nested under a portfolio — see docs/API_DESIGN.md `Goals`."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.goal_planning import run as run_goal_planning_agent
from app.api.v1.deps import get_owned_portfolio, get_tenant_session
from app.models.goal import Goal
from app.models.portfolio import Portfolio
from app.schemas.portfolio import GoalCreate, GoalOut, GoalProjectionOut

router = APIRouter()


@router.get("/portfolios/{portfolio_id}/goals", response_model=list[GoalOut])
async def list_goals(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[GoalOut]:
    result = await session.execute(select(Goal).where(Goal.portfolio_id == portfolio.id))
    return [
        GoalOut(
            id=g.id, type=g.type.value, target_amount=f"{g.target_amount:.2f}",
            target_date=g.target_date,
            required_monthly_sip=f"{g.required_monthly_sip:.2f}" if g.required_monthly_sip is not None else None,
            probability_of_success=float(g.probability_of_success) if g.probability_of_success is not None else None,
        )
        for g in result.scalars().all()
    ]


@router.post("/portfolios/{portfolio_id}/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate,
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> GoalOut:
    goal = Goal(
        portfolio_id=portfolio.id, type=payload.type, target_amount=payload.target_amount,
        target_date=payload.target_date, current_progress_value=0.0,
        assumed_return_rate=payload.assumed_return_rate,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return GoalOut(
        id=goal.id, type=goal.type.value, target_amount=f"{goal.target_amount:.2f}",
        target_date=goal.target_date, required_monthly_sip=None, probability_of_success=None,
    )


@router.get("/goals/{goal_id}/projection", response_model=GoalProjectionOut)
async def get_goal_projection(
    goal_id: UUID,
    session: AsyncSession = Depends(get_tenant_session),
) -> GoalProjectionOut:
    goal = await session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")

    result = run_goal_planning_agent(
        {
            "goals": [
                {
                    "target_amount": float(goal.target_amount),
                    "target_date": goal.target_date.isoformat(),
                    "current_progress_value": float(goal.current_progress_value),
                    "assumed_return_rate": float(goal.assumed_return_rate),
                }
            ]
        }
    )
    enriched = result["goals"][0]

    goal.required_monthly_sip = enriched["required_monthly_sip"]
    goal.probability_of_success = enriched["probability_of_success"]
    await session.commit()

    return GoalProjectionOut(
        percentiles=enriched["projection_percentiles"],
        required_monthly_sip=f"{enriched['required_monthly_sip']:.2f}",
        probability_of_success=enriched["probability_of_success"],
    )
