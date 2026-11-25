export type AuditCategory =
  | "INCIDENT"
  | "INVESTIGATION"
  | "POLICY"
  | "RECOVERY"
  | "VERIFICATION"
  | "SIMULATION";

export type AuditActorType = "SYSTEM" | "AGENT" | "POLICY" | "HUMAN";

export interface AuditLogEntry {
  id: string;
  incident_id: string | null;
  actor_type: string;
  actor_name: string;
  action: string;
  category: AuditCategory;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface AuditLogListResponse {
  total: number;
  entries: AuditLogEntry[];
}
