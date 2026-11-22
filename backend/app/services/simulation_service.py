"""Application controller managing the SimulationEngine and background tick loop."""

import asyncio
from collections.abc import Callable
from contextlib import suppress

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.schemas.simulation import (
    DetectedIncident,
    ScenarioDefinition,
    SimulationStatusResponse,
)
from app.schemas.telemetry import ServiceTelemetrySample
from app.schemas.topology import TopologyResponse
from app.services.audit_service import record_audit_event
from app.services.incident_repository import clear_persisted_incidents, upsert_incident
from app.simulator.engine import SimulationEngine


class SimulationController:
    """Coordinates simulation lifecycle, deterministic stepping, and audit logging."""

    def __init__(
        self,
        *,
        tick_interval_seconds: float = 2.0,
        session_factory: Callable[[], Session] | None = SessionLocal,
    ) -> None:
        self.engine = SimulationEngine(tick_interval_seconds=tick_interval_seconds)
        self._session_factory = session_factory
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    async def start(self, db: Session | None = None) -> SimulationStatusResponse:
        """Start the periodic background simulation tick loop."""
        if not self.is_running:
            self._running = True
            self._task = asyncio.create_task(self._tick_loop(), name="nexus-sim-loop")
            record_audit_event(
                db,
                actor_type="SYSTEM",
                actor_name="SimulationController",
                action="SIMULATION_STARTED",
                details={"tick": self.engine.tick, "interval_s": self.engine.tick_interval_seconds},
            )
        return self.get_status()

    async def stop(self, db: Session | None = None) -> SimulationStatusResponse:
        """Stop the periodic background simulation tick loop."""
        was_running = self.is_running
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        if was_running:
            record_audit_event(
                db,
                actor_type="SYSTEM",
                actor_name="SimulationController",
                action="SIMULATION_STOPPED",
                details={"tick": self.engine.tick},
            )
        return self.get_status()

    def advance(self, ticks: int = 1, db: Session | None = None) -> SimulationStatusResponse:
        """Deterministically advance the simulation by `ticks` without real-time waiting."""
        _, new_incidents = self.engine.step(ticks=ticks)
        self._sync_incidents_to_db(db)
        self._record_detected_incidents(new_incidents, db)
        return self.get_status()

    def inject_scenario(
        self, scenario_id: str, db: Session | None = None
    ) -> tuple[ScenarioDefinition, SimulationStatusResponse]:
        """Inject a failure scenario into the simulation engine."""
        scenario = self.engine.inject_scenario(scenario_id)
        record_audit_event(
            db,
            actor_type="HUMAN",
            actor_name="operator",
            action="SCENARIO_INJECTED",
            details={"scenario_id": scenario.id, "tick": self.engine.tick},
        )
        return scenario, self.get_status()

    async def reset(
        self, *, clear_incidents: bool = True, db: Session | None = None
    ) -> SimulationStatusResponse:
        """Stop any active loop and restore all services to healthy baseline."""
        was_running = self.is_running
        if was_running:
            await self.stop(db=None)
        self.engine.reset(clear_incidents=clear_incidents)
        if clear_incidents and db is not None:
            clear_persisted_incidents(db)
        record_audit_event(
            db,
            actor_type="HUMAN",
            actor_name="operator",
            action="SIMULATION_RESET",
            details={
                "clear_incidents": clear_incidents,
                "stopped_running_loop": was_running,
            },
        )
        return self.get_status()

    def list_scenarios(self) -> list[ScenarioDefinition]:
        return self.engine.scenarios.list_definitions()

    def get_status(self) -> SimulationStatusResponse:
        return self.engine.get_status(running=self.is_running)

    def get_topology(self) -> TopologyResponse:
        return self.engine.get_topology_snapshot()

    def get_latest_telemetry(self, service_id: str | None = None) -> list[ServiceTelemetrySample]:
        return self.engine.get_latest_telemetry(service_id=service_id)

    def get_telemetry_history(
        self, service_id: str | None = None, limit: int = 30
    ) -> list[ServiceTelemetrySample]:
        return self.engine.get_telemetry_history(service_id=service_id, limit=limit)

    def list_incidents(self) -> list[DetectedIncident]:
        return self.engine.detector.list_incidents()

    def get_incident(self, incident_id: str) -> DetectedIncident | None:
        return self.engine.detector.get_incident(incident_id)

    def _record_detected_incidents(
        self, new_incidents: list[DetectedIncident], db: Session | None
    ) -> None:
        for inc in new_incidents:
            record_audit_event(
                db,
                actor_type="SYSTEM",
                actor_name="IncidentDetector",
                action="INCIDENT_DETECTED",
                incident_id=inc.id,
                details={
                    "severity": inc.severity,
                    "affected_services": inc.affected_services,
                    "root_cause_candidate": inc.root_cause_candidate,
                    "tick": inc.detected_tick,
                },
            )

    def _sync_incidents_to_db(self, db: Session | None) -> None:
        if db is None:
            return
        for inc in self.engine.detector.list_incidents():
            upsert_incident(db, inc, tick_interval_seconds=self.engine.tick_interval_seconds)

    async def _tick_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.engine.tick_interval_seconds)
            if not self._running:
                break
            _, new_incidents = self.engine.step(ticks=1)
            if self._session_factory is not None and (
                new_incidents or self.engine.detector.list_incidents()
            ):
                with self._session_factory() as db:
                    self._sync_incidents_to_db(db)
                    if new_incidents:
                        self._record_detected_incidents(new_incidents, db)

