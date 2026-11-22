"""Deterministic, reproducible infrastructure simulation engine."""

from collections import deque
from datetime import datetime, timedelta, timezone

from app.schemas.simulation import DetectedIncident, ScenarioDefinition, SimulationStatusResponse
from app.schemas.telemetry import MonitoringEvent, ServiceHealthStatus, ServiceTelemetrySample
from app.schemas.topology import DependencyEdgeState, ServiceNodeState, TopologyResponse
from app.simulator.detector import IncidentDetector
from app.simulator.models import ActiveFault, ActiveMitigation, ServiceRuntimeState
from app.simulator.propagation import propagate_tick
from app.simulator.scenarios import ScenarioManager
from app.simulator.topology_graph import TopologyGraph

# Deterministic epoch base so simulation timestamps are reproducible when stepping programmatically
_SIM_EPOCH = datetime(2026, 11, 22, 0, 0, 0, tzinfo=timezone.utc)


class SimulationEngine:
    """Core deterministic engine modeling topology, telemetry, faults, and incident detection."""

    def __init__(
        self,
        *,
        tick_interval_seconds: float = 2.0,
        history_limit_per_service: int = 120,
    ) -> None:
        self.tick_interval_seconds = tick_interval_seconds
        self._history_limit = history_limit_per_service
        self.topology = TopologyGraph()
        self.scenarios = ScenarioManager()
        self.detector = IncidentDetector(self.topology)

        self._tick: int = 0
        self._active_scenario: str | None = None
        self._active_faults: dict[str, ActiveFault] = {}
        self._active_mitigations: dict[str, ActiveMitigation] = {}
        self._states: dict[str, ServiceRuntimeState] = {}
        self._history: dict[str, deque[ServiceTelemetrySample]] = {}
        self._recent_events: deque[MonitoringEvent] = deque(maxlen=200)

        self.reset(clear_incidents=True)

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def sim_time_s(self) -> float:
        return round(self._tick * self.tick_interval_seconds, 2)

    @property
    def active_scenario(self) -> str | None:
        return self._active_scenario

    def _current_sim_timestamp(self) -> datetime:
        return _SIM_EPOCH + timedelta(seconds=self.sim_time_s)

    def reset(self, *, clear_incidents: bool = True) -> None:
        """Restore all services to their healthy baseline and clear active faults."""
        self._tick = 0
        self._active_scenario = None
        self._active_faults.clear()
        self._active_mitigations.clear()
        self._recent_events.clear()

        self._states = {
            svc.id: ServiceRuntimeState(baseline=svc) for svc in self.topology.services
        }
        self._history = {
            svc.id: deque(maxlen=self._history_limit) for svc in self.topology.services
        }

        if clear_incidents:
            self.detector.reset()

        self._record_samples()

    def inject_scenario(self, scenario_id: str) -> ScenarioDefinition:
        """Activate a named fault scenario starting at the next simulation tick."""
        spec = self.scenarios.get_scenario(scenario_id)
        self._active_scenario = spec.id
        next_tick = self._tick + 1
        for fault_spec in spec.faults:
            self._active_faults[fault_spec.target_service_id] = ActiveFault(
                scenario_id=spec.id,
                spec=fault_spec,
                injected_tick=next_tick,
            )
        return ScenarioDefinition(
            id=spec.id,
            name=spec.name,
            description=spec.description,
            root_service=spec.root_service,
            expected_severity=spec.expected_severity,
        )

    def apply_mitigation(self, mitigation: ActiveMitigation) -> None:
        """Register an approved, allowlisted simulated mitigation on a target service."""
        self._active_mitigations[mitigation.target_service_id] = mitigation

    def step(self, ticks: int = 1) -> tuple[list[MonitoringEvent], list[DetectedIncident]]:
        """Deterministically advance the simulation by `ticks` steps."""
        if ticks < 1:
            raise ValueError("ticks must be >= 1")

        all_events: list[MonitoringEvent] = []
        all_new_incidents: list[DetectedIncident] = []

        for _ in range(ticks):
            self._tick += 1
            self._states = propagate_tick(
                tick=self._tick,
                tick_interval_seconds=self.tick_interval_seconds,
                topology=self.topology,
                previous_states=self._states,
                active_faults=self._active_faults,
                active_mitigations=self._active_mitigations or None,
            )
            self._record_samples()

            events, new_incidents = self.detector.evaluate_tick(
                tick=self._tick,
                sim_time_s=self.sim_time_s,
                timestamp=self._current_sim_timestamp(),
                states=self._states,
                active_scenario=self._active_scenario,
                auto_resolve_on_healthy=not bool(self._active_mitigations),
            )
            for ev in events:
                self._recent_events.append(ev)
            all_events.extend(events)
            all_new_incidents.extend(new_incidents)

        return all_events, all_new_incidents

    def calculate_resilience_score(self) -> float:
        """Compute global resilience score (0-100) weighted by service criticality."""
        total_weight = sum(s.baseline.criticality for s in self._states.values())
        if total_weight == 0:
            return 100.0

        penalty = 0.0
        for state in self._states.values():
            w = state.baseline.criticality / total_weight
            if state.status == "critical":
                penalty += w * 78.0
            elif state.status == "degraded":
                penalty += w * 38.0
            # Fine-grained latency/error drag even before full status flip
            slo_ratio = max(
                0.0,
                (state.metrics.latency_ms - state.baseline.baseline_latency_ms)
                / max(1.0, state.baseline.slo_latency_ms * 4.0),
            )
            penalty += w * min(15.0, slo_ratio * 8.0 + state.metrics.error_rate * 25.0)

        return round(max(0.0, min(100.0, 100.0 - penalty)), 2)

    def get_status(self, *, running: bool) -> SimulationStatusResponse:
        """Return current simulation status summary."""
        healthy = sum(1 for s in self._states.values() if s.status == "healthy")
        degraded = sum(1 for s in self._states.values() if s.status == "degraded")
        critical = sum(1 for s in self._states.values() if s.status == "critical")
        active_incidents = sum(
            1 for inc in self.detector.list_incidents() if inc.status != "RESOLVED"
        )
        return SimulationStatusResponse(
            running=running,
            tick=self._tick,
            sim_time_s=self.sim_time_s,
            tick_interval_seconds=self.tick_interval_seconds,
            active_scenario=self._active_scenario,
            resilience_score=self.calculate_resilience_score(),
            total_services=len(self._states),
            healthy_services=healthy,
            degraded_services=degraded,
            critical_services=critical,
            active_incidents_count=active_incidents,
        )

    def get_topology_snapshot(self) -> TopologyResponse:
        """Return live topology nodes and edges with blast-radius / root-cause overlays."""
        active_incidents = [
            inc for inc in self.detector.list_incidents() if inc.status != "RESOLVED"
        ]
        blast_services: set[str] = set()
        root_candidates: set[str] = set()
        for inc in active_incidents:
            blast_services.update(inc.affected_services)
            if inc.root_cause_candidate:
                root_candidates.add(inc.root_cause_candidate)

        nodes: list[ServiceNodeState] = []
        for svc in self.topology.services:
            state = self._states[svc.id]
            nodes.append(
                ServiceNodeState(
                    id=svc.id,
                    name=svc.name,
                    tier=svc.tier,
                    status=state.status,
                    criticality=svc.criticality,
                    baseline_latency_ms=svc.baseline_latency_ms,
                    slo_latency_ms=svc.slo_latency_ms,
                    slo_error_rate=svc.slo_error_rate,
                    metrics=state.metrics,
                    in_blast_radius=svc.id in blast_services,
                    is_root_cause_candidate=svc.id in root_candidates,
                )
            )

        edges: list[DependencyEdgeState] = []
        for edge in self.topology.edges:
            target_state = self._states[edge.target_id]
            source_state = self._states[edge.source_id]
            edge_status = self._worst_status(source_state.status, target_state.status)
            edges.append(
                DependencyEdgeState(
                    id=edge.id,
                    source=edge.source_id,
                    target=edge.target_id,
                    protocol=edge.protocol,
                    impact_weight=edge.impact_weight,
                    status=edge_status,
                    latency_ms=target_state.metrics.latency_ms,
                )
            )

        return TopologyResponse(
            tick=self._tick,
            sim_time_s=self.sim_time_s,
            active_scenario=self._active_scenario,
            nodes=nodes,
            edges=edges,
        )

    def get_latest_telemetry(self, service_id: str | None = None) -> list[ServiceTelemetrySample]:
        """Return the latest telemetry sample for one or all services."""
        if service_id is not None:
            if service_id not in self._history:
                raise KeyError(f"Unknown service '{service_id}'.")
            return [self._history[service_id][-1]]
        return [self._history[svc.id][-1] for svc in self.topology.services]

    def get_telemetry_history(
        self, service_id: str | None = None, limit: int = 30
    ) -> list[ServiceTelemetrySample]:
        """Return recent telemetry samples ordered chronologically."""
        if service_id is not None:
            if service_id not in self._history:
                raise KeyError(f"Unknown service '{service_id}'.")
            return list(self._history[service_id])[-limit:]

        samples: list[ServiceTelemetrySample] = []
        for svc in self.topology.services:
            samples.extend(list(self._history[svc.id])[-limit:])
        samples.sort(key=lambda s: (s.tick, s.service_id))
        return samples

    def _record_samples(self) -> None:
        ts = self._current_sim_timestamp()
        for svc in self.topology.services:
            state = self._states[svc.id]
            self._history[svc.id].append(
                ServiceTelemetrySample(
                    tick=self._tick,
                    sim_time_s=self.sim_time_s,
                    timestamp=ts,
                    service_id=svc.id,
                    status=state.status,
                    metrics=state.metrics,
                )
            )

    @staticmethod
    def _worst_status(a: ServiceHealthStatus, b: ServiceHealthStatus) -> ServiceHealthStatus:
        rank = {"healthy": 0, "degraded": 1, "critical": 2}
        return a if rank[a] >= rank[b] else b

