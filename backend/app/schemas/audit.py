"""Pydantic v2 schemas for read-only persisted audit log retrieval."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AuditCategory = Literal[
    "INCIDENT",
    "INVESTIGATION",
    "POLICY",
    "RECOVERY",
    "VERIFICATION",
    "SIMULATION",
]

ACTION_TO_CATEGORY: dict[str, AuditCategory] = {
    "INCIDENT_DETECTED": "INCIDENT",
    "INCIDENT_UPDATED": "INCIDENT",
    "INCIDENT_RESOLVED": "INCIDENT",
    "INVESTIGATION_STARTED": "INVESTIGATION",
    "INVESTIGATION_COMPLETED": "INVESTIGATION",
    "INVESTIGATION_FAILED": "INVESTIGATION",
    "POLICY_EVALUATED": "POLICY",
    "REMEDIATION_APPROVED": "POLICY",
    "REMEDIATION_REJECTED": "POLICY",
    "REMEDIATION_PLAN_CREATED": "RECOVERY",
    "REMEDIATION_EXECUTION_STARTED": "RECOVERY",
    "REMEDIATION_EXECUTION_COMPLETED": "RECOVERY",
    "REMEDIATION_EXECUTION_FAILED": "RECOVERY",
    "VERIFICATION_STARTED": "VERIFICATION",
    "VERIFICATION_COMPLETED": "VERIFICATION",
    "VERIFICATION_FAILED": "VERIFICATION",
    "SIMULATION_STARTED": "SIMULATION",
    "SIMULATION_STOPPED": "SIMULATION",
    "SCENARIO_INJECTED": "SIMULATION",
    "SIMULATION_RESET": "SIMULATION",
}


def classify_audit_category(action: str) -> AuditCategory:
    """Map a persisted audit action name to its logical governance category."""
    return ACTION_TO_CATEGORY.get(action, "SIMULATION")


class AuditLogEntry(BaseModel):
    """Single persisted append-only audit record from SQLite."""

    id: str
    incident_id: str | None = None
    actor_type: str
    actor_name: str
    action: str
    category: AuditCategory
    details: dict = Field(default_factory=dict)
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    """Collection of persisted audit records."""

    total: int
    entries: list[AuditLogEntry]
