from __future__ import annotations

import json

from app.agents.llm import FakeChatModel
from app.agents.recommendation import run


def _holding(**overrides) -> dict:
    base = dict(
        holding_id="h1", fund_id="f1", fund_name="Expensive Laggard Fund", amc="AMC1",
        category="Large Cap", asset_type="equity", units=1000.0,
        invested_value=100_000.0, current_value=110_000.0, avg_cost_nav=100.0,
        current_nav=110.0, expense_ratio=2.8, buy_date="2022-01-01",
    )
    base.update(overrides)
    return base


def _scripted_narration() -> str:
    return json.dumps(
        {
            "reason": "This fund's expense ratio is well above its category median.",
            "risk": "Exiting may realize a taxable gain sooner than planned.",
            "expected_benefit": "You save on ongoing costs by switching to a cheaper alternative.",
        }
    )


def test_recommends_exit_for_expensive_underperforming_bottom_quartile_fund():
    state = {
        "holdings": [_holding()],
        "fund_metrics": {
            "f1": {
                "category_median_expense_ratio": 1.0,
                "category_rank": 90,
                "category_size": 100,
                "cagr": 0.05,
                "category_median_xirr": 13.0,
            }
        },
        "overlap_report": {},
        "portfolio_metrics": {},
    }
    fake_model = FakeChatModel(default=_scripted_narration())
    result = run(state, chat_model=fake_model)
    recs = result["recommendations"]
    assert len(recs) == 1
    assert recs[0]["action"] == "exit"
    assert recs[0]["reason"]
    assert recs[0]["risk"]
    assert recs[0]["expected_benefit"]
    assert recs[0]["supporting_metrics"]


def test_ungrounded_llm_narration_is_downgraded_by_guardrail():
    state = {
        "holdings": [_holding()],
        "fund_metrics": {
            "f1": {
                "category_median_expense_ratio": 1.0,
                "category_rank": 90,
                "category_size": 100,
                "cagr": 0.05,
                "category_median_xirr": 13.0,
            }
        },
        "overlap_report": {},
        "portfolio_metrics": {},
    }
    ungrounded_response = json.dumps(
        {
            "reason": "This fund lost 88.4% of its value last year, sell immediately!",
            "risk": "none",
            "expected_benefit": "huge savings",
        }
    )
    fake_model = FakeChatModel(default=ungrounded_response)
    result = run(state, chat_model=fake_model)
    assert result["recommendations"][0]["action"] == "keep"
    assert "_rejected_original" in result["recommendations"][0]


def _five_equal_holdings(prefix: str) -> tuple[list[dict], dict]:
    # Five equally-sized holdings (20% each) so no single one crosses the
    # 25% concentration threshold — isolates the "no rule triggered" case.
    holdings = [
        _holding(
            fund_id=f"{prefix}{i}", holding_id=f"h_{prefix}{i}", fund_name=f"Fund {prefix}{i}",
            expense_ratio=1.0, current_value=20_000, invested_value=18_000,
        )
        for i in range(5)
    ]
    fund_metrics = {
        f"{prefix}{i}": {
            "category_median_expense_ratio": 1.0,
            "category_rank": 50,
            "category_size": 100,
            "cagr": 0.12,
            "category_median_xirr": 12.0,
        }
        for i in range(5)
    }
    return holdings, fund_metrics


def test_keep_for_healthy_fund_with_no_triggered_rules():
    holdings, fund_metrics = _five_equal_holdings("f2_")
    state = {
        "holdings": holdings,
        "fund_metrics": fund_metrics,
        "overlap_report": {},
        "portfolio_metrics": {},
    }
    fake_model = FakeChatModel(default=_scripted_narration())
    result = run(state, chat_model=fake_model)
    for rec in result["recommendations"]:
        assert rec["action"] == "keep"


def test_malformed_llm_json_falls_back_to_template():
    holdings, fund_metrics = _five_equal_holdings("f3_")
    state = {
        "holdings": holdings,
        "fund_metrics": fund_metrics,
        "overlap_report": {},
        "portfolio_metrics": {},
    }
    fake_model = FakeChatModel(default="not valid json at all")
    result = run(state, chat_model=fake_model)
    rec = result["recommendations"][0]
    assert rec["reason"]  # template fallback still produces a reason
    assert rec["action"] == "keep"
