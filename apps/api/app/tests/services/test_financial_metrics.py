"""Unit + property tests for the pure financial-math engine.

These are the tests that matter most in this codebase: every AI
recommendation is only as trustworthy as the numbers computed here.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.financial_metrics import (
    CashFlow,
    FinancialMetricsError,
    alpha,
    allocation_breakdown,
    beta,
    cagr,
    concentration_risk_flag,
    herfindahl_hirschman_index,
    max_drawdown,
    periodic_returns,
    sharpe_ratio,
    sortino_ratio,
    volatility,
    xirr,
)


class TestXIRR:
    def test_single_investment_matches_closed_form_cagr(self):
        # Invest 100,000 on day 0, redeem 150,000 exactly 2 years later.
        # This degenerates to a simple compounding problem: XIRR must equal
        # the closed-form (150000/100000)^(1/2) - 1.
        start = date(2023, 1, 1)
        end = date(2025, 1, 1)
        years = (end - start).days / 365.0
        cashflows = [CashFlow(start, -100_000), CashFlow(end, 150_000)]
        result = xirr(cashflows)
        expected = (150_000 / 100_000) ** (1 / years) - 1
        assert result == pytest.approx(expected, abs=1e-4)

    def test_monthly_sip_positive_return(self):
        # 12 monthly SIPs of 10,000, redeemed for 135,000 a year after the
        # first installment — should yield a healthy positive XIRR.
        start = date(2024, 1, 1)
        cashflows = [CashFlow(start + timedelta(days=30 * i), -10_000) for i in range(12)]
        cashflows.append(CashFlow(start + timedelta(days=395), 135_000))
        result = xirr(cashflows)
        assert 0.05 < result < 0.60  # sanity band, not a tight assertion

    def test_requires_sign_change(self):
        with pytest.raises(FinancialMetricsError):
            xirr([CashFlow(date(2024, 1, 1), -100), CashFlow(date(2024, 6, 1), -50)])

    def test_requires_at_least_two_cashflows(self):
        with pytest.raises(FinancialMetricsError):
            xirr([CashFlow(date(2024, 1, 1), -100)])

    @given(
        principal=st.floats(min_value=1_000, max_value=10_000_000, allow_nan=False),
        multiple=st.floats(min_value=1.01, max_value=5.0, allow_nan=False),
        days=st.integers(min_value=30, max_value=3650),
    )
    @settings(max_examples=50, deadline=None)
    def test_xirr_scale_invariant(self, principal: float, multiple: float, days: int):
        """XIRR of a two-cashflow series depends only on the *ratio* of
        inflow to outflow and the elapsed time — not the absolute scale."""
        start = date(2020, 1, 1)
        end = start + timedelta(days=days)
        r1 = xirr([CashFlow(start, -principal), CashFlow(end, principal * multiple)])
        r2 = xirr([CashFlow(start, -principal * 7), CashFlow(end, principal * 7 * multiple)])
        assert r1 == pytest.approx(r2, abs=1e-5)


class TestCAGR:
    def test_doubling_in_seven_years_is_about_ten_percent(self):
        # Rule of 72 sanity check: doubling in ~7.2 years ~ 10% CAGR.
        result = cagr(100_000, 200_000, 7.2)
        assert result == pytest.approx(0.10, abs=0.005)

    def test_rejects_non_positive_begin_value(self):
        with pytest.raises(FinancialMetricsError):
            cagr(0, 100, 1)

    def test_rejects_non_positive_years(self):
        with pytest.raises(FinancialMetricsError):
            cagr(100, 200, 0)


class TestReturnSeries:
    def test_periodic_returns_basic(self):
        result = periodic_returns([100, 110, 121])
        assert result == pytest.approx([0.10, 0.10])

    def test_rejects_non_positive_prices(self):
        with pytest.raises(FinancialMetricsError):
            periodic_returns([100, -5, 90])

    def test_volatility_zero_variance_series(self):
        assert volatility([0.01] * 12, periods_per_year=12) == pytest.approx(0.0, abs=1e-9)

    def test_volatility_annualization_scales_by_sqrt_periods(self):
        monthly = [0.01, -0.02, 0.03, -0.01, 0.02, -0.015, 0.01, 0.0, 0.02, -0.01, 0.015, -0.005]
        monthly_std = volatility(monthly, periods_per_year=1, annualized=False)
        annualized = volatility(monthly, periods_per_year=12)
        assert annualized == pytest.approx(monthly_std * math.sqrt(12))


class TestBetaAlpha:
    def test_beta_of_identical_series_is_one(self):
        benchmark = [0.01, 0.02, -0.01, 0.03, -0.02, 0.015]
        assert beta(benchmark, benchmark) == pytest.approx(1.0, abs=1e-9)

    def test_beta_of_double_leveraged_series_is_two(self):
        benchmark = [0.01, 0.02, -0.01, 0.03, -0.02, 0.015]
        leveraged = [2 * r for r in benchmark]
        assert beta(leveraged, benchmark) == pytest.approx(2.0, abs=1e-9)

    def test_beta_rejects_mismatched_lengths(self):
        with pytest.raises(FinancialMetricsError):
            beta([0.01, 0.02], [0.01, 0.02, 0.03])

    def test_alpha_zero_when_fund_matches_capm_expectation(self):
        # If fund return exactly equals CAPM's expected return, alpha == 0.
        risk_free = 0.06
        benchmark_return = 0.14
        beta_value = 1.2
        expected_fund_return = risk_free + beta_value * (benchmark_return - risk_free)
        result = alpha(expected_fund_return, benchmark_return, beta_value, risk_free)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_alpha_positive_when_fund_beats_capm(self):
        result = alpha(0.20, 0.14, 1.0, 0.06)
        # expected = 0.06 + 1.0*(0.14-0.06) = 0.14; alpha = 0.20 - 0.14 = 0.06
        assert result == pytest.approx(0.06, abs=1e-9)


class TestSharpeSortino:
    def test_sharpe_higher_for_less_volatile_equal_mean_series(self):
        low_vol = [0.01, 0.011, 0.009, 0.0105, 0.0095, 0.010]
        high_vol = [0.03, -0.01, 0.02, 0.0, 0.02, -0.005]
        # normalize both to same mean for a fair comparison
        rf = 0.0
        s_low = sharpe_ratio(low_vol, risk_free_periodic_rate=rf)
        s_high = sharpe_ratio(high_vol, risk_free_periodic_rate=rf)
        assert s_low > s_high

    def test_sortino_ignores_upside_volatility(self):
        # Series A has big upside swings but never goes negative excess;
        # Series B has the same std dev but with downside swings.
        rf = 0.0
        series_a = [0.05, 0.01, 0.06, 0.01, 0.05, 0.01]  # all >= rf
        series_b = [0.05, -0.03, 0.06, -0.03, 0.05, -0.03]
        sortino_a = sortino_ratio(series_a, risk_free_periodic_rate=rf)
        sortino_b = sortino_ratio(series_b, risk_free_periodic_rate=rf)
        assert sortino_a == math.inf
        assert sortino_b < sortino_a

    def test_sharpe_zero_variance_positive_mean_is_inf(self):
        assert sharpe_ratio([0.02] * 6, risk_free_periodic_rate=0.0) == math.inf


class TestMaxDrawdown:
    def test_known_drawdown_sequence(self):
        # Peak at 120, trough at 90 => drawdown = (90-120)/120 = -25%
        prices = [100, 110, 120, 100, 90, 95, 105]
        assert max_drawdown(prices) == pytest.approx(-0.25, abs=1e-9)

    def test_monotonically_increasing_series_has_zero_drawdown(self):
        assert max_drawdown([100, 105, 110, 120]) == pytest.approx(0.0, abs=1e-9)


class TestAllocationAndConcentration:
    def test_allocation_breakdown_sums_to_100(self):
        pct = allocation_breakdown({"equity": 65_000, "debt": 25_000, "gold": 10_000})
        assert sum(pct.values()) == pytest.approx(100.0, abs=0.01)

    def test_hhi_fully_concentrated_is_10000(self):
        assert herfindahl_hirschman_index({"only_fund": 100_000}) == pytest.approx(10_000.0)

    def test_hhi_evenly_split_four_ways_is_2500(self):
        values = {f"fund_{i}": 25_000 for i in range(4)}
        assert herfindahl_hirschman_index(values) == pytest.approx(2_500.0, abs=1.0)

    def test_concentration_flag_detects_single_dominant_holding(self):
        flagged = concentration_risk_flag({"HDFC Top 100": 60_000, "Axis Bluechip": 40_000}, threshold_pct=50.0)
        assert flagged == ["HDFC Top 100"]

    def test_concentration_flag_empty_when_diversified(self):
        values = {f"fund_{i}": 20_000 for i in range(5)}
        assert concentration_risk_flag(values, threshold_pct=25.0) == []
