export type SeverityLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type IncidentStatus = "DETECTED" | "ACTIVE" | "RESOLVED";
export type InvestigationStatus = "NOT_STARTED" | "RUNNING" | "COMPLETED" | "FAILED";
export type ServiceHealthStatus = "healthy" | "degraded" | "critical";
export type ServiceCausalRole =
  | "probable_root_cause"
  | "contributing_cause"
  | "downstream_symptom"
  | "unaffected";

export interface MonitoringEvent {
  id: string;
  tick: number;
  sim_time_s: number;
  timestamp: string;
  service_id: string;
  event_type: string;
  severity: SeverityLevel;
  metric_name: string;
  metric_value: number;
  threshold_value: number;
  message: string;
}

export interface DetectedIncident {
  id: string;
  title: string;
  scenario_id: string | null;
  status: IncidentStatus;
  severity: SeverityLevel;
  affected_services: string[];
  root_cause_candidate: string | null;
  root_cause_rationale: string | null;
  triggering_evidence: MonitoringEvent[];
  detected_tick: number;
  detected_sim_time_s: number;
  detected_at: string;
  updated_tick: number;
  updated_at: string;
  investigation_status: InvestigationStatus;
}

export interface EvidenceItem {
  evidence_id: string;
  source_type: string;
  source_ref: string;
  service_id: string | null;
  tick: number | null;
  metric_name: string | null;
  metric_value: number | null;
  observation: string;
}

export interface ServiceRoleAssessment {
  service_id: string;
  tier: string;
  status: ServiceHealthStatus;
  role: ServiceCausalRole;
  rationale: string;
}

export interface ConfidenceCriterion {
  name: string;
  score: number;
  weight: number;
  explanation: string;
}

export interface ConfidenceAssessment {
  score: number;
  level: "LOW" | "MEDIUM" | "HIGH";
  criteria: ConfidenceCriterion[];
}

export interface BlastRadiusAssessment {
  risk_score: number;
  risk_level: SeverityLevel;
  impacted_services: string[];
  unaffected_services: string[];
  impacted_service_count: number;
  total_service_count: number;
  customer_facing_impact: boolean;
  business_impact_summary: string;
  factors: Record<string, number>;
}

export interface LogicalAgentTrace {
  agent_role: "Observer" | "Investigator" | "Risk Analyst";
  status: "COMPLETED" | "FAILED";
  inference_mode: "DETERMINISTIC" | "LLM";
  duration_ms: number;
  summary: string;
}

export interface InvestigationResult {
  id: string;
  incident_id: string;
  status: "COMPLETED" | "FAILED";
  inference_mode: "DETERMINISTIC" | "LLM";
  model_name: string;
  summary: string;
  root_cause_hypothesis: string;
  probable_root_cause_service: string | null;
  supporting_evidence: EvidenceItem[];
  limiting_evidence: string[];
  affected_services: string[];
  service_roles: ServiceRoleAssessment[];
  contributing_factors: string[];
  blast_radius: BlastRadiusAssessment;
  confidence: ConfidenceAssessment;
  recommended_next_steps: string[];
  agent_trace: LogicalAgentTrace[];
  created_at: string;
  updated_at: string;
}

export interface TimelineEntry {
  timestamp: string;
  source: "MONITORING_EVENT" | "AUDIT_LOG";
  event_type: string;
  actor: string;
  service_id: string | null;
  tick: number | null;
  summary: string;
  details: Record<string, unknown>;
}

export interface IncidentTimelineResponse {
  incident_id: string;
  entries: TimelineEntry[];
}

