from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.tax_calculator import (
    DEFAULT_TAX_RULES,
    FundAssetType,
    GainTerm,
    SaleLot,
    compute_tax_summary,
    find_tax_harvesting_opportunities,
)


def _lot(days_held: int, units: float, buy_nav: float, sell_nav: float, asset_type=FundAssetType.EQUITY) -> SaleLot:
    sell_date = date(2025, 3, 31)
    return SaleLot(
        fund_id="f1",
        asset_type=asset_type,
        buy_date=sell_date - timedelta(days=days_held),
        sell_date=sell_date,
        units=units,
        buy_nav=buy_nav,
        sell_nav=sell_nav,
    )


class TestGainTermClassification:
    def test_equity_held_over_12_months_is_long_term(self):
        lot = _lot(days_held=400, units=100, buy_nav=10, sell_nav=15)
        assert lot.gain_term() == GainTerm.LONG_TERM

    def test_equity_held_under_12_months_is_short_term(self):
        lot = _lot(days_held=200, units=100, buy_nav=10, sell_nav=15)
        assert lot.gain_term() == GainTerm.SHORT_TERM

    def test_debt_fund_always_short_term_regardless_of_holding_period(self):
        lot = _lot(days_held=1500, units=100, buy_nav=10, sell_nav=15, asset_type=FundAssetType.DEBT)
        assert lot.gain_term() == GainTerm.SHORT_TERM


class TestTaxSummary:
    def test_ltcg_within_exemption_is_untaxed(self):
        # Gain of 100,000 is fully within the 125,000 exemption.
        lot = _lot(days_held=400, units=10_000, buy_nav=10, sell_nav=20)
        summary = compute_tax_summary([lot])
        assert summary.ltcg == pytest.approx(100_000)
        assert summary.ltcg_tax == pytest.approx(0.0)
        assert summary.ltcg_exemption_remaining == pytest.approx(25_000)

    def test_ltcg_above_exemption_taxed_at_12_5_pct_on_excess_only(self):
        lot = _lot(days_held=400, units=10_000, buy_nav=10, sell_nav=30)  # gain = 200,000
        summary = compute_tax_summary([lot])
        taxable = 200_000 - DEFAULT_TAX_RULES.equity_ltcg_exemption
        assert summary.ltcg_tax == pytest.approx(taxable * DEFAULT_TAX_RULES.equity_ltcg_rate)

    def test_stcg_taxed_at_flat_20_pct(self):
        lot = _lot(days_held=100, units=1_000, buy_nav=10, sell_nav=15)  # gain = 5,000
        summary = compute_tax_summary([lot])
        assert summary.stcg_tax == pytest.approx(5_000 * 0.20)

    def test_debt_gain_taxed_at_slab_rate(self):
        lot = _lot(days_held=1500, units=1_000, buy_nav=10, sell_nav=15, asset_type=FundAssetType.DEBT)
        summary = compute_tax_summary([lot], debt_slab_rate=0.30)
        assert summary.stcg_tax == pytest.approx(5_000 * 0.30)

    def test_prior_realized_ltcg_reduces_remaining_exemption(self):
        lot = _lot(days_held=400, units=1_000, buy_nav=10, sell_nav=20)  # gain = 10,000
        summary = compute_tax_summary([lot], other_equity_ltcg_already_realized_this_fy=125_000)
        assert summary.ltcg_tax == pytest.approx(10_000 * DEFAULT_TAX_RULES.equity_ltcg_rate)


class TestHarvestingOpportunities:
    def test_finds_long_term_unrealized_gain_within_exemption(self):
        holdings = [
            {
                "holding_id": "h1",
                "fund_name": "HDFC Flexicap",
                "asset_type": "equity",
                "buy_date": date.today() - timedelta(days=500),
                "buy_nav": 50.0,
                "current_nav": 60.0,
                "units": 1000.0,  # unrealized gain = 10,000
            }
        ]
        opportunities = find_tax_harvesting_opportunities(holdings)
        assert len(opportunities) == 1
        assert opportunities[0].unrealized_gain == pytest.approx(10_000.0)
        assert opportunities[0].estimated_tax_saved == pytest.approx(10_000 * DEFAULT_TAX_RULES.equity_ltcg_rate)

    def test_ignores_short_term_and_loss_making_holdings(self):
        holdings = [
            {
                "holding_id": "h1",
                "fund_name": "Recent buy",
                "asset_type": "equity",
                "buy_date": date.today() - timedelta(days=90),
                "buy_nav": 50.0,
                "current_nav": 60.0,
                "units": 1000.0,
            },
            {
                "holding_id": "h2",
                "fund_name": "Loss maker",
                "asset_type": "equity",
                "buy_date": date.today() - timedelta(days=500),
                "buy_nav": 60.0,
                "current_nav": 50.0,
                "units": 1000.0,
            },
        ]
        assert find_tax_harvesting_opportunities(holdings) == []
