from __future__ import annotations

from app.services.health_score import HealthScoreInputs, compute_health_score


def _base_inputs(**overrides) -> HealthScoreInputs:
    defaults = dict(
        amc_values={"AMC A": 25_000, "AMC B": 25_000, "AMC C": 25_000, "AMC D": 25_000},
        sector_values={"IT": 20_000, "Financials": 20_000, "Healthcare": 20_000, "Energy": 20_000, "FMCG": 20_000},
        fund_count=8,
        portfolio_volatility_pct=14.0,
        portfolio_max_drawdown_pct=-18.0,
        risk_profile_volatility_tolerance_pct=14.0,
        portfolio_xirr_pct=13.0,
        category_median_xirr_pct=12.0,
        weighted_avg_expense_ratio_pct=0.8,
        category_median_expense_ratio_pct=1.0,
        avg_category_rank_percentile=80.0,
        unrealized_ltcg_within_exemption_pct=90.0,
        stcg_pct_of_total_gains=10.0,
        equity_pct=65.0,
        target_equity_pct=65.0,
        avg_goal_probability_of_success_pct=85.0,
    )
    defaults.update(overrides)
    return HealthScoreInputs(**defaults)


class TestHealthScore:
    def test_well_balanced_portfolio_scores_high(self):
        result = compute_health_score(_base_inputs())
        assert result.overall_score >= 70

    def test_concentrated_single_fund_scores_lower_diversification(self):
        concentrated = _base_inputs(amc_values={"Single AMC": 100_000}, sector_values={"IT": 100_000}, fund_count=1)
        diversified = _base_inputs()
        assert (
            compute_health_score(concentrated).diversification_score
            < compute_health_score(diversified).diversification_score
        )

    def test_high_expense_ratio_reduces_fees_score(self):
        expensive = _base_inputs(weighted_avg_expense_ratio_pct=2.5)
        cheap = _base_inputs(weighted_avg_expense_ratio_pct=0.3)
        assert compute_health_score(expensive).fees_score < compute_health_score(cheap).fees_score

    def test_large_drawdown_reduces_risk_score(self):
        crashed = _base_inputs(portfolio_max_drawdown_pct=-55.0)
        stable = _base_inputs(portfolio_max_drawdown_pct=-5.0)
        assert compute_health_score(crashed).risk_score < compute_health_score(stable).risk_score

    def test_allocation_drift_from_target_reduces_score(self):
        drifted = _base_inputs(equity_pct=95.0, target_equity_pct=60.0)
        on_target = _base_inputs(equity_pct=60.0, target_equity_pct=60.0)
        assert (
            compute_health_score(drifted).asset_allocation_score
            < compute_health_score(on_target).asset_allocation_score
        )

    def test_all_sub_scores_within_0_100(self):
        result = compute_health_score(_base_inputs())
        for value in (
            result.overall_score,
            result.diversification_score,
            result.risk_score,
            result.returns_score,
            result.fees_score,
            result.fund_quality_score,
            result.tax_efficiency_score,
            result.asset_allocation_score,
            result.goal_readiness_score,
        ):
            assert 0 <= value <= 100
