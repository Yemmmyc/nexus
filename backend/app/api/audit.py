"""Read-only persisted audit trail API routes (/api/v1/audit)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import AuditLogORM
from app.schemas.audit import (
    ACTION_TO_CATEGORY,
    AuditCategory,
    AuditLogEntry,
    AuditLogListResponse,
    classify_audit_category,
)

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("", response_model=AuditLogListResponse, summary="List persisted audit trail records")
def list_audit_logs(
    incident_id: str | None = Query(default=None, description="Filter by incident ID"),
    actor_type: str | None = Query(default=None, description="Filter by actor type (SYSTEM|AGENT|POLICY|HUMAN)"),
    category: AuditCategory | None = Query(default=None, description="Filter by lifecycle category"),
    order: Literal["asc", "desc"] = Query(default="asc", description="Chronological ordering"),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Return persisted append-only audit records directly from SQLite."""
    stmt = select(AuditLogORM)

    if incident_id is not None:
        stmt = stmt.where(AuditLogORM.incident_id == incident_id)
    if actor_type is not None:
        stmt = stmt.where(AuditLogORM.actor_type == actor_type.upper())
    if category is not None:
        matching_actions = [
            act for act, cat in ACTION_TO_CATEGORY.items() if cat == category
        ]
        stmt = stmt.where(AuditLogORM.action.in_(matching_actions))

    if order == "desc":
        stmt = stmt.order_by(AuditLogORM.timestamp.desc(), AuditLogORM.id.desc())
    else:
        stmt = stmt.order_by(AuditLogORM.timestamp.asc(), AuditLogORM.id.asc())

    rows = db.execute(stmt.limit(limit)).scalars().all()
    entries = [
        AuditLogEntry(
            id=row.id,
            incident_id=row.incident_id,
            actor_type=row.actor_type,
            actor_name=row.actor_name,
            action=row.action,
            category=classify_audit_category(row.action),
            details=row.details if isinstance(row.details, dict) else {},
            timestamp=row.timestamp,
        )
        for row in rows
    ]
    return AuditLogListResponse(total=len(entries), entries=entries)
