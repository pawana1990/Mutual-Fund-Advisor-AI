"""Core, dependency-free financial mathematics used by every downstream
agent (Portfolio Analysis, Risk Analysis, Recommendation).

Every function here is pure (no I/O, no LLM) and unit-tested against
hand-verified fixtures in `app/tests/services/test_financial_metrics.py`.
This is the one place "the numbers" live — agents explain these values in
plain English, they never invent their own.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

DAYS_IN_YEAR = 365.0
TRADING_DAYS_PER_YEAR = 252


class FinancialMetricsError(ValueError):
    """Raised when an input series is unsuitable for the requested metric
    (e.g. all-zero cashflows for XIRR, empty return series for Sharpe)."""


@dataclass(frozen=True, slots=True)
class CashFlow:
    when: date
    amount: float  # negative = outflow (investment), positive = inflow (redemption/current value)


# ---------------------------------------------------------------------------
# XIRR — Extended Internal Rate of Return for irregular cashflows
# ---------------------------------------------------------------------------

def _npv(rate: float, cashflows: list[CashFlow], t0: date) -> float:
    if rate <= -1.0:
        # Guard against a domain error in the fractional power below.
        rate = -0.999999
    total = 0.0
    for cf in cashflows:
        years = (cf.when - t0).days / DAYS_IN_YEAR
        total += cf.amount / ((1.0 + rate) ** years)
    return total


def _npv_derivative(rate: float, cashflows: list[CashFlow], t0: date) -> float:
    if rate <= -1.0:
        rate = -0.999999
    total = 0.0
    for cf in cashflows:
        years = (cf.when - t0).days / DAYS_IN_YEAR
        if years == 0:
            continue
        total += -years * cf.amount / ((1.0 + rate) ** (years + 1))
    return total


def xirr(cashflows: list[CashFlow], *, guess: float = 0.1, tol: float = 1e-7, max_iter: int = 200) -> float:
    """Solve for the annualized rate `r` such that NPV(cashflows, r) == 0.

    Requires at least one negative and one positive cashflow. Uses
    Newton-Raphson with a bisection fallback (bounded to [-0.9999, 100.0])
    for cases where Newton fails to converge or diverges — irregular SIP +
    lump-sum + redemption cashflow series are not always well-behaved for
    Newton alone.
    """
    if len(cashflows) < 2:
        raise FinancialMetricsError("XIRR requires at least two cashflows")
    if not any(cf.amount < 0 for cf in cashflows) or not any(cf.amount > 0 for cf in cashflows):
        raise FinancialMetricsError("XIRR requires both an outflow and an inflow")

    ordered = sorted(cashflows, key=lambda cf: cf.when)
    t0 = ordered[0].when

    rate = guess
    for _ in range(max_iter):
        f = _npv(rate, ordered, t0)
        if abs(f) < tol:
            return rate
        fprime = _npv_derivative(rate, ordered, t0)
        if fprime == 0:
            break
        next_rate = rate - f / fprime
        if not math.isfinite(next_rate):
            break
        rate = next_rate

    # Fallback: bisection over a wide, sane bound.
    lo, hi = -0.9999, 100.0
    f_lo, f_hi = _npv(lo, ordered, t0), _npv(hi, ordered, t0)
    if f_lo * f_hi > 0:
        raise FinancialMetricsError(
            "XIRR did not converge — cashflow series may be pathological (e.g. no sign change in NPV)"
        )
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, ordered, t0)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


# ---------------------------------------------------------------------------
# CAGR
# ---------------------------------------------------------------------------

def cagr(begin_value: float, end_value: float, years: float) -> float:
    """Compound Annual Growth Rate. `years` may be fractional."""
    if begin_value <= 0:
        raise FinancialMetricsError("CAGR requires a positive beginning value")
    if years <= 0:
        raise FinancialMetricsError("CAGR requires a positive time period")
    return (end_value / begin_value) ** (1.0 / years) - 1.0


# ---------------------------------------------------------------------------
# Return-series helpers
# ---------------------------------------------------------------------------

def periodic_returns(prices: list[float]) -> np.ndarray:
    """Simple period-over-period returns from a price/NAV series."""
    if len(prices) < 2:
        raise FinancialMetricsError("Need at least two price points to compute returns")
    arr = np.asarray(prices, dtype=float)
    if np.any(arr <= 0):
        raise FinancialMetricsError("Prices must be strictly positive")
    return arr[1:] / arr[:-1] - 1.0


def annualize_return(mean_periodic_return: float, periods_per_year: int) -> float:
    return (1.0 + mean_periodic_return) ** periods_per_year - 1.0


def annualize_volatility(periodic_std: float, periods_per_year: int) -> float:
    return periodic_std * math.sqrt(periods_per_year)


def volatility(returns: np.ndarray | list[float], *, periods_per_year: int = 12, annualized: bool = True) -> float:
    """Standard deviation of returns (sample std, ddof=1)."""
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        raise FinancialMetricsError("Need at least two returns to compute volatility")
    std = float(np.std(arr, ddof=1))
    return annualize_volatility(std, periods_per_year) if annualized else std


# Backwards-friendly alias matching the product spec's terminology.
standard_deviation = volatility


# ---------------------------------------------------------------------------
# Beta / Alpha
# ---------------------------------------------------------------------------

def beta(fund_returns: np.ndarray | list[float], benchmark_returns: np.ndarray | list[float]) -> float:
    """Beta = Cov(fund, benchmark) / Var(benchmark)."""
    f = np.asarray(fund_returns, dtype=float)
    b = np.asarray(benchmark_returns, dtype=float)
    if f.shape != b.shape or f.size < 2:
        raise FinancialMetricsError("Fund and benchmark return series must be equal length and >= 2 points")
    cov_matrix = np.cov(f, b, ddof=1)
    benchmark_var = cov_matrix[1, 1]
    if benchmark_var == 0:
        raise FinancialMetricsError("Benchmark variance is zero — beta is undefined")
    return float(cov_matrix[0, 1] / benchmark_var)


def alpha(
    fund_annual_return: float,
    benchmark_annual_return: float,
    beta_value: float,
    risk_free_annual_rate: float,
) -> float:
    """Jensen's Alpha = fund_return - [risk_free + beta * (benchmark_return - risk_free)]."""
    expected_return = risk_free_annual_rate + beta_value * (benchmark_annual_return - risk_free_annual_rate)
    return fund_annual_return - expected_return


# ---------------------------------------------------------------------------
# Sharpe / Sortino
# ---------------------------------------------------------------------------

def sharpe_ratio(
    returns: np.ndarray | list[float],
    *,
    risk_free_periodic_rate: float,
    periods_per_year: int = 12,
) -> float:
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        raise FinancialMetricsError("Need at least two returns to compute Sharpe ratio")
    excess = arr - risk_free_periodic_rate
    std = float(np.std(excess, ddof=1))
    if std == 0:
        return math.inf if float(np.mean(excess)) > 0 else 0.0
    periodic_sharpe = float(np.mean(excess)) / std
    return periodic_sharpe * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: np.ndarray | list[float],
    *,
    risk_free_periodic_rate: float,
    periods_per_year: int = 12,
) -> float:
    """Like Sharpe, but only penalizes downside deviation (returns below the
    risk-free/target rate) — a fund with big upside swings and no downside
    is NOT penalized, unlike with plain volatility."""
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        raise FinancialMetricsError("Need at least two returns to compute Sortino ratio")
    excess = arr - risk_free_periodic_rate
    downside = excess[excess < 0]
    if downside.size == 0:
        return math.inf if float(np.mean(excess)) > 0 else 0.0
    downside_deviation = float(np.sqrt(np.mean(downside**2)))
    if downside_deviation == 0:
        return 0.0
    periodic_sortino = float(np.mean(excess)) / downside_deviation
    return periodic_sortino * math.sqrt(periods_per_year)


# ---------------------------------------------------------------------------
# Maximum drawdown
# ---------------------------------------------------------------------------

def max_drawdown(prices: np.ndarray | list[float]) -> float:
    """Largest peak-to-trough decline over the series, expressed as a
    negative percentage (e.g. -0.32 == a 32% drawdown)."""
    arr = np.asarray(prices, dtype=float)
    if arr.size < 2:
        raise FinancialMetricsError("Need at least two price points to compute max drawdown")
    running_max = np.maximum.accumulate(arr)
    drawdowns = (arr - running_max) / running_max
    return float(np.min(drawdowns))


# ---------------------------------------------------------------------------
# Portfolio-level allocation & concentration
# ---------------------------------------------------------------------------

def allocation_breakdown(values_by_key: dict[str, float]) -> dict[str, float]:
    """Turns `{key: value}` into `{key: percent_of_total}`, rounded to 2dp,
    guaranteed to sum to ~100 (last bucket absorbs rounding remainder)."""
    total = sum(values_by_key.values())
    if total <= 0:
        raise FinancialMetricsError("Cannot compute allocation breakdown for non-positive total")
    keys = list(values_by_key.keys())
    pct = {k: round(values_by_key[k] / total * 100, 2) for k in keys}
    if keys:
        drift = round(100 - sum(pct.values()), 2)
        pct[keys[-1]] = round(pct[keys[-1]] + drift, 2)
    return pct


def herfindahl_hirschman_index(values_by_key: dict[str, float]) -> float:
    """HHI (0-10000 scale) — used to flag concentration risk. > 2500 is
    conventionally "highly concentrated" (e.g. in a single AMC/sector)."""
    total = sum(values_by_key.values())
    if total <= 0:
        raise FinancialMetricsError("Cannot compute HHI for non-positive total")
    return sum((v / total * 100) ** 2 for v in values_by_key.values())


def concentration_risk_flag(values_by_key: dict[str, float], *, threshold_pct: float = 25.0) -> list[str]:
    """Returns the keys (e.g. fund names, AMCs, sectors) whose share of the
    total exceeds `threshold_pct` — a simple, explainable concentration
    check the Recommendation Agent cites directly in `supporting_metrics`."""
    pct = allocation_breakdown(values_by_key)
    return [k for k, v in pct.items() if v > threshold_pct]
