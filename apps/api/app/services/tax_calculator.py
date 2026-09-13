"""Indian mutual-fund capital-gains tax rules, kept isolated in one file so a
tax-law change (e.g. a Budget revision to LTCG rates/thresholds) is a
one-file diff. Rules encoded reflect the framework effective from the
FY2024-25 Union Budget (equity LTCG @ 12.5% above a ₹1.25L annual exemption,
STCG @ 20%; debt funds taxed at slab rate as short-term regardless of
holding period, post the April-2023 amendment). Override the constants below
via `TaxRules` if a subsequent Budget changes them — never hardcode a new
rate inline in a call site.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class FundAssetType(StrEnum):
    EQUITY = "equity"  # >= 65% domestic equity allocation
    DEBT = "debt"
    HYBRID_EQUITY_ORIENTED = "hybrid_equity_oriented"  # treated as equity for tax
    HYBRID_DEBT_ORIENTED = "hybrid_debt_oriented"  # treated as debt for tax


class GainTerm(StrEnum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


@dataclass(frozen=True, slots=True)
class TaxRules:
    equity_long_term_holding_months: int = 12
    debt_is_always_short_term: bool = True  # post Finance Act 2023 amendment

    equity_stcg_rate: float = 0.20
    equity_ltcg_rate: float = 0.125
    equity_ltcg_exemption: float = 125_000.0  # per financial year, across all equity LTCG

    # Debt/non-equity gains are added to income and taxed at slab rate; the
    # caller supplies the investor's marginal slab rate since we don't know
    # their other income here.
    default_slab_rate_for_debt: float = 0.30


DEFAULT_TAX_RULES = TaxRules()


@dataclass(frozen=True, slots=True)
class SaleLot:
    """One redemption event, matched against its acquisition lot (FIFO)."""

    fund_id: str
    asset_type: FundAssetType
    buy_date: date
    sell_date: date
    units: float
    buy_nav: float
    sell_nav: float
    exit_load_pct: float = 0.0

    @property
    def holding_months(self) -> float:
        return (self.sell_date - self.buy_date).days / 30.44

    @property
    def gross_gain(self) -> float:
        return (self.sell_nav - self.buy_nav) * self.units

    @property
    def exit_load_amount(self) -> float:
        return self.sell_nav * self.units * self.exit_load_pct / 100.0

    @property
    def net_gain(self) -> float:
        return self.gross_gain - self.exit_load_amount

    def gain_term(self, rules: TaxRules = DEFAULT_TAX_RULES) -> GainTerm:
        if self.asset_type in (FundAssetType.DEBT, FundAssetType.HYBRID_DEBT_ORIENTED) and rules.debt_is_always_short_term:
            return GainTerm.SHORT_TERM
        return (
            GainTerm.LONG_TERM
            if self.holding_months >= rules.equity_long_term_holding_months
            else GainTerm.SHORT_TERM
        )


@dataclass(slots=True)
class TaxSummary:
    ltcg: float = 0.0
    stcg: float = 0.0
    ltcg_tax: float = 0.0
    stcg_tax: float = 0.0
    ltcg_exemption_used: float = 0.0
    ltcg_exemption_remaining: float = 0.0

    @property
    def total_tax(self) -> float:
        return self.ltcg_tax + self.stcg_tax


def compute_tax_summary(
    sale_lots: list[SaleLot],
    *,
    rules: TaxRules = DEFAULT_TAX_RULES,
    debt_slab_rate: float | None = None,
    other_equity_ltcg_already_realized_this_fy: float = 0.0,
) -> TaxSummary:
    """Aggregate LTCG/STCG across a set of sale lots for one financial year.

    `other_equity_ltcg_already_realized_this_fy` lets the caller account for
    gains already booked elsewhere in the same FY so the ₹1.25L exemption is
    applied correctly across the whole portfolio, not per-call.
    """
    slab_rate = debt_slab_rate if debt_slab_rate is not None else rules.default_slab_rate_for_debt

    equity_like = {FundAssetType.EQUITY, FundAssetType.HYBRID_EQUITY_ORIENTED}
    ltcg_equity = 0.0
    stcg_equity = 0.0
    gain_debt = 0.0  # always short-term per current rules

    for lot in sale_lots:
        term = lot.gain_term(rules)
        if lot.asset_type in equity_like:
            if term == GainTerm.LONG_TERM:
                ltcg_equity += lot.net_gain
            else:
                stcg_equity += lot.net_gain
        else:
            gain_debt += lot.net_gain

    exemption_already_used = min(
        other_equity_ltcg_already_realized_this_fy, rules.equity_ltcg_exemption
    )
    exemption_left = max(0.0, rules.equity_ltcg_exemption - exemption_already_used)
    taxable_ltcg_equity = max(0.0, ltcg_equity - exemption_left)
    exemption_used_this_call = min(max(0.0, ltcg_equity), exemption_left)

    ltcg_tax = taxable_ltcg_equity * rules.equity_ltcg_rate
    stcg_tax = max(0.0, stcg_equity) * rules.equity_stcg_rate
    debt_tax = max(0.0, gain_debt) * slab_rate

    return TaxSummary(
        ltcg=ltcg_equity,
        stcg=stcg_equity + gain_debt,
        ltcg_tax=ltcg_tax,
        stcg_tax=stcg_tax + debt_tax,
        ltcg_exemption_used=exemption_used_this_call,
        ltcg_exemption_remaining=max(0.0, exemption_left - exemption_used_this_call),
    )


@dataclass(frozen=True, slots=True)
class HarvestingOpportunity:
    holding_id: str
    fund_name: str
    unrealized_gain: float
    recommended_action: str
    estimated_tax_saved: float
    reason: str


def find_tax_harvesting_opportunities(
    holdings: list[dict],
    *,
    rules: TaxRules = DEFAULT_TAX_RULES,
    unused_ltcg_exemption: float | None = None,
) -> list[HarvestingOpportunity]:
    """Identify equity holdings with long-term unrealized gains that can be
    booked (sold and immediately rebought) tax-free up to the unused
    ₹1.25L LTCG exemption for the financial year — the single most common,
    mechanical tax-optimization move for Indian equity MF investors.

    Each `holding` dict: {holding_id, fund_name, asset_type, buy_date,
    current_nav, buy_nav, units}.
    """
    exemption_left = (
        unused_ltcg_exemption if unused_ltcg_exemption is not None else rules.equity_ltcg_exemption
    )
    opportunities: list[HarvestingOpportunity] = []
    remaining_exemption = exemption_left

    equity_like = {FundAssetType.EQUITY, FundAssetType.HYBRID_EQUITY_ORIENTED}
    candidates = [
        h
        for h in holdings
        if FundAssetType(h["asset_type"]) in equity_like
        and (date.today() - h["buy_date"]).days / 30.44 >= rules.equity_long_term_holding_months
        and (h["current_nav"] - h["buy_nav"]) * h["units"] > 0
    ]
    # Harvest the smallest gains first to maximize how many lots fit inside
    # the exemption without triggering any taxable LTCG.
    candidates.sort(key=lambda h: (h["current_nav"] - h["buy_nav"]) * h["units"])

    for h in candidates:
        gain = (h["current_nav"] - h["buy_nav"]) * h["units"]
        if remaining_exemption <= 0:
            break
        harvestable = min(gain, remaining_exemption)
        tax_saved = harvestable * rules.equity_ltcg_rate
        opportunities.append(
            HarvestingOpportunity(
                holding_id=h["holding_id"],
                fund_name=h["fund_name"],
                unrealized_gain=round(gain, 2),
                recommended_action=(
                    f"Sell and immediately rebuy {round(harvestable / gain * 100, 1)}% of units to "
                    "book gains within your unused LTCG exemption, resetting your cost basis higher"
                    if harvestable < gain
                    else "Sell and immediately rebuy the full holding to book the gain tax-free"
                ),
                estimated_tax_saved=round(tax_saved, 2),
                reason=(
                    f"₹{gain:,.0f} unrealized long-term gain; you have ₹{remaining_exemption:,.0f} of "
                    f"your ₹{rules.equity_ltcg_exemption:,.0f} annual LTCG exemption unused this FY"
                ),
            )
        )
        remaining_exemption -= harvestable

    return opportunities
