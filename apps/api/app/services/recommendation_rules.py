"""Deterministic pre-screening rules that decide WHICH action a holding is a
*candidate* for, before the LLM is asked to explain WHY in natural language.
The LLM never chooses the action from scratch — it explains a rule-derived
verdict, or the verdict is `keep` — this is what keeps recommendations
evidence-first rather than free-form hallucination. See
docs/AI_AGENT_WORKFLOW.md §4.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuleVerdict:
    action: str  # keep | increase | reduce | exit | switch
    triggered_rules: list[str]
    supporting_metrics: dict[str, float]
    confidence: float


def evaluate_holding(
    *,
    expense_ratio: float,
    category_median_expense_ratio: float,
    category_rank_percentile: float,  # 0-100, 100 = best in category
    fund_xirr_pct: float,
    category_median_xirr_pct: float,
    overlap_pct_with_other_holdings: float,
    concentration_pct_of_portfolio: float,
    sharpe_ratio: float | None = None,
    expense_ratio_outlier_std_devs: float = 2.0,
    category_expense_ratio_std_dev: float = 0.3,
    overlap_warning_threshold_pct: float = 40.0,
    concentration_warning_threshold_pct: float = 25.0,
) -> RuleVerdict:
    triggered: list[str] = []
    metrics: dict[str, float] = {
        "expense_ratio": expense_ratio,
        "category_median_expense_ratio": category_median_expense_ratio,
        "category_rank_percentile": category_rank_percentile,
        "fund_xirr_pct": fund_xirr_pct,
        "category_median_xirr_pct": category_median_xirr_pct,
        "overlap_pct_with_other_holdings": overlap_pct_with_other_holdings,
        "concentration_pct_of_portfolio": concentration_pct_of_portfolio,
    }
    if sharpe_ratio is not None:
        metrics["sharpe_ratio"] = sharpe_ratio

    expense_outlier_threshold = category_median_expense_ratio + (
        expense_ratio_outlier_std_devs * category_expense_ratio_std_dev
    )
    is_expensive_outlier = expense_ratio > expense_outlier_threshold
    is_bottom_quartile = category_rank_percentile < 25
    is_underperforming = fund_xirr_pct < category_median_xirr_pct - 2.0
    is_high_overlap = overlap_pct_with_other_holdings > overlap_warning_threshold_pct
    is_overconcentrated = concentration_pct_of_portfolio > concentration_warning_threshold_pct
    is_top_performer = category_rank_percentile >= 90 and fund_xirr_pct > category_median_xirr_pct + 3.0

    # Exit: consistently bad on cost AND performance AND fund quality.
    if is_expensive_outlier and is_bottom_quartile and is_underperforming:
        triggered += ["expensive_outlier", "bottom_quartile", "underperforming"]
        return RuleVerdict("exit", triggered, metrics, confidence=0.85)

    # Switch: expensive + underperforming, but not necessarily bottom quartile
    # (a cheaper/better fund in the same category is a like-for-like swap).
    if is_expensive_outlier and is_underperforming:
        triggered += ["expensive_outlier", "underperforming"]
        return RuleVerdict("switch", triggered, metrics, confidence=0.7)

    # Reduce: high overlap with existing holdings, or overconcentration —
    # not a quality problem with the fund itself, a portfolio-construction one.
    if is_high_overlap or is_overconcentrated:
        if is_high_overlap:
            triggered.append("high_overlap")
        if is_overconcentrated:
            triggered.append("overconcentrated")
        return RuleVerdict("reduce", triggered, metrics, confidence=0.65)

    # Increase: clear top performer, cheap-ish, not already overconcentrated.
    if is_top_performer and not is_expensive_outlier and not is_overconcentrated:
        triggered += ["top_performer"]
        return RuleVerdict("increase", triggered, metrics, confidence=0.6)

    return RuleVerdict("keep", ["no_rule_triggered"], metrics, confidence=0.5)
