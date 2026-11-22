"""Deterministic threshold monitoring and topological incident detection."""

from datetime import datetime

from app.schemas.simulation import DetectedIncident
from app.schemas.telemetry import MonitoringEvent, SeverityLevel
from app.simulator.models import ServiceRuntimeState
from app.simulator.topology_graph import TopologyGraph


class IncidentDetector:
    """Detects threshold breaches and correlates connected alerts into incidents."""

    def __init__(self, topology: TopologyGraph) -> None:
        self._topology = topology
        self._event_counter = 0
        self._incident_counter = 0
        self._incidents: dict[str, DetectedIncident] = {}
        self._first_anomaly_tick: dict[str, int] = {}

    def reset(self) -> None:
        """Clear all tracked incidents and anomaly state."""
        self._event_counter = 0
        self._incident_counter = 0
        self._incidents.clear()
        self._first_anomaly_tick.clear()

    def list_incidents(self) -> list[DetectedIncident]:
        """Return detected incidents ordered newest first."""
        return sorted(
            self._incidents.values(),
            key=lambda inc: (inc.detected_tick, inc.id),
            reverse=True,
        )

    def get_incident(self, incident_id: str) -> DetectedIncident | None:
        """Return a single incident by ID."""
        return self._incidents.get(incident_id)

    def evaluate_tick(
        self,
        *,
        tick: int,
        sim_time_s: float,
        timestamp: datetime,
        states: dict[str, ServiceRuntimeState],
        active_scenario: str | None,
    ) -> tuple[list[MonitoringEvent], list[DetectedIncident]]:
        """Generate monitoring events for breached thresholds and correlate into incidents."""
        tick_events: list[MonitoringEvent] = []
        unhealthy_services: list[str] = []

        for service in self._topology.services:
            state = states[service.id]
            if state.status == "healthy":
                self._first_anomaly_tick.pop(service.id, None)
                continue

            unhealthy_services.append(service.id)
            if service.id not in self._first_anomaly_tick:
                self._first_anomaly_tick[service.id] = tick

            tick_events.extend(
                self._detect_service_events(
                    tick=tick,
                    sim_time_s=sim_time_s,
                    timestamp=timestamp,
                    state=state,
                )
            )

        newly_created: list[DetectedIncident] = []
        if not unhealthy_services:
            # Resolve any previously active incidents if all services are healthy again
            for inc_id, inc in list(self._incidents.items()):
                if inc.status != "RESOLVED":
                    self._incidents[inc_id] = inc.model_copy(
                        update={
                            "status": "RESOLVED",
                            "updated_tick": tick,
                            "updated_at": timestamp,
                        }
                    )
            return tick_events, newly_created

        # Group unhealthy services into connected components in the topology
        components = self._connected_components(unhealthy_services)
        for component in components:
            comp_set = set(component)
            comp_events = [ev for ev in tick_events if ev.service_id in comp_set]
            existing_id = self._find_matching_active_incident(comp_set)
            severity = self._classify_severity(component, states)
            root_candidate, rationale = self._identify_root_cause_candidate(component, states)

            if existing_id is not None:
                existing = self._incidents[existing_id]
                merged_services = sorted(set(existing.affected_services) | comp_set)
                # Keep triggering evidence bounded & recent while preserving initial signals
                merged_evidence = (existing.triggering_evidence + comp_events)[-25:]
                self._incidents[existing_id] = existing.model_copy(
                    update={
                        "status": "ACTIVE",
                        "severity": self._max_severity(existing.severity, severity),
                        "affected_services": merged_services,
                        "root_cause_candidate": root_candidate,
                        "root_cause_rationale": rationale,
                        "triggering_evidence": merged_evidence,
                        "updated_tick": tick,
                        "updated_at": timestamp,
                    }
                )
            else:
                self._incident_counter += 1
                inc_id = f"INC-{self._incident_counter:04d}"
                title = (
                    f"Cascading degradation rooted near {root_candidate}"
                    if root_candidate
                    else f"Service degradation across {len(component)} service(s)"
                )
                incident = DetectedIncident(
                    id=inc_id,
                    title=title,
                    scenario_id=active_scenario,
                    status="DETECTED",
                    severity=severity,
                    affected_services=sorted(component),
                    root_cause_candidate=root_candidate,
                    root_cause_rationale=rationale,
                    triggering_evidence=comp_events,
                    detected_tick=tick,
                    detected_at=timestamp,
                    updated_tick=tick,
                    updated_at=timestamp,
                )
                self._incidents[inc_id] = incident
                newly_created.append(incident)

        return tick_events, newly_created

    def _detect_service_events(
        self,
        *,
        tick: int,
        sim_time_s: float,
        timestamp: datetime,
        state: ServiceRuntimeState,
    ) -> list[MonitoringEvent]:
        events: list[MonitoringEvent] = []
        b = state.baseline
        m = state.metrics

        if m.latency_ms >= b.slo_latency_ms * 1.25:
            sev: SeverityLevel = "CRITICAL" if m.latency_ms >= b.slo_latency_ms * 3.0 else "HIGH"
            events.append(
                self._make_event(
                    tick=tick,
                    sim_time_s=sim_time_s,
                    timestamp=timestamp,
                    service_id=b.id,
                    event_type="LATENCY_SLO_BREACH",
                    severity=sev,
                    metric_name="latency_ms",
                    metric_value=m.latency_ms,
                    threshold_value=b.slo_latency_ms,
                    message=f"{b.id} latency {m.latency_ms:.1f}ms exceeds SLO {b.slo_latency_ms:.1f}ms",
                )
            )

        if m.error_rate >= b.slo_error_rate * 2.0:
            sev = "CRITICAL" if m.error_rate >= max(0.10, b.slo_error_rate * 5.0) else "HIGH"
            events.append(
                self._make_event(
                    tick=tick,
                    sim_time_s=sim_time_s,
                    timestamp=timestamp,
                    service_id=b.id,
                    event_type="ERROR_RATE_SPIKE",
                    severity=sev,
                    metric_name="error_rate",
                    metric_value=m.error_rate,
                    threshold_value=b.slo_error_rate,
                    message=f"{b.id} error rate {m.error_rate * 100:.1f}% exceeds SLO {b.slo_error_rate * 100:.2f}%",
                )
            )

        if m.saturation_pct >= 75.0:
            sev = "CRITICAL" if m.saturation_pct >= 90.0 else "HIGH"
            events.append(
                self._make_event(
                    tick=tick,
                    sim_time_s=sim_time_s,
                    timestamp=timestamp,
                    service_id=b.id,
                    event_type="RESOURCE_SATURATION",
                    severity=sev,
                    metric_name="saturation_pct",
                    metric_value=m.saturation_pct,
                    threshold_value=75.0,
                    message=f"{b.id} resource saturation at {m.saturation_pct:.1f}%",
                )
            )

        if m.queue_depth >= 250:
            sev = "CRITICAL" if m.queue_depth >= 1000 else "MEDIUM"
            events.append(
                self._make_event(
                    tick=tick,
                    sim_time_s=sim_time_s,
                    timestamp=timestamp,
                    service_id=b.id,
                    event_type="QUEUE_BACKLOG_ACCUMULATION",
                    severity=sev,
                    metric_name="queue_depth",
                    metric_value=float(m.queue_depth),
                    threshold_value=250.0,
                    message=f"{b.id} backlog accumulated to {m.queue_depth} pending messages",
                )
            )

        return events

    def _make_event(
        self,
        *,
        tick: int,
        sim_time_s: float,
        timestamp: datetime,
        service_id: str,
        event_type: str,
        severity: SeverityLevel,
        metric_name: str,
        metric_value: float,
        threshold_value: float,
        message: str,
    ) -> MonitoringEvent:
        self._event_counter += 1
        return MonitoringEvent(
            id=f"EVT-{self._event_counter:05d}",
            tick=tick,
            sim_time_s=sim_time_s,
            timestamp=timestamp,
            service_id=service_id,
            event_type=event_type,
            severity=severity,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold_value=threshold_value,
            message=message,
        )

    def _connected_components(self, service_ids: list[str]) -> list[list[str]]:
        remaining = list(service_ids)
        components: list[list[str]] = []
        while remaining:
            seed = remaining.pop(0)
            comp = [seed]
            changed = True
            while changed:
                changed = False
                for other in list(remaining):
                    if any(self._topology.are_connected(member, other) for member in comp):
                        comp.append(other)
                        remaining.remove(other)
                        changed = True
            components.append(comp)
        return components

    def _find_matching_active_incident(self, component: set[str]) -> str | None:
        for inc_id, inc in self._incidents.items():
            if inc.status == "RESOLVED":
                continue
            existing_set = set(inc.affected_services)
            if existing_set & component:
                return inc_id
            if any(
                self._topology.are_connected(a, b) for a in existing_set for b in component
            ):
                return inc_id
        return None

    def _classify_severity(
        self, component: list[str], states: dict[str, ServiceRuntimeState]
    ) -> SeverityLevel:
        critical_count = sum(1 for sid in component if states[sid].status == "critical")
        max_crit = max(states[sid].baseline.criticality for sid in component)

        if critical_count >= 2 or (critical_count >= 1 and len(component) >= 3 and max_crit >= 5):
            return "CRITICAL"
        if critical_count >= 1 or len(component) >= 3:
            return "HIGH"
        if len(component) >= 2:
            return "MEDIUM"
        return "LOW"

    def _identify_root_cause_candidate(
        self, component: list[str], states: dict[str, ServiceRuntimeState]
    ) -> tuple[str | None, str | None]:
        """Deterministically pick the deepest unhealthy dependency with earliest anomaly."""
        comp_set = set(component)
        bottom_up = self._topology.bottom_up_order()
        depth_rank = {sid: idx for idx, sid in enumerate(bottom_up)}

        # Prefer unhealthy services that have NO unhealthy outgoing dependencies
        leaf_unhealthy = [
            sid
            for sid in component
            if not any(
                edge.target_id in comp_set for edge in self._topology.dependencies_of(sid)
            )
        ]
        candidates = leaf_unhealthy or component

        best = min(
            candidates,
            key=lambda sid: (
                self._first_anomaly_tick.get(sid, 10**9),
                depth_rank.get(sid, 10**9),
                -states[sid].metrics.saturation_pct,
            ),
        )
        m = states[best].metrics
        rationale = (
            f"Deepest unhealthy dependency in affected subgraph ({len(component)} impacted services); "
            f"first anomalous at tick {self._first_anomaly_tick.get(best, 0)} with "
            f"latency={m.latency_ms:.1f}ms, saturation={m.saturation_pct:.1f}%."
        )
        return best, rationale

    @staticmethod
    def _max_severity(a: SeverityLevel, b: SeverityLevel) -> SeverityLevel:
        order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        return a if order[a] >= order[b] else b

