"""Append-only audit trail writer for consequential NEXUS operations."""

from sqlalchemy.orm import Session

from app.db.models import AuditLogORM


def record_audit_event(
    db: Session | None,
    *,
    actor_type: str,
    actor_name: str,
    action: str,
    details: dict | None = None,
    incident_id: str | None = None,
) -> None:
    """Append an immutable audit log entry when a DB session is provided."""
    if db is None:
        return
    entry = AuditLogORM(
        incident_id=incident_id,
        actor_type=actor_type,
        actor_name=actor_name,
        action=action,
        details=details or {},
    )
    db.add(entry)
    db.commit()

