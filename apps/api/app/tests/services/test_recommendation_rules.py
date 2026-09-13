from __future__ import annotations

from app.services.recommendation_rules import evaluate_holding


def test_exit_when_expensive_bottom_quartile_and_underperforming():
    verdict = evaluate_holding(
        expense_ratio=2.5,
        category_median_expense_ratio=1.0,
        category_rank_percentile=10,
        fund_xirr_pct=6.0,
        category_median_xirr_pct=12.0,
        overlap_pct_with_other_holdings=5.0,
        concentration_pct_of_portfolio=5.0,
    )
    assert verdict.action == "exit"
    assert "expensive_outlier" in verdict.triggered_rules


def test_switch_when_expensive_and_underperforming_but_not_bottom_quartile():
    verdict = evaluate_holding(
        expense_ratio=2.2,
        category_median_expense_ratio=1.0,
        category_rank_percentile=50,
        fund_xirr_pct=8.0,
        category_median_xirr_pct=12.0,
        overlap_pct_with_other_holdings=5.0,
        concentration_pct_of_portfolio=5.0,
    )
    assert verdict.action == "switch"


def test_reduce_on_high_overlap():
    verdict = evaluate_holding(
        expense_ratio=1.0,
        category_median_expense_ratio=1.0,
        category_rank_percentile=60,
        fund_xirr_pct=12.0,
        category_median_xirr_pct=12.0,
        overlap_pct_with_other_holdings=55.0,
        concentration_pct_of_portfolio=5.0,
    )
    assert verdict.action == "reduce"
    assert "high_overlap" in verdict.triggered_rules


def test_reduce_on_overconcentration():
    verdict = evaluate_holding(
        expense_ratio=1.0,
        category_median_expense_ratio=1.0,
        category_rank_percentile=60,
        fund_xirr_pct=12.0,
        category_median_xirr_pct=12.0,
        overlap_pct_with_other_holdings=5.0,
        concentration_pct_of_portfolio=40.0,
    )
    assert verdict.action == "reduce"
    assert "overconcentrated" in verdict.triggered_rules


def test_increase_for_clear_top_performer():
    verdict = evaluate_holding(
        expense_ratio=0.8,
        category_median_expense_ratio=1.0,
        category_rank_percentile=95,
        fund_xirr_pct=18.0,
        category_median_xirr_pct=12.0,
        overlap_pct_with_other_holdings=5.0,
        concentration_pct_of_portfolio=5.0,
    )
    assert verdict.action == "increase"


def test_keep_when_nothing_triggers():
    verdict = evaluate_holding(
        expense_ratio=1.0,
        category_median_expense_ratio=1.0,
        category_rank_percentile=55,
        fund_xirr_pct=12.0,
        category_median_xirr_pct=12.0,
        overlap_pct_with_other_holdings=5.0,
        concentration_pct_of_portfolio=5.0,
    )
    assert verdict.action == "keep"
