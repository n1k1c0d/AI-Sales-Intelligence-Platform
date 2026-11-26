"""Importing these mappings registers the complete CRM schema for Alembic."""

from .crm import (
    Activity,
    Contact,
    Deal,
    DealStageHistory,
    Organization,
    Pipeline,
    PipelineStage,
    User,
)

__all__ = [
    "Activity",
    "Contact",
    "Deal",
    "DealStageHistory",
    "Organization",
    "Pipeline",
    "PipelineStage",
    "User",
]
