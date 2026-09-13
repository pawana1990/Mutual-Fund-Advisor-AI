"""Goal planning math: required-SIP annuity formula + Monte Carlo
probability-of-success projection, backing the Goal Planning Agent."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class GoalInputs:
    target_amount: float
    years_remaining: float
    current_value: float
    assumed_annual_return_pct: float  # e.g. 11.0
    step_up_pct_per_year: float = 0.0  # SIP step-up, e.g. 10.0 for a 10%/yr increase


def required_monthly_sip(inputs: GoalInputs) -> float:
    """Future value of a growing annuity (monthly SIP with annual step-up)
    plus the future value of the current corpus must equal the target.
    Solved via bisection on the initial monthly SIP amount — closed form
    for a step-up annuity is unwieldy; bisection is exact enough for a
    monetary answer and trivially testable."""
    months = int(round(inputs.years_remaining * 12))
    if months <= 0:
        raise ValueError("years_remaining must be positive")
    monthly_rate = (1 + inputs.assumed_annual_return_pct / 100) ** (1 / 12) - 1

    fv_current_corpus = inputs.current_value * (1 + monthly_rate) ** months
    remaining_target = inputs.target_amount - fv_current_corpus
    if remaining_target <= 0:
        return 0.0  # goal already funded by existing corpus

    def fv_of_sip(monthly_sip: float) -> float:
        total = 0.0
        sip = monthly_sip
        for month in range(months):
            if month > 0 and month % 12 == 0:
                sip *= 1 + inputs.step_up_pct_per_year / 100
            months_of_growth = months - month
            total += sip * (1 + monthly_rate) ** months_of_growth
        return total

    lo, hi = 0.0, max(remaining_target, 1.0)
    for _ in range(60):
        mid = (lo + hi) / 2
        if fv_of_sip(mid) < remaining_target:
            lo = mid
        else:
            hi = mid
    return round(hi, 2)


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    percentiles: dict[int, dict[int, float]]  # percentile -> {year_offset: value}
    probability_of_success_pct: float


def monte_carlo_projection(
    *,
    current_value: float,
    monthly_contribution: float,
    years: float,
    target_amount: float,
    expected_annual_return_pct: float,
    annual_volatility_pct: float,
    simulations: int = 5_000,
    seed: int | None = 42,
) -> MonteCarloResult:
    """Simulate `simulations` random paths of monthly returns (drawn from a
    normal distribution parameterized by the fund/portfolio's historical
    mean+volatility) to produce a percentile fan chart and a probability of
    reaching `target_amount` by `years` from now.
    """
    if years <= 0:
        raise ValueError("years must be positive")
    rng = np.random.default_rng(seed)
    months = int(round(years * 12))
    monthly_mean = (1 + expected_annual_return_pct / 100) ** (1 / 12) - 1
    monthly_std = (annual_volatility_pct / 100) / np.sqrt(12)

    # shape: (simulations, months)
    monthly_returns = rng.normal(loc=monthly_mean, scale=monthly_std, size=(simulations, months))

    values = np.full(simulations, current_value, dtype=float)
    # Track value at each year-end for the fan chart.
    yearly_values: list[np.ndarray] = [values.copy()]
    for month in range(months):
        values = values * (1 + monthly_returns[:, month]) + monthly_contribution
        if (month + 1) % 12 == 0:
            yearly_values.append(values.copy())

    percentiles_requested = [10, 25, 50, 75, 90]
    percentile_series: dict[int, dict[int, float]] = {p: {} for p in percentiles_requested}
    for year_offset, year_values in enumerate(yearly_values):
        for p in percentiles_requested:
            percentile_series[p][year_offset] = round(float(np.percentile(year_values, p)), 2)

    probability_of_success = float(np.mean(values >= target_amount)) * 100
    return MonteCarloResult(
        percentiles=percentile_series,
        probability_of_success_pct=round(probability_of_success, 2),
    )
