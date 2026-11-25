import type { AuditCategory, AuditLogListResponse } from "../types/audit";
import type { HealthResponse, SimulationStatusResponse } from "../types/health";
import type {
  DetectedIncident,
  IncidentTimelineResponse,
  InvestigationResult,
} from "../types/incidents";
import type { RemediationPlan, VerificationResult } from "../types/remediation";
import type { TopologyResponse } from "../types/topology";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}

export function fetchSimulationStatus(): Promise<SimulationStatusResponse> {
  return requestJson<SimulationStatusResponse>("/simulation/status");
}

export function startSimulation(): Promise<SimulationStatusResponse> {
  return requestJson<SimulationStatusResponse>("/simulation/start", { method: "POST" });
}

export function stopSimulation(): Promise<SimulationStatusResponse> {
  return requestJson<SimulationStatusResponse>("/simulation/stop", { method: "POST" });
}

export function advanceSimulation(ticks = 1): Promise<SimulationStatusResponse> {
  return requestJson<SimulationStatusResponse>("/simulation/advance", {
    method: "POST",
    body: JSON.stringify({ ticks }),
  });
}

export function injectScenario(scenarioId: string): Promise<SimulationStatusResponse> {
  return requestJson<SimulationStatusResponse>("/simulation/inject", {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function resetSimulation(): Promise<SimulationStatusResponse> {
  return requestJson<SimulationStatusResponse>("/simulation/reset", {
    method: "POST",
    body: JSON.stringify({ clear_incidents: true }),
  });
}

export async function fetchIncidents(): Promise<DetectedIncident[]> {
  const data = await requestJson<{ incidents: DetectedIncident[] }>("/incidents");
  return data.incidents;
}

export function investigateIncident(incidentId: string): Promise<InvestigationResult> {
  return requestJson<InvestigationResult>(`/incidents/${incidentId}/investigate`, {
    method: "POST",
  });
}

export async function fetchInvestigation(incidentId: string): Promise<InvestigationResult | null> {
  const response = await fetch(`${API_BASE}/incidents/${incidentId}/investigation`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch investigation (${response.status})`);
  }
  return (await response.json()) as InvestigationResult;
}

export function fetchIncidentTimeline(incidentId: string): Promise<IncidentTimelineResponse> {
  return requestJson<IncidentTimelineResponse>(`/incidents/${incidentId}/timeline`);
}

export async function fetchRemediationPlans(incidentId: string): Promise<RemediationPlan[]> {
  const data = await requestJson<{ plans: RemediationPlan[] }>(
    `/remediations?incident_id=${encodeURIComponent(incidentId)}`
  );
  return data.plans;
}

export function createRemediationPlan(incidentId: string): Promise<RemediationPlan> {
  return requestJson<RemediationPlan>(`/incidents/${incidentId}/remediations`, {
    method: "POST",
  });
}

export function approveRemediationPlan(
  planId: string,
  actor = "sre-operator",
  comment = ""
): Promise<RemediationPlan> {
  return requestJson<RemediationPlan>(`/remediations/${planId}/approve`, {
    method: "POST",
    body: JSON.stringify({ actor, comment }),
  });
}

export function rejectRemediationPlan(
  planId: string,
  actor = "sre-operator",
  comment = ""
): Promise<RemediationPlan> {
  return requestJson<RemediationPlan>(`/remediations/${planId}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor, comment }),
  });
}

export function executeRemediationPlan(planId: string): Promise<RemediationPlan> {
  return requestJson<RemediationPlan>(`/remediations/${planId}/execute`, {
    method: "POST",
  });
}

export function fetchRemediationVerification(planId: string): Promise<VerificationResult> {
  return requestJson<VerificationResult>(`/remediations/${planId}/verification`);
}

export function fetchTopology(): Promise<TopologyResponse> {
  return requestJson<TopologyResponse>("/topology");
}

export async function fetchAllRemediations(): Promise<RemediationPlan[]> {
  const data = await requestJson<{ plans: RemediationPlan[] }>("/remediations");
  return data.plans;
}

export interface AuditQueryParams {
  incidentId?: string | null;
  actorType?: string | null;
  category?: AuditCategory | null;
  order?: "asc" | "desc";
  limit?: number;
}

export function fetchAuditLogs(params: AuditQueryParams = {}): Promise<AuditLogListResponse> {
  const query = new URLSearchParams();
  if (params.incidentId) query.set("incident_id", params.incidentId);
  if (params.actorType) query.set("actor_type", params.actorType);
  if (params.category) query.set("category", params.category);
  if (params.order) query.set("order", params.order);
  if (params.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return requestJson<AuditLogListResponse>(`/audit${qs ? `?${qs}` : ""}`);
}
