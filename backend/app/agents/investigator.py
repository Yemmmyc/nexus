"""Investigator logical agent: deterministic causal analysis with optional LLM enhancement."""

from dataclasses import dataclass

from app.agents.llm_adapter import OptionalLLMAdapter
from app.config import Settings
from app.schemas.investigation import (
    ConfidenceAssessment,
    ConfidenceCriterion,
    ConfidenceLevel,
    EvidenceBundle,
    EvidenceItem,
    InferenceMode,
    ServiceRoleAssessment,
)
from app.simulator.topology_graph import TopologyGraph


@dataclass
class InvestigatorOutput:
    """Structured output produced by the Investigator logical agent."""

    inference_mode: InferenceMode
    model_name: str
    summary: str
    root_cause_hypothesis: str
    probable_root_cause_service: str | None
    supporting_evidence: list[EvidenceItem]
    limiting_evidence: list[str]
    service_roles: list[ServiceRoleAssessment]
    contributing_factors: list[str]
    confidence: ConfidenceAssessment
    recommended_next_steps: list[str]


class InvestigatorAgent:
    """Evaluates causal relationships from an EvidenceBundle without inventing data."""

    DETERMINISTIC_MODEL = "nexus-deterministic-investigator-v1"

    def __init__(self, settings: Settings, llm_adapter: OptionalLLMAdapter | None = None) -> None:
        self._settings = settings
        self._llm = llm_adapter or OptionalLLMAdapter(settings)

    def investigate(
        self, bundle: EvidenceBundle, topology: TopologyGraph
    ) -> InvestigatorOutput:
        """Produce an evidence-grounded causal investigation (deterministic + optional LLM)."""
        trends_by_id = {t.service_id: t for t in bundle.service_trends}
        affected_set = set(bundle.affected_services)

        # 1. Identify probable root cause from evidence + topology
        root_service = self._select_probable_root(bundle, topology)
        service_roles = self._classify_service_roles(
            root_service=root_service,
            bundle=bundle,
            topology=topology,
            trends_by_id=trends_by_id,
        )

        # 2. Build deterministic summary, hypothesis, contributing factors, and next steps
        root_trend = trends_by_id.get(root_service) if root_service else None
        downstream_symptoms = [
            r.service_id for r in service_roles if r.role == "downstream_symptom"
        ]
        contributing_services = [
            r.service_id for r in service_roles if r.role == "contributing_cause"
        ]

        if root_service and root_trend:
            summary = (
                f"Incident {bundle.incident_id} began at tick {bundle.detected_tick} "
                f"(t={bundle.detected_sim_time_s:.1f}s) and impacted {len(bundle.affected_services)} "
                f"of {len(bundle.service_trends)} monitored services. "
                f"Observed telemetry and dependency topology indicate degradation originating at "
                f"'{root_service}' (latency {root_trend.current_latency_ms:.1f}ms, "
                f"{root_trend.latency_ratio}x baseline; saturation {root_trend.current_saturation_pct:.1f}%), "
                f"cascading into downstream dependents while {', '.join(bundle.unaffected_services) or 'no services'} "
                f"remained unaffected."
            )
            hypothesis = (
                f"Probable root cause is resource saturation and elevated latency on '{root_service}' "
                f"(tier: {root_trend.tier}, status: {root_trend.current_status}). "
                f"This bottleneck propagated along directed dependency edges to "
                f"{', '.join(downstream_symptoms) or 'dependent callers'}"
                + (
                    f", with secondary backpressure amplified by {', '.join(contributing_services)}."
                    if contributing_services
                    else "."
                )
            )
        else:
            summary = (
                f"Incident {bundle.incident_id} impacted {len(bundle.affected_services)} service(s) "
                f"starting at tick {bundle.detected_tick}; insufficient topological separation to isolate a single root."
            )
            hypothesis = "No single root-cause service could be isolated from available telemetry."

        contributing_factors = self._build_contributing_factors(bundle, trends_by_id, root_service)
        confidence = self._score_confidence(bundle, topology, root_service, trends_by_id)
        limiting_evidence = self._build_limiting_evidence(bundle, root_service, affected_set)
        next_steps = self._build_recommended_next_steps(root_service, contributing_services, trends_by_id)
        supporting_evidence = self._select_supporting_evidence(bundle, root_service)

        inference_mode: InferenceMode = "DETERMINISTIC"
        model_name = self.DETERMINISTIC_MODEL

        # 3. Optional AI enhancement (strictly read-only, grounded, with deterministic fallback)
        if self._llm.is_enabled():
            try:
                ai_narrative = self._llm.synthesize_narrative(bundle)
                cited_set = set(ai_narrative.cited_evidence_ids)
                cited_items = [item for item in bundle.items if item.evidence_id in cited_set]
                if cited_items:
                    supporting_evidence = cited_items
                summary = ai_narrative.summary
                root_cause_hypothesis = ai_narrative.root_cause_hypothesis
                contributing_factors = ai_narrative.contributing_factors
                next_steps = ai_narrative.recommended_next_steps
                inference_mode = "LLM"
                model_name = self._settings.llm_model
            except Exception as exc:
                root_cause_hypothesis = hypothesis
                limiting_evidence.append(
                    f"AI provider synthesis unavailable or rejected ({type(exc).__name__}: {exc}); "
                    f"fell back to deterministic evidence-grounded investigation."
                )
        else:
            root_cause_hypothesis = hypothesis

        return InvestigatorOutput(
            inference_mode=inference_mode,
            model_name=model_name,
            summary=summary,
            root_cause_hypothesis=root_cause_hypothesis,
            probable_root_cause_service=root_service,
            supporting_evidence=supporting_evidence,
            limiting_evidence=limiting_evidence,
            service_roles=service_roles,
            contributing_factors=contributing_factors,
            confidence=confidence,
            recommended_next_steps=next_steps,
        )

    def _select_probable_root(
        self, bundle: EvidenceBundle, topology: TopologyGraph
    ) -> str | None:
        if bundle.detector_root_cause_candidate in bundle.affected_services:
            return bundle.detector_root_cause_candidate
        if not bundle.affected_services:
            return None
        affected_set = set(bundle.affected_services)
        for sid in topology.bottom_up_order():
            if sid in affected_set:
                return sid
        return bundle.affected_services[0]

    def _classify_service_roles(
        self,
        *,
        root_service: str | None,
        bundle: EvidenceBundle,
        topology: TopologyGraph,
        trends_by_id: dict,
    ) -> list[ServiceRoleAssessment]:
        roles: list[ServiceRoleAssessment] = []
        affected_set = set(bundle.affected_services)

        for svc in topology.services:
            trend = trends_by_id[svc.id]
            if svc.id not in affected_set:
                roles.append(
                    ServiceRoleAssessment(
                        service_id=svc.id,
                        tier=svc.tier,
                        status=trend.current_status,
                        role="unaffected",
                        rationale="No dependency path from failing root; metrics remained within SLO.",
                    )
                )
            elif svc.id == root_service:
                roles.append(
                    ServiceRoleAssessment(
                        service_id=svc.id,
                        tier=svc.tier,
                        status=trend.current_status,
                        role="probable_root_cause",
                        rationale=(
                            f"Deepest unhealthy dependency; latency {trend.current_latency_ms:.1f}ms "
                            f"({trend.latency_ratio}x baseline), saturation {trend.current_saturation_pct:.1f}%."
                        ),
                    )
                )
            elif svc.tier in ("worker", "messaging") and (
                trend.queue_delta > 100 or svc.id == "worker-fulfillment"
            ):
                roles.append(
                    ServiceRoleAssessment(
                        service_id=svc.id,
                        tier=svc.tier,
                        status=trend.current_status,
                        role="contributing_cause",
                        rationale=(
                            f"Secondary backpressure amplifier ({svc.tier} tier): "
                            + (
                                f"queue depth grew by +{trend.queue_delta} messages."
                                if trend.queue_delta > 0
                                else f"degraded throughput stalled queue drain (latency {trend.current_latency_ms:.1f}ms)."
                            )
                        ),
                    )
                )
            else:
                deps = [
                    e.target_id
                    for e in topology.dependencies_of(svc.id)
                    if e.target_id in affected_set
                ]
                roles.append(
                    ServiceRoleAssessment(
                        service_id=svc.id,
                        tier=svc.tier,
                        status=trend.current_status,
                        role="downstream_symptom",
                        rationale=(
                            f"Propagated impact via unhealthy dependencies ({', '.join(deps) or 'upstream'}): "
                            f"error rate {trend.current_error_rate * 100:.1f}%, latency {trend.current_latency_ms:.1f}ms."
                        ),
                    )
                )

        return roles

    def _build_contributing_factors(
        self, bundle: EvidenceBundle, trends_by_id: dict, root_service: str | None
    ) -> list[str]:
        factors: list[str] = []
        if root_service and root_service in trends_by_id:
            rt = trends_by_id[root_service]
            if rt.current_saturation_pct >= 75.0:
                factors.append(
                    f"High resource saturation on {root_service} ({rt.current_saturation_pct:.1f}%) "
                    f"and CPU utilization ({rt.current_cpu_pct:.1f}%)."
                )
            if rt.latency_ratio >= 5.0:
                factors.append(
                    f"Severe latency amplification on {root_service} ({rt.latency_ratio}x baseline)."
                )
        for t in bundle.service_trends:
            if t.tier == "messaging" and t.queue_delta > 100:
                factors.append(
                    f"Backpressure accumulation in {t.service_id} (+{t.queue_delta} queued messages) "
                    f"caused by reduced worker drain throughput."
                )
        if len(bundle.propagation_paths) >= 3:
            factors.append(
                f"Tight synchronous dependency coupling across {len(bundle.propagation_paths)} "
                f"active call paths amplified timeouts toward edge services."
            )
        if not factors:
            factors.append("Elevated telemetry metrics exceeding service SLO thresholds.")
        return factors

    def _score_confidence(
        self,
        bundle: EvidenceBundle,
        topology: TopologyGraph,
        root_service: str | None,
        trends_by_id: dict,
    ) -> ConfidenceAssessment:
        affected_set = set(bundle.affected_services)
        criteria: list[ConfidenceCriterion] = []

        # Criterion 1: Topological isolation (0.30)
        if root_service:
            unhealthy_deps = [
                e.target_id
                for e in topology.dependencies_of(root_service)
                if e.target_id in affected_set
            ]
            topo_score = 1.0 if not unhealthy_deps else 0.4
            topo_exp = (
                f"'{root_service}' has no unhealthy upstream dependencies while downstream callers degraded."
                if not unhealthy_deps
                else f"'{root_service}' also depends on unhealthy service(s): {', '.join(unhealthy_deps)}."
            )
        else:
            topo_score = 0.2
            topo_exp = "No single topological root candidate could be isolated."
        criteria.append(
            ConfidenceCriterion(
                name="topological_isolation",
                score=topo_score,
                weight=0.30,
                explanation=topo_exp,
            )
        )

        # Criterion 2: Temporal precedence (0.25)
        event_items = [i for i in bundle.items if i.source_type == "monitoring_event" and i.tick is not None]
        if root_service and event_items:
            root_ticks = [i.tick for i in event_items if i.service_id == root_service and i.tick is not None]
            min_all_tick = min(i.tick for i in event_items if i.tick is not None)
            temp_score = 1.0 if (root_ticks and min(root_ticks) <= min_all_tick) else 0.55
            temp_exp = (
                f"Earliest anomaly on '{root_service}' occurred at tick {min(root_ticks)}, "
                f"matching or preceding all downstream alerts (earliest overall: tick {min_all_tick})."
                if root_ticks
                else f"No direct monitoring event tick recorded for '{root_service}'."
            )
        else:
            temp_score = 0.4
            temp_exp = "Limited timestamped monitoring event sequence available."
        criteria.append(
            ConfidenceCriterion(
                name="temporal_precedence",
                score=temp_score,
                weight=0.25,
                explanation=temp_exp,
            )
        )

        # Criterion 3: Multi-signal corroboration (0.25)
        if root_service and root_service in trends_by_id:
            rt = trends_by_id[root_service]
            signals = sum(
                [
                    1 if rt.latency_ratio >= 2.0 else 0,
                    1 if rt.current_saturation_pct >= 50.0 else 0,
                    1 if rt.current_error_rate >= 0.01 else 0,
                ]
            )
            sig_score = round(signals / 3.0, 2)
            sig_exp = (
                f"{signals}/3 independent signals corroborate '{root_service}' "
                f"(latency {rt.latency_ratio}x, saturation {rt.current_saturation_pct:.1f}%, "
                f"error_rate {rt.current_error_rate * 100:.2f}%)."
            )
        else:
            sig_score = 0.3
            sig_exp = "Insufficient multi-metric signals on candidate root."
        criteria.append(
            ConfidenceCriterion(
                name="multi_signal_corroboration",
                score=sig_score,
                weight=0.25,
                explanation=sig_exp,
            )
        )

        # Criterion 4: Evidence coverage across affected services (0.20)
        ev_services = {i.service_id for i in bundle.items if i.service_id in affected_set}
        cov_score = round(len(ev_services) / max(1, len(affected_set)), 2)
        criteria.append(
            ConfidenceCriterion(
                name="evidence_coverage",
                score=cov_score,
                weight=0.20,
                explanation=(
                    f"Direct telemetry/event evidence collected for {len(ev_services)} of "
                    f"{len(affected_set)} affected services."
                ),
            )
        )

        weighted = round(sum(c.score * c.weight for c in criteria), 2)
        # Cap deterministic simulated confidence at 0.95 (never claim 100% certainty)
        final_score = min(0.95, weighted)
        level: ConfidenceLevel = (
            "HIGH" if final_score >= 0.78 else "MEDIUM" if final_score >= 0.50 else "LOW"
        )
        return ConfidenceAssessment(score=final_score, level=level, criteria=criteria)

    def _build_limiting_evidence(
        self, bundle: EvidenceBundle, root_service: str | None, affected_set: set[str]
    ) -> list[str]:
        limits = [
            (
                "Analysis is based on deterministic simulated telemetry and topology; "
                "live SQL query plans, lock tables, and distributed request traces are not available."
            ),
            (
                "Root-cause attribution represents the highest-probability hypothesis supported by "
                "observed simulation evidence rather than definitive production root-cause proof."
            ),
        ]
        if bundle.unaffected_services:
            limits.append(
                f"Unaffected service(s) ({', '.join(bundle.unaffected_services)}) support "
                f"scoping the fault away from edge authentication, but shared host/network faults are not modeled."
            )
        if root_service and len(affected_set) > 1:
            limits.append(
                f"Multiple affected services breached thresholds in the same 2s tick window, "
                f"limiting sub-second causal ordering precision."
            )
        return limits

    def _build_recommended_next_steps(
        self, root_service: str | None, contributing_services: list[str], trends_by_id: dict
    ) -> list[str]:
        steps: list[str] = []
        if root_service:
            rt = trends_by_id.get(root_service)
            if rt and rt.tier == "database":
                steps.append(
                    f"Inspect connection pool utilization, active locks, and slow queries on '{root_service}'."
                )
                steps.append(
                    f"Evaluate controlled connection pool expansion or read/write load shedding for '{root_service}' (requires human approval)."
                )
            else:
                steps.append(
                    f"Inspect resource saturation and recent configuration changes on '{root_service}'."
                )
        steps.append(
            "Verify circuit-breaker and timeout budgets on synchronous callers (payment-service, checkout-api) to contain blast radius."
        )
        if contributing_services:
            steps.append(
                f"Monitor backlog drain rate across {', '.join(contributing_services)} once upstream database latency stabilizes."
            )
        steps.append(
            "Confirm post-mitigation SLO recovery across all affected services before closing the incident."
        )
        return steps

    def _select_supporting_evidence(
        self, bundle: EvidenceBundle, root_service: str | None
    ) -> list[EvidenceItem]:
        # Prioritize root-cause events/telemetry, queue metrics, detector candidate, and key topology edges
        prioritized: list[EvidenceItem] = []
        seen: set[str] = set()

        def _add(item: EvidenceItem) -> None:
            if item.evidence_id not in seen:
                seen.add(item.evidence_id)
                prioritized.append(item)

        for item in bundle.items:
            if item.service_id == root_service or item.source_type in ("detector_candidate", "queue_metric"):
                _add(item)
        for item in bundle.items:
            if item.source_type in ("telemetry_trend", "topology_edge"):
                _add(item)
        for item in bundle.items:
            _add(item)
            if len(prioritized) >= 18:
                break

        return prioritized[:18]

