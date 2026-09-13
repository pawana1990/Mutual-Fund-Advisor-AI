"""Portfolio overlap detection: duplicate holdings across funds, AMC
concentration, and sector overlap — the deterministic core behind the
Overlap Detection Agent (see docs/AI_AGENT_WORKFLOW.md)."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.financial_metrics import allocation_breakdown, herfindahl_hirschman_index


@dataclass(frozen=True, slots=True)
class FundStockBasket:
    """A fund's top underlying stock holdings, weighted by % of the fund's
    AUM — sourced from the Fund Research Agent's factsheet ingestion."""

    fund_id: str
    fund_name: str
    amc: str
    stock_weights: dict[str, float]  # stock_name -> % of fund AUM
    sector_weights: dict[str, float]  # sector -> % of fund AUM


@dataclass(frozen=True, slots=True)
class PairwiseOverlap:
    fund_a: str
    fund_b: str
    overlap_pct: float  # weighted overlap of common holdings, min-weight method
    common_holdings: list[str]


def pairwise_stock_overlap(a: FundStockBasket, b: FundStockBasket) -> PairwiseOverlap:
    """Standard "portfolio overlap %" definition: sum, over stocks held by
    both funds, of min(weight_in_a, weight_in_b) — the fraction of each
    fund's basket that is functionally duplicated by the other."""
    common = set(a.stock_weights) & set(b.stock_weights)
    overlap = sum(min(a.stock_weights[s], b.stock_weights[s]) for s in common)
    return PairwiseOverlap(
        fund_a=a.fund_id,
        fund_b=b.fund_id,
        overlap_pct=round(overlap, 2),
        common_holdings=sorted(common, key=lambda s: -min(a.stock_weights[s], b.stock_weights[s])),
    )


@dataclass(frozen=True, slots=True)
class OverlapReport:
    portfolio_overlap_pct: float  # weighted-average pairwise overlap across the portfolio
    duplicate_pairs: list[PairwiseOverlap]
    amc_concentration: dict[str, float]
    sector_overlap: dict[str, float]
    amc_hhi: float


def build_overlap_report(
    baskets: list[FundStockBasket],
    holding_values: dict[str, float],  # fund_id -> current_value, for weighting
    *,
    pair_overlap_warning_threshold: float = 30.0,
) -> OverlapReport:
    if not baskets:
        raise ValueError("Need at least one fund to build an overlap report")

    total_value = sum(holding_values.get(b.fund_id, 0.0) for b in baskets)
    pairs: list[PairwiseOverlap] = []
    weighted_overlap_sum = 0.0
    weighted_overlap_weight = 0.0

    for i in range(len(baskets)):
        for j in range(i + 1, len(baskets)):
            a, b = baskets[i], baskets[j]
            pair = pairwise_stock_overlap(a, b)
            if pair.overlap_pct > 0:
                pairs.append(pair)
            pair_weight = (
                holding_values.get(a.fund_id, 0.0) + holding_values.get(b.fund_id, 0.0)
            )
            weighted_overlap_sum += pair.overlap_pct * pair_weight
            weighted_overlap_weight += pair_weight

    portfolio_overlap_pct = (
        round(weighted_overlap_sum / weighted_overlap_weight, 2) if weighted_overlap_weight else 0.0
    )

    amc_values: dict[str, float] = {}
    sector_values: dict[str, float] = {}
    for basket in baskets:
        value = holding_values.get(basket.fund_id, 0.0)
        amc_values[basket.amc] = amc_values.get(basket.amc, 0.0) + value
        for sector, weight in basket.sector_weights.items():
            sector_values[sector] = sector_values.get(sector, 0.0) + value * (weight / 100.0)

    amc_concentration = allocation_breakdown(amc_values) if amc_values and total_value > 0 else {}
    sector_overlap = allocation_breakdown(sector_values) if sector_values and total_value > 0 else {}
    amc_hhi = herfindahl_hirschman_index(amc_values) if amc_values and total_value > 0 else 0.0

    flagged_pairs = sorted(
        (p for p in pairs if p.overlap_pct >= pair_overlap_warning_threshold),
        key=lambda p: -p.overlap_pct,
    )

    return OverlapReport(
        portfolio_overlap_pct=portfolio_overlap_pct,
        duplicate_pairs=flagged_pairs or sorted(pairs, key=lambda p: -p.overlap_pct)[:5],
        amc_concentration=amc_concentration,
        sector_overlap=sector_overlap,
        amc_hhi=round(amc_hhi, 2),
    )
