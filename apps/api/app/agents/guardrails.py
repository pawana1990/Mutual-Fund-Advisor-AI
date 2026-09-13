"""Grounding guardrail: every AI-generated recommendation must be traceable
to the numbers it was given. This module extracts numeric claims from a
recommendation's natural-language `reason` and cross-checks them against
`supporting_metrics` — a recommendation citing a number that isn't backed by
evidence is downgraded to `keep` rather than shown to the user as-is.
See docs/AI_AGENT_WORKFLOW.md §4.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")

_RELATIVE_TOLERANCE = 0.02  # 2% — allows for rounding/formatting differences


@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_grounded: bool
    ungrounded_numbers: list[float]


def _extract_numbers(text: str) -> list[float]:
    numbers = []
    for match in _NUMBER_RE.findall(text):
        cleaned = match.replace(",", "")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        # Ignore tiny integers (1, 2, 3...) that are almost always ordinal/
        # list references ("3 funds"), not evidentiary metrics, to avoid
        # false positives that would reject perfectly grounded reasoning.
        if abs(value) < 10:
            continue
        numbers.append(value)
    return numbers


def _flatten_metric_values(metrics: dict) -> list[float]:
    values: list[float] = []
    for v in metrics.values():
        if isinstance(v, (int, float)):
            values.append(float(v))
        elif isinstance(v, dict):
            values.extend(_flatten_metric_values(v))
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, (int, float)):
                    values.append(float(item))
                elif isinstance(item, dict):
                    values.extend(_flatten_metric_values(item))
    return values


def _is_grounded_number(number: float, evidence_values: list[float]) -> bool:
    for evidence in evidence_values:
        if evidence == 0:
            if number == 0:
                return True
            continue
        if abs(number - evidence) <= abs(evidence) * _RELATIVE_TOLERANCE:
            return True
        # Also accept the same number scaled by 100 (percent vs fraction
        # formatting mismatches, e.g. 0.145 in the metrics vs "14.5%" in text).
        if abs(number - evidence * 100) <= abs(evidence * 100) * _RELATIVE_TOLERANCE:
            return True
        if abs(number - evidence / 100) <= max(abs(evidence / 100) * _RELATIVE_TOLERANCE, 1e-6):
            return True
    return False


def validate_recommendation_grounding(reason: str, supporting_metrics: dict) -> ValidationResult:
    """Returns `is_grounded=False` if `reason` cites a number that cannot be
    matched (within tolerance) to any value in `supporting_metrics`."""
    claimed_numbers = _extract_numbers(reason)
    evidence_values = _flatten_metric_values(supporting_metrics)

    ungrounded = [n for n in claimed_numbers if not _is_grounded_number(n, evidence_values)]
    return ValidationResult(is_grounded=len(ungrounded) == 0, ungrounded_numbers=ungrounded)


def enforce_guardrails(recommendation: dict) -> dict:
    """Given a candidate recommendation dict (as produced by an agent),
    return it unchanged if grounded, or a downgraded `keep` recommendation
    (with the original preserved under `_rejected_original` for audit/
    prompt-engineering review) if not."""
    required_fields = ("reason", "supporting_metrics", "risk", "expected_benefit")
    for field in required_fields:
        if not recommendation.get(field):
            return _downgrade(recommendation, reason=f"Missing required field: {field}")

    result = validate_recommendation_grounding(
        recommendation["reason"], recommendation["supporting_metrics"]
    )
    if not result.is_grounded:
        return _downgrade(
            recommendation,
            reason=(
                f"Reason cited unsupported figures {result.ungrounded_numbers} not present in "
                "supporting_metrics"
            ),
        )
    return recommendation


def _downgrade(recommendation: dict, *, reason: str) -> dict:
    return {
        **recommendation,
        "action": "keep",
        "reason": (
            "Insufficient verified evidence to recommend a change at this time; "
            "more data is needed before an actionable recommendation can be made."
        ),
        "confidence": 0.0,
        "_rejected_original": recommendation,
        "_rejection_reason": reason,
    }
