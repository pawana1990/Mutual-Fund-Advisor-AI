from __future__ import annotations

import json

from app.agents.llm import FakeChatModel
from app.agents.orchestrator import build_chat_graph, build_refresh_graph, classify_chat_intent

_NARRATION = FakeChatModel(
    default=json.dumps(
        {
            "reason": "Metrics support this action.",
            "risk": "Some risk applies.",
            "expected_benefit": "Some benefit expected.",
        }
    )
)


def _holding(**overrides) -> dict:
    base = dict(
        holding_id="h1", fund_id="f1", fund_name="HDFC Top 100", amc="HDFC",
        category="Large Cap", asset_type="equity", units=1000.0,
        invested_value=100_000.0, current_value=110_000.0, avg_cost_nav=100.0,
        current_nav=110.0, expense_ratio=1.0, buy_date="2023-01-01",
    )
    base.update(overrides)
    return base


class TestIntentClassification:
    def test_risk_question(self):
        assert classify_chat_intent("Is my portfolio too risky?") == "risk"

    def test_goal_question(self):
        assert classify_chat_intent("Will I reach 5 crore by retirement?") == "goal"

    def test_tax_question(self):
        assert classify_chat_intent("What LTCG tax will I owe?") == "tax"

    def test_general_fallback(self):
        assert classify_chat_intent("Hello there") == "general"


class TestRefreshGraph:
    def test_full_pipeline_runs_and_produces_health_score(self):
        graph = build_refresh_graph(chat_model=_NARRATION)
        initial_state = {
            "portfolio_id": "p1",
            "holdings": [_holding(), _holding(fund_id="f2", holding_id="h2", current_value=90_000, invested_value=80_000)],
            "fund_metrics": {
                "f1": {
                    "category_median_expense_ratio": 1.0,
                    "category_rank": 60,
                    "category_size": 100,
                    "cagr": 0.12,
                    "category_median_xirr": 12.0,
                }
            },
            "goals": [],
        }
        final_state = graph.invoke(initial_state)
        assert "portfolio_metrics" in final_state
        assert "recommendations" in final_state
        assert "health_score" in final_state
        assert final_state["health_score"]  # non-empty since holdings present


class TestChatGraph:
    def test_risk_question_routes_to_risk_report(self):
        graph = build_chat_graph(chat_model=_NARRATION)
        state = graph.invoke(
            {
                "chat_question": "Is my portfolio too risky?",
                "holdings": [_holding()],
                "fund_metrics": {"f1": {"beta": 1.1, "sharpe_ratio": 0.9}},
            }
        )
        assert state["chat_intent"] == "risk"
        assert "risk_report" in state

    def test_goal_question_routes_to_goal_planning(self):
        graph = build_chat_graph()
        state = graph.invoke(
            {
                "chat_question": "Will I reach 2 crore in 10 years?",
                "holdings": [],
                "goals": [
                    {
                        "target_amount": 20_000_000,
                        "target_date": "2035-01-01",
                        "current_progress_value": 500_000,
                        "assumed_return_rate": 12.0,
                        "current_monthly_sip": 25_000,
                    }
                ],
            }
        )
        assert state["chat_intent"] == "goal"
        assert state["goals"][0]["probability_of_success"] is not None
