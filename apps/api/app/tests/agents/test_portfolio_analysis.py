from __future__ import annotations

from app.agents.portfolio_analysis import run


def _holding(**overrides) -> dict:
    base = dict(
        holding_id="h1", fund_id="f1", fund_name="HDFC Top 100", amc="HDFC",
        category="Large Cap", asset_type="equity", units=1000.0,
        invested_value=100_000.0, current_value=130_000.0, avg_cost_nav=100.0,
        current_nav=130.0, expense_ratio=1.0, buy_date="2023-01-01",
    )
    base.update(overrides)
    return base


def test_empty_holdings_returns_zeroed_metrics():
    result = run({"holdings": []})
    metrics = result["portfolio_metrics"]
    assert metrics["invested_value"] == 0.0
    assert metrics["current_value"] == 0.0


def test_computes_invested_and_current_value():
    result = run({"holdings": [_holding()]})
    metrics = result["portfolio_metrics"]
    assert metrics["invested_value"] == 100_000.0
    assert metrics["current_value"] == 130_000.0
    assert metrics["absolute_return_pct"] == 30.0


def test_positive_xirr_for_profitable_holding():
    result = run({"holdings": [_holding()]})
    assert result["portfolio_metrics"]["xirr"] > 0


def test_asset_allocation_splits_equity_and_debt():
    holdings = [
        _holding(fund_id="f1", category="Large Cap", current_value=60_000, invested_value=50_000),
        _holding(fund_id="f2", category="Debt", current_value=40_000, invested_value=35_000),
    ]
    result = run({"holdings": holdings})
    allocation = result["portfolio_metrics"]["asset_allocation"]
    assert allocation["equity"] == 60.0
    assert allocation["debt"] == 40.0


def test_concentration_flag_for_dominant_single_holding():
    holdings = [
        _holding(fund_id="f1", fund_name="Dominant Fund", current_value=80_000, invested_value=70_000),
        _holding(fund_id="f2", fund_name="Small Fund", current_value=20_000, invested_value=18_000),
    ]
    result = run({"holdings": holdings})
    assert "Dominant Fund" in result["portfolio_metrics"]["concentration_flags"]
