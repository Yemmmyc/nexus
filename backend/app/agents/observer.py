"""Observer logical agent: collects and organizes traceable incident evidence."""

from app.schemas.investigation import EvidenceBundle, EvidenceItem, ServiceTrendSummary
from app.schemas.simulation import DetectedIncident
from app.simulator.engine import SimulationEngine


class ObserverAgent:
    """Collects non-fabricated evidence directly from simulator telemetry, topology, and events."""

    def collect(self, incident: DetectedIncident, engine: SimulationEngine) -> EvidenceBundle:
        """Assemble a traceable EvidenceBundle for the given incident."""
        topo = engine.get_topology_snapshot()
        nodes_by_id = {n.id: n for n in topo.nodes}
        affected_set = set(incident.affected_services)
        unaffected = sorted(n.id for n in topo.nodes if n.id not in affected_set)

        items: list[EvidenceItem] = []
        trends: list[ServiceTrendSummary] = []

        # 1. Monitoring events correlated into this incident
        for ev in incident.triggering_evidence:
            items.append(
                EvidenceItem(
                    evidence_id=f"EVID-{ev.id}",
                    source_type="monitoring_event",
                    source_ref=ev.id,
                    service_id=ev.service_id,
                    tick=ev.tick,
                    metric_name=ev.metric_name,
                    metric_value=ev.metric_value,
                    observation=f"[{ev.severity}] {ev.message}",
                )
            )

        # 2. Telemetry trends (baseline vs current) and detection-tick snapshots
        for svc in engine.topology.services:
            node = nodes_by_id[svc.id]
            history = engine.get_telemetry_history(service_id=svc.id, limit=120)
            baseline_sample = history[0] if history else None
            base_lat = baseline_sample.metrics.latency_ms if baseline_sample else svc.baseline_latency_ms
            base_q = baseline_sample.metrics.queue_depth if baseline_sample else svc.baseline_queue_depth
            lat_ratio = round(node.metrics.latency_ms / max(0.1, base_lat), 2)
            q_delta = node.metrics.queue_depth - base_q

            trends.append(
                ServiceTrendSummary(
                    service_id=svc.id,
                    tier=svc.tier,
                    current_status=node.status,
                    baseline_latency_ms=round(base_lat, 2),
                    current_latency_ms=node.metrics.latency_ms,
                    latency_ratio=lat_ratio,
                    current_error_rate=node.metrics.error_rate,
                    current_cpu_pct=node.metrics.cpu_pct,
                    current_saturation_pct=node.metrics.saturation_pct,
                    current_queue_depth=node.metrics.queue_depth,
                    queue_delta=q_delta,
                )
            )

            if svc.id in affected_set:
                items.append(
                    EvidenceItem(
                        evidence_id=f"EVID-TEL-{svc.id}-T{engine.tick}",
                        source_type="telemetry_trend",
                        source_ref=f"telemetry:{svc.id}:tick-{engine.tick}",
                        service_id=svc.id,
                        tick=engine.tick,
                        metric_name="latency_ms",
                        metric_value=node.metrics.latency_ms,
                        observation=(
                            f"{svc.id} ({node.status}) latency moved from {base_lat:.1f}ms to "
                            f"{node.metrics.latency_ms:.1f}ms ({lat_ratio}x baseline), "
                            f"error_rate={node.metrics.error_rate * 100:.1f}%, "
                            f"saturation={node.metrics.saturation_pct:.1f}%, cpu={node.metrics.cpu_pct:.1f}%."
                        ),
                    )
                )

                if svc.tier == "messaging" and q_delta > 0:
                    items.append(
                        EvidenceItem(
                            evidence_id=f"EVID-QUEUE-{svc.id}-T{engine.tick}",
                            source_type="queue_metric",
                            source_ref=f"queue:{svc.id}:tick-{engine.tick}",
                            service_id=svc.id,
                            tick=engine.tick,
                            metric_name="queue_depth",
                            metric_value=float(node.metrics.queue_depth),
                            observation=(
                                f"{svc.id} backlog rose by +{q_delta} messages "
                                f"(baseline {base_q} -> current {node.metrics.queue_depth})."
                            ),
                        )
                    )

        # 3. Topology propagation edges connecting affected services
        propagation_paths: list[str] = []
        for edge in topo.edges:
            if edge.source in affected_set and edge.target in affected_set:
                path_label = f"{edge.source} -> {edge.target} ({edge.protocol}, weight={edge.impact_weight})"
                propagation_paths.append(path_label)
                items.append(
                    EvidenceItem(
                        evidence_id=f"EVID-TOPO-{edge.id}",
                        source_type="topology_edge",
                        source_ref=edge.id,
                        service_id=edge.source,
                        tick=engine.tick,
                        metric_name="latency_ms",
                        metric_value=edge.latency_ms,
                        observation=(
                            f"Dependency {edge.source} -> {edge.target} ({edge.protocol}, "
                            f"impact_weight={edge.impact_weight}) is {edge.status} "
                            f"with target latency {edge.latency_ms:.1f}ms."
                        ),
                    )
                )

        # 4. Detector's initial root-cause candidate signal
        if incident.root_cause_candidate:
            items.append(
                EvidenceItem(
                    evidence_id=f"EVID-DET-{incident.id}",
                    source_type="detector_candidate",
                    source_ref=incident.id,
                    service_id=incident.root_cause_candidate,
                    tick=incident.detected_tick,
                    observation=(
                        f"Deterministic detector flagged '{incident.root_cause_candidate}' "
                        f"as initial candidate: {incident.root_cause_rationale or 'topological root'}."
                    ),
                )
            )

        return EvidenceBundle(
            incident_id=incident.id,
            collected_at_tick=engine.tick,
            collected_sim_time_s=engine.sim_time_s,
            detected_tick=incident.detected_tick,
            detected_sim_time_s=round(incident.detected_tick * engine.tick_interval_seconds, 2),
            affected_services=sorted(affected_set),
            unaffected_services=unaffected,
            detector_root_cause_candidate=incident.root_cause_candidate,
            detector_rationale=incident.root_cause_rationale,
            service_trends=trends,
            propagation_paths=propagation_paths,
            items=items,
        )

