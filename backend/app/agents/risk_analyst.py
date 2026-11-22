"""Risk Analyst logical agent: deterministic blast-radius and operational risk scoring."""

from app.schemas.investigation import BlastRadiusAssessment, EvidenceBundle
from app.schemas.telemetry import SeverityLevel
from app.simulator.topology_graph import TopologyGraph


class RiskAnalystAgent:
    """Computes explainable blast-radius and composite operational risk (0-100)."""

    def assess(self, bundle: EvidenceBundle, topology: TopologyGraph) -> BlastRadiusAssessment:
        """Evaluate operational impact, customer exposure, and risk score."""
        trends_by_id = {t.service_id: t for t in bundle.service_trends}
        total_services = len(topology.services)
        impacted = sorted(bundle.affected_services)
        unaffected = sorted(bundle.unaffected_services)

        total_criticality = sum(s.criticality for s in topology.services)
        impacted_criticality = sum(
            topology.get_service(sid).criticality for sid in impacted
        )
        criticality_ratio = impacted_criticality / max(1, total_criticality)
        blast_ratio = len(impacted) / max(1, total_services)

        max_error = max(
            (trends_by_id[sid].current_error_rate for sid in impacted), default=0.0
        )
        max_queue = max(
            (trends_by_id[sid].current_queue_depth for sid in impacted), default=0
        )
        queue_pressure = min(1.0, max(0.0, (max_queue - 50) / 1000.0))

        customer_facing = any(
            sid in impacted for sid in ("api-gateway", "checkout-api", "payment-service")
        )

        # Transparent 0-100 weighted composite formula
        f_crit = round(criticality_ratio * 35.0, 2)
        f_blast = round(blast_ratio * 25.0, 2)
        f_err = round(min(1.0, max_error / 0.50) * 25.0, 2)
        f_queue = round(queue_pressure * 15.0, 2)
        risk_score = int(round(min(100.0, max(0.0, f_crit + f_blast + f_err + f_queue))))

        risk_level: SeverityLevel = (
            "CRITICAL"
            if risk_score >= 75
            else "HIGH"
            if risk_score >= 50
            else "MEDIUM"
            if risk_score >= 25
            else "LOW"
        )

        if customer_facing:
            impact_summary = (
                f"High customer-facing impact: {len(impacted)} of {total_services} services degraded "
                f"(including checkout/payment/edge path), peak error rate {max_error * 100:.1f}%"
                + (f", and {max_queue} queued orders awaiting fulfillment." if max_queue >= 100 else ".")
            )
        else:
            impact_summary = (
                f"Contained internal impact across {len(impacted)} of {total_services} services "
                f"with no direct edge/checkout disruption detected."
            )

        return BlastRadiusAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            impacted_services=impacted,
            unaffected_services=unaffected,
            impacted_service_count=len(impacted),
            total_service_count=total_services,
            customer_facing_impact=customer_facing,
            business_impact_summary=impact_summary,
            factors={
                "criticality_weight": f_crit,
                "blast_radius_ratio": f_blast,
                "error_severity": f_err,
                "queue_backlog_pressure": f_queue,
            },
        )

