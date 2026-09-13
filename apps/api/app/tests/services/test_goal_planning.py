from __future__ import annotations

import pytest

from app.services.goal_planning import GoalInputs, monte_carlo_projection, required_monthly_sip


class TestRequiredMonthlySip:
    def test_zero_when_current_corpus_already_covers_target(self):
        inputs = GoalInputs(
            target_amount=100_000,
            years_remaining=5,
            current_value=1_000_000,
            assumed_annual_return_pct=10,
        )
        assert required_monthly_sip(inputs) == 0.0

    def test_positive_sip_grows_corpus_to_target(self):
        inputs = GoalInputs(
            target_amount=5_000_000,
            years_remaining=15,
            current_value=200_000,
            assumed_annual_return_pct=12,
        )
        sip = required_monthly_sip(inputs)
        assert sip > 0
        # Sanity: verify forward simulation of this SIP lands near the target.
        monthly_rate = (1 + 0.12) ** (1 / 12) - 1
        months = 15 * 12
        fv = inputs.current_value * (1 + monthly_rate) ** months
        fv += sum(sip * (1 + monthly_rate) ** (months - m) for m in range(months))
        assert fv == pytest.approx(inputs.target_amount, rel=0.01)

    def test_step_up_reduces_required_initial_sip(self):
        base = GoalInputs(target_amount=5_000_000, years_remaining=15, current_value=0, assumed_annual_return_pct=12)
        stepped = GoalInputs(
            target_amount=5_000_000,
            years_remaining=15,
            current_value=0,
            assumed_annual_return_pct=12,
            step_up_pct_per_year=10,
        )
        assert required_monthly_sip(stepped) < required_monthly_sip(base)


class TestMonteCarloProjection:
    def test_higher_expected_return_increases_success_probability(self):
        common = dict(
            current_value=500_000,
            monthly_contribution=20_000,
            years=10,
            target_amount=6_000_000,
            annual_volatility_pct=15,
            simulations=2000,
            seed=1,
        )
        low = monte_carlo_projection(expected_annual_return_pct=8, **common)
        high = monte_carlo_projection(expected_annual_return_pct=16, **common)
        assert high.probability_of_success_pct > low.probability_of_success_pct

    def test_percentile_ordering_is_monotonic_at_final_year(self):
        result = monte_carlo_projection(
            current_value=100_000,
            monthly_contribution=10_000,
            years=5,
            target_amount=1_000_000,
            expected_annual_return_pct=12,
            annual_volatility_pct=18,
            simulations=2000,
            seed=7,
        )
        final_year = max(result.percentiles[50].keys())
        p10 = result.percentiles[10][final_year]
        p50 = result.percentiles[50][final_year]
        p90 = result.percentiles[90][final_year]
        assert p10 <= p50 <= p90

    def test_probability_bounded_between_0_and_100(self):
        result = monte_carlo_projection(
            current_value=0,
            monthly_contribution=1_000,
            years=1,
            target_amount=10_000_000,  # unreachable target
            expected_annual_return_pct=10,
            annual_volatility_pct=15,
            simulations=500,
            seed=3,
        )
        assert 0.0 <= result.probability_of_success_pct <= 100.0
