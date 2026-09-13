from __future__ import annotations

from datetime import date

from app.services.report_generator import ReportData, render_portfolio_report


def test_renders_a_valid_pdf_with_all_sections():
    data = ReportData(
        portfolio_name="Primary",
        generated_on=date(2025, 1, 1),
        invested_value=500_000,
        current_value=650_000,
        xirr=14.2,
        absolute_return_pct=30.0,
        health_score={
            "overall_score": 82, "diversification_score": 75, "risk_score": 80,
            "returns_score": 85, "fees_score": 70, "fund_quality_score": 88,
            "tax_efficiency_score": 90, "asset_allocation_score": 80, "goal_readiness_score": 78,
        },
        risk_metrics={"beta": 1.05, "sharpe_ratio": 1.2, "max_drawdown": -22.5},
        recommendations=[
            {"action": "exit", "reason": "High expense ratio.", "risk": "May realize gains sooner.", "expected_benefit": "Lower fees."}
        ],
        tax_summary={"ltcg": 45000.0, "ltcg_tax": 0.0},
        goals=[{"type": "retirement", "target_amount": 20_000_000, "required_monthly_sip": 35000, "probability_of_success": 78}],
    )
    pdf_bytes = render_portfolio_report(data)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_renders_gracefully_with_minimal_data():
    data = ReportData(
        portfolio_name="Empty",
        generated_on=date(2025, 1, 1),
        invested_value=0,
        current_value=0,
        xirr=0,
        absolute_return_pct=0,
        health_score={},
        risk_metrics={},
        recommendations=[],
    )
    pdf_bytes = render_portfolio_report(data)
    assert pdf_bytes.startswith(b"%PDF-")
