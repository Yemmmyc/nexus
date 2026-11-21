"""Foundational SQLAlchemy 2.0 ORM models for NEXUS."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ServiceNodeORM(Base):
    """Simulated infrastructure service node."""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy")
    criticality: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    baseline_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    slo_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=250.0)
    slo_error_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.01)


class DependencyEdgeORM(Base):
    """Directed dependency edge (source depends on target)."""

    __tablename__ = "dependencies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("services.id"), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), ForeignKey("services.id"), nullable=False)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)
    impact_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)


class AuditLogORM(Base):
    """Append-only audit trail entry."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    incident_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)

