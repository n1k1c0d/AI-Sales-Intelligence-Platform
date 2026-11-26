"""Stable CRM codes stored in PostgreSQL as lowercase strings."""

from enum import StrEnum


class UserRole(StrEnum):
    MANAGER = "manager"
    SALES_LEAD = "sales_lead"
    ADMIN = "admin"


class DealStatus(StrEnum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"


class ActivityType(StrEnum):
    CALL = "call"
    MESSAGE = "message"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"


class ActivityDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class LossReason(StrEnum):
    PRICE = "price"
    NO_BUDGET = "no_budget"
    NO_RESPONSE = "no_response"
    NOT_INTERESTED = "not_interested"
    COMPETITOR = "competitor"
    TIMING = "timing"
    PRODUCT_MISMATCH = "product_mismatch"
    OTHER = "other"


# The scoped Deal → Stage foreign key uses the same three codes on both sides.
StageType = DealStatus
