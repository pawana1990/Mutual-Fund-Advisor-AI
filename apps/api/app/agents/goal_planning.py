"""Goal Planning Agent — wraps `services/goal_planning.py` for each goal in
`state["goals"]` (each goal dict must carry target_amount, target_date,
current_progress_value, assumed_return_rate, and — for the Monte Carlo run
— an expected volatility estimate derived from the portfolio's asset mix)."""
from __future__ import annotations

from datetime import date

from app.agents.state import AdvisorState
from app.services.goal_planning import GoalInputs, monte_carlo_projection, required_monthly_sip

AGENT_NAME = "goal_planning_agent_v1"


def _years_between(target_date_iso: str) -> float:
    target = date.fromisoformat(target_date_iso)
    return max((target - date.today()).days / 365.0, 0.01)


def run(state: AdvisorState) -> dict:
    goals = state.get("goals", [])
    if not goals:
        return {"goals": []}

    enriched = []
    for goal in goals:
        years = _years_between(goal["target_date"])
        sip_inputs = GoalInputs(
            target_amount=goal["target_amount"],
            years_remaining=years,
            current_value=goal.get("current_progress_value", 0.0),
            assumed_annual_return_pct=goal.get("assumed_return_rate", 11.0),
            step_up_pct_per_year=goal.get("step_up_pct_per_year", 0.0),
        )
        sip = required_monthly_sip(sip_inputs)

        mc = monte_carlo_projection(
            current_value=goal.get("current_progress_value", 0.0),
            monthly_contribution=goal.get("current_monthly_sip", sip),
            years=years,
            target_amount=goal["target_amount"],
            expected_annual_return_pct=goal.get("assumed_return_rate", 11.0),
            annual_volatility_pct=goal.get("assumed_volatility_pct", 15.0),
        )

        enriched.append(
            {
                **goal,
                "required_monthly_sip": sip,
                "probability_of_success": mc.probability_of_success_pct,
                "projection_percentiles": mc.percentiles,
            }
        )

    return {"goals": enriched}
