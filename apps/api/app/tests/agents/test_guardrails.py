from __future__ import annotations

from app.agents.guardrails import enforce_guardrails, validate_recommendation_grounding


class TestGrounding:
    def test_grounded_reason_passes(self):
        result = validate_recommendation_grounding(
            "This fund's expense ratio of 2.35% is well above the category median of 1.10%, "
            "and its 3-year CAGR of 9.2% trails the benchmark.",
            {"expense_ratio": 2.35, "category_median_expense_ratio": 1.10, "cagr_3y": 9.2},
        )
        assert result.is_grounded

    def test_ungrounded_number_is_flagged(self):
        result = validate_recommendation_grounding(
            "This fund has lost 47.5% this year, you should exit immediately.",
            {"expense_ratio": 2.35, "cagr_3y": 9.2},
        )
        assert not result.is_grounded
        assert 47.5 in result.ungrounded_numbers

    def test_percent_vs_fraction_formatting_is_tolerated(self):
        result = validate_recommendation_grounding(
            "The fund's Sharpe-adjusted overlap of 14.5% with your other holding is notable.",
            {"overlap_pct": 0.145},
        )
        assert result.is_grounded

    def test_small_ordinal_numbers_are_ignored(self):
        result = validate_recommendation_grounding(
            "You hold 3 similar large-cap funds with meaningfully overlapping portfolios.",
            {"fund_count": 3},
        )
        assert result.is_grounded


class TestEnforceGuardrails:
    def test_grounded_recommendation_passes_through_unchanged(self):
        rec = {
            "action": "exit",
            "reason": "Expense ratio of 2.5% is far above the category median of 1.0%.",
            "supporting_metrics": {"expense_ratio": 2.5, "category_median_expense_ratio": 1.0},
            "risk": "You may miss short-term upside if the fund rallies.",
            "expected_benefit": "Save on recurring fees over the long term.",
            "confidence": 0.8,
        }
        assert enforce_guardrails(rec) == rec

    def test_ungrounded_recommendation_is_downgraded_to_keep(self):
        rec = {
            "action": "exit",
            "reason": "This fund crashed 62% last quarter.",
            "supporting_metrics": {"expense_ratio": 1.2},
            "risk": "some risk",
            "expected_benefit": "some benefit",
            "confidence": 0.9,
        }
        downgraded = enforce_guardrails(rec)
        assert downgraded["action"] == "keep"
        assert downgraded["confidence"] == 0.0
        assert "_rejected_original" in downgraded

    def test_missing_required_field_is_downgraded(self):
        rec = {"action": "exit", "reason": "", "supporting_metrics": {}, "risk": "x", "expected_benefit": "y"}
        downgraded = enforce_guardrails(rec)
        assert downgraded["action"] == "keep"
