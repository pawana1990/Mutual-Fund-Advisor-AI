"""Shared enums, mirrored as Postgres ENUM types in the Alembic migrations."""
from __future__ import annotations

from enum import StrEnum


class Plan(StrEnum):
    RETAIL_FREE = "retail_free"
    RETAIL_PREMIUM = "retail_premium"
    ADVISOR = "advisor"
    ENTERPRISE = "enterprise"


class UserRole(StrEnum):
    OWNER = "owner"
    ADVISOR = "advisor"
    CLIENT_VIEWER = "client_viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


class RiskProfile(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class HoldingSource(StrEnum):
    CAMS = "cams"
    KFIN = "kfin"
    GROWW = "groww"
    ZERODHA_COIN = "zerodha_coin"
    ETMONEY = "etmoney"
    KUVERA = "kuvera"
    MANUAL = "manual"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


class TransactionType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    SIP = "sip"
    SWITCH_IN = "switch_in"
    SWITCH_OUT = "switch_out"
    DIVIDEND = "dividend"
    STT = "stt"


class SipFrequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class SipStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class RecommendationAction(StrEnum):
    KEEP = "keep"
    INCREASE = "increase"
    REDUCE = "reduce"
    EXIT = "exit"
    SWITCH = "switch"


class RecommendationStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


class GoalType(StrEnum):
    RETIREMENT = "retirement"
    HOUSE = "house"
    EDUCATION = "education"
    EMERGENCY_FUND = "emergency_fund"
    FIRE = "fire"
    VACATION = "vacation"
    WEALTH_CREATION = "wealth_creation"


class AlertType(StrEnum):
    UNDERPERFORMANCE = "underperformance"
    EXPENSE_RATIO_CHANGE = "expense_ratio_change"
    MANAGER_CHANGE = "manager_change"
    OVERLAP_INCREASE = "overlap_increase"
    EXIT_LOAD_ENDED = "exit_load_ended"
    TAX_HARVEST = "tax_harvest"
    MARKET_CRASH = "market_crash"
    SEBI_CIRCULAR = "sebi_circular"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ImportStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
