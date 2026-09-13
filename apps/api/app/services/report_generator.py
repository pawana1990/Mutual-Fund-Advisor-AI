"""Generates the "beautiful PDF report" (Executive Summary, Portfolio
Overview, Risk Analysis, Performance, Recommendations, Tax Report, Goal
Tracking) using ReportLab. Pure function of already-computed agent
outputs — never recomputes metrics, matching the evidence-first principle
in docs/AI_AGENT_WORKFLOW.md §4."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_BRAND_COLOR = colors.HexColor("#0F62FE")
_MUTED = colors.HexColor("#6B7280")


@dataclass(slots=True)
class ReportData:
    portfolio_name: str
    generated_on: date
    invested_value: float
    current_value: float
    xirr: float
    absolute_return_pct: float
    health_score: dict
    risk_metrics: dict
    recommendations: list[dict]
    tax_summary: dict | None = None
    goals: list[dict] = field(default_factory=list)


def _styles():
    stylesheet = getSampleStyleSheet()
    stylesheet.add(
        ParagraphStyle(name="ReportTitle", fontSize=22, textColor=_BRAND_COLOR, spaceAfter=6, leading=26)
    )
    stylesheet.add(ParagraphStyle(name="SectionHeading", fontSize=15, textColor=_BRAND_COLOR, spaceBefore=18, spaceAfter=8))
    stylesheet.add(ParagraphStyle(name="Muted", fontSize=9, textColor=_MUTED))
    return stylesheet


def render_portfolio_report(data: ReportData) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm
    )
    styles = _styles()
    story = []

    story.append(Paragraph("AI Wealth Advisor", styles["ReportTitle"]))
    story.append(Paragraph(f"Portfolio Report — {data.portfolio_name}", styles["Heading2"]))
    story.append(Paragraph(f"Generated on {data.generated_on.isoformat()}", styles["Muted"]))
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Executive Summary", styles["SectionHeading"]))
    gain = data.current_value - data.invested_value
    story.append(
        Paragraph(
            f"Your portfolio is currently valued at ₹{data.current_value:,.0f}, invested from "
            f"₹{data.invested_value:,.0f}, an absolute gain of ₹{gain:,.0f} "
            f"({data.absolute_return_pct:+.2f}%). Your money-weighted return (XIRR) is "
            f"{data.xirr:.2f}% annualized. Your overall Portfolio Health Score is "
            f"{data.health_score.get('overall_score', 'N/A')}/100.",
            styles["BodyText"],
        )
    )

    story.append(Paragraph("Portfolio Health Score", styles["SectionHeading"]))
    if data.health_score:
        rows = [["Category", "Score"]] + [
            [key.replace("_", " ").replace(" score", "").title(), f"{value}/100"]
            for key, value in data.health_score.items()
            if key != "overall_score"
        ]
        story.append(_styled_table(rows))

    story.append(Paragraph("Risk Analysis", styles["SectionHeading"]))
    if data.risk_metrics:
        rows = [["Metric", "Value"]] + [[k.replace("_", " ").title(), str(v)] for k, v in data.risk_metrics.items()]
        story.append(_styled_table(rows))
    else:
        story.append(Paragraph("Risk metrics are not yet available for this portfolio.", styles["BodyText"]))

    story.append(PageBreak())
    story.append(Paragraph("Recommendations", styles["SectionHeading"]))
    if data.recommendations:
        for rec in data.recommendations:
            story.append(Paragraph(f"<b>{rec['action'].upper()}</b> — {rec['reason']}", styles["BodyText"]))
            story.append(Paragraph(f"Risk: {rec['risk']}", styles["Muted"]))
            story.append(Paragraph(f"Expected benefit: {rec['expected_benefit']}", styles["Muted"]))
            story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph("No active recommendations at this time.", styles["BodyText"]))

    if data.tax_summary:
        story.append(Paragraph("Tax Report", styles["SectionHeading"]))
        rows = [["Item", "Amount (₹)"]] + [[k.replace("_", " ").title(), f"{v:,.2f}"] for k, v in data.tax_summary.items()]
        story.append(_styled_table(rows))

    if data.goals:
        story.append(Paragraph("Goal Tracking", styles["SectionHeading"]))
        rows = [["Goal", "Target", "Required Monthly SIP", "Success Probability"]] + [
            [
                g.get("type", ""),
                f"₹{g.get('target_amount', 0):,.0f}",
                f"₹{g.get('required_monthly_sip', 0):,.0f}",
                f"{g.get('probability_of_success', 0):.0f}%",
            ]
            for g in data.goals
        ]
        story.append(_styled_table(rows))

    doc.build(story)
    return buffer.getvalue()


def _styled_table(rows: list[list[str]]) -> Table:
    table = Table(rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BRAND_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table
