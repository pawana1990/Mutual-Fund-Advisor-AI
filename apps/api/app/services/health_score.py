"""Deterministic Portfolio Health Score aggregator (0-100).

Intentionally NOT an LLM call: the score must be reproducible, auditable,
and stable given the same inputs — the LLM's only job (in
`agents/recommendation.py`) is to *explain* this score in plain English,
never to compute it. See docs/DATABASE_SCHEMA.md `health_scores` and
docs/AI_AGENT_WORKFLOW.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.financial_metrics import herfindahl_hirschman_index


@dataclass(frozen=True, slots=True)
class HealthScoreInputs:
    # Diversification
    amc_values: dict[str, float]
    sector_values: dict[str, float]
    fund_count: int

    # Risk
    portfolio_volatility_pct: float  # annualized
    portfolio_max_drawdown_pct: float  # negative number, e.g. -28.0
    risk_profile_volatility_tolerance_pct: float  # from user's risk_profile

    # Returns
    portfolio_xirr_pct: float
    category_median_xirr_pct: float

    # Fees
    weighted_avg_expense_ratio_pct: float
    category_median_expense_ratio_pct: float

    # Fund quality
    avg_category_rank_percentile: float  # 0-100, 100 = best-in-category on average

    # Tax efficiency
    unrealized_ltcg_within_exemption_pct: float  # 0-100, how much of harvestable exemption is being used
    stcg_pct_of_total_gains: float  # 0-100, lower is better (fewer short-term sales)

    # Asset allocation
    equity_pct: float
    target_equity_pct: float  # from user's risk profile / goal horizon

    # Goal readiness
    avg_goal_probability_of_success_pct: float  # 0-100, from Monte Carlo


@dataclass(frozen=True, slots=True)
class HealthScoreResult:
    overall_score: int
    diversification_score: int
    risk_score: int
    returns_score: int
    fees_score: int
    fund_quality_score: int
    tax_efficiency_score: int
    asset_allocation_score: int
    goal_readiness_score: int


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(round(max(lo, min(hi, value))))


def _score_diversification(i: HealthScoreInputs) -> int:
    amc_hhi = herfindahl_hirschman_index(i.amc_values) if i.amc_values else 10_000
    sector_hhi = herfindahl_hirschman_index(i.sector_values) if i.sector_values else 10_000
    # HHI ranges 0(perfectly diversified)-10000(single holding); invert to a 0-100 score.
    amc_component = 100 - (amc_hhi / 100)
    sector_component = 100 - (sector_hhi / 100)
    fund_count_component = min(100, i.fund_count * 12.5)  # ~8 well-chosen funds -> 100
    return _clip(0.4 * amc_component + 0.4 * sector_component + 0.2 * fund_count_component)


def _score_risk(i: HealthScoreInputs) -> int:
    vol_ratio = i.portfolio_volatility_pct / max(i.risk_profile_volatility_tolerance_pct, 1e-6)
    # 1.0 = exactly at tolerance -> 70 pts; scales down/up around that anchor.
    vol_component = _clip(100 - abs(vol_ratio - 1.0) * 60)
    drawdown_component = _clip(100 + i.portfolio_max_drawdown_pct * 1.5)  # -40% dd -> 40 pts
    return _clip(0.5 * vol_component + 0.5 * drawdown_component)


def _score_returns(i: HealthScoreInputs) -> int:
    delta = i.portfolio_xirr_pct - i.category_median_xirr_pct
    # +5pp above category median -> 100; -5pp below -> 0; linear in between, anchored at 50.
    return _clip(50 + delta * 10)


def _score_fees(i: HealthScoreInputs) -> int:
    delta = i.category_median_expense_ratio_pct - i.weighted_avg_expense_ratio_pct
    # Cheaper than median -> higher score. 1pp cheaper -> +25 from the 50 anchor.
    return _clip(50 + delta * 25)


def _score_fund_quality(i: HealthScoreInputs) -> int:
    return _clip(i.avg_category_rank_percentile)


def _score_tax_efficiency(i: HealthScoreInputs) -> int:
    harvest_component = _clip(i.unrealized_ltcg_within_exemption_pct)
    stcg_penalty_component = _clip(100 - i.stcg_pct_of_total_gains)
    return _clip(0.5 * harvest_component + 0.5 * stcg_penalty_component)


def _score_asset_allocation(i: HealthScoreInputs) -> int:
    drift = abs(i.equity_pct - i.target_equity_pct)
    # 0pp drift -> 100; 30pp drift -> 0.
    return _clip(100 - drift * (100 / 30))


def _score_goal_readiness(i: HealthScoreInputs) -> int:
    return _clip(i.avg_goal_probability_of_success_pct)


# Weights sum to 1.0 — tune here, never inline at a call site.
_WEIGHTS = {
    "diversification": 0.15,
    "risk": 0.15,
    "returns": 0.15,
    "fees": 0.10,
    "fund_quality": 0.15,
    "tax_efficiency": 0.10,
    "asset_allocation": 0.10,
    "goal_readiness": 0.10,
}
assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9


def compute_health_score(inputs: HealthScoreInputs) -> HealthScoreResult:
    sub_scores = {
        "diversification": _score_diversification(inputs),
        "risk": _score_risk(inputs),
        "returns": _score_returns(inputs),
        "fees": _score_fees(inputs),
        "fund_quality": _score_fund_quality(inputs),
        "tax_efficiency": _score_tax_efficiency(inputs),
        "asset_allocation": _score_asset_allocation(inputs),
        "goal_readiness": _score_goal_readiness(inputs),
    }
    overall = round(sum(sub_scores[k] * _WEIGHTS[k] for k in _WEIGHTS))
    return HealthScoreResult(
        overall_score=int(overall),
        diversification_score=sub_scores["diversification"],
        risk_score=sub_scores["risk"],
        returns_score=sub_scores["returns"],
        fees_score=sub_scores["fees"],
        fund_quality_score=sub_scores["fund_quality"],
        tax_efficiency_score=sub_scores["tax_efficiency"],
        asset_allocation_score=sub_scores["asset_allocation"],
        goal_readiness_score=sub_scores["goal_readiness"],
    )
