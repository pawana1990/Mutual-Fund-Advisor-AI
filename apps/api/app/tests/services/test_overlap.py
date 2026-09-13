from __future__ import annotations

import pytest

from app.services.overlap import FundStockBasket, build_overlap_report, pairwise_stock_overlap


def test_pairwise_overlap_uses_min_weight_method():
    a = FundStockBasket(
        fund_id="a", fund_name="Fund A", amc="AMC1",
        stock_weights={"HDFC Bank": 8.0, "Infosys": 6.0, "Reliance": 5.0},
        sector_weights={"Financials": 40.0, "IT": 30.0, "Energy": 30.0},
    )
    b = FundStockBasket(
        fund_id="b", fund_name="Fund B", amc="AMC2",
        stock_weights={"HDFC Bank": 5.0, "Infosys": 9.0, "TCS": 7.0},
        sector_weights={"Financials": 30.0, "IT": 70.0},
    )
    result = pairwise_stock_overlap(a, b)
    # min(8,5) + min(6,9) = 5 + 6 = 11
    assert result.overlap_pct == pytest.approx(11.0)
    assert set(result.common_holdings) == {"HDFC Bank", "Infosys"}


def test_identical_funds_have_full_overlap():
    a = FundStockBasket(
        fund_id="a", fund_name="Fund A", amc="AMC1",
        stock_weights={"HDFC Bank": 10.0, "Infosys": 10.0},
        sector_weights={"Financials": 50.0, "IT": 50.0},
    )
    b = FundStockBasket(
        fund_id="b", fund_name="Fund B (clone)", amc="AMC1",
        stock_weights={"HDFC Bank": 10.0, "Infosys": 10.0},
        sector_weights={"Financials": 50.0, "IT": 50.0},
    )
    result = pairwise_stock_overlap(a, b)
    assert result.overlap_pct == pytest.approx(20.0)


def test_build_overlap_report_flags_high_overlap_pairs():
    a = FundStockBasket("a", "Large Cap A", "AMC1", {"HDFC Bank": 9.0, "Infosys": 8.0}, {"Financials": 50, "IT": 50})
    b = FundStockBasket("b", "Large Cap B", "AMC1", {"HDFC Bank": 8.0, "Infosys": 7.0}, {"Financials": 50, "IT": 50})
    c = FundStockBasket("c", "Small Cap C", "AMC2", {"Tiny Co": 5.0}, {"Industrials": 100})

    report = build_overlap_report(
        [a, b, c],
        holding_values={"a": 100_000, "b": 100_000, "c": 50_000},
        pair_overlap_warning_threshold=10.0,
    )
    assert report.portfolio_overlap_pct > 0
    assert any(p.fund_a == "a" and p.fund_b == "b" for p in report.duplicate_pairs)
    assert "AMC1" in report.amc_concentration
    assert report.amc_hhi > 0


def test_no_overlap_when_funds_share_no_holdings():
    a = FundStockBasket("a", "Fund A", "AMC1", {"Stock1": 10.0}, {"IT": 100})
    b = FundStockBasket("b", "Fund B", "AMC2", {"Stock2": 10.0}, {"Financials": 100})
    report = build_overlap_report([a, b], holding_values={"a": 50_000, "b": 50_000})
    assert report.portfolio_overlap_pct == pytest.approx(0.0)
