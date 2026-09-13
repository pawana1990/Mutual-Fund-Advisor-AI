"""SQLAlchemy ORM models.

Import every model module here so `Base.metadata` is fully populated for
Alembic autogenerate and for `Base.metadata.create_all()` in tests.
"""
from app.models.alert import Alert
from app.models.chat import ChatMessage, ChatSession
from app.models.fund import Fund, FundNavHistory, FundRiskMetrics
from app.models.goal import Goal, GoalProjection
from app.models.imports import ImportJob, ImportRow
from app.models.organization import Organization
from app.models.portfolio import Holding, Portfolio, Sip, Transaction
from app.models.recommendation import Recommendation
from app.models.snapshot import HealthScore, OverlapReport, PortfolioSnapshot
from app.models.tax import TaxRecord
from app.models.user import AuditLog, User

__all__ = [
    "Organization",
    "User",
    "AuditLog",
    "Fund",
    "FundNavHistory",
    "FundRiskMetrics",
    "Portfolio",
    "Holding",
    "Transaction",
    "Sip",
    "PortfolioSnapshot",
    "HealthScore",
    "OverlapReport",
    "Recommendation",
    "Goal",
    "GoalProjection",
    "TaxRecord",
    "Alert",
    "ChatSession",
    "ChatMessage",
    "ImportJob",
    "ImportRow",
]
