import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownUp,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  ExternalLink,
  FileClock,
  FileSearch,
  Lock,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Wrench,
} from "lucide-react";
import { fetchAuditLogs, fetchIncidents } from "../api/client";
import { Panel } from "../components/common/Panel";
import type { AuditCategory, AuditLogEntry } from "../types/audit";
import type { DetectedIncident } from "../types/incidents";

interface AuditViewProps {
  onOpenIncident?: (incidentId: string) => void;
}

const CATEGORIES: Array<"ALL" | AuditCategory> = [
  "ALL",
  "INCIDENT",
  "INVESTIGATION",
  "POLICY",
  "RECOVERY",
  "VERIFICATION",
  "SIMULATION",
];

const ACTOR_TYPES = ["ALL", "SYSTEM", "AGENT", "POLICY", "HUMAN"] as const;

const LIFECYCLE_MILESTONES: Array<{
  id: string;
  label: string;
  actions: string[];
}> = [
  { id: "detected", label: "Detected", actions: ["INCIDENT_DETECTED"] },
  { id: "investigated", label: "Investigated", actions: ["INVESTIGATION_COMPLETED"] },
  { id: "planned", label: "Plan Proposed", actions: ["REMEDIATION_PLAN_CREATED"] },
  {
    id: "governed",
    label: "Policy / Approval",
    actions: ["POLICY_EVALUATED", "REMEDIATION_APPROVED", "REMEDIATION_REJECTED"],
  },
  {
    id: "executed",
    label: "Simulated Exec",
    actions: ["REMEDIATION_EXECUTION_COMPLETED", "REMEDIATION_EXECUTION_FAILED"],
  },
  {
    id: "verified",
    label: "Verified & Resolved",
    actions: ["VERIFICATION_COMPLETED", "INCIDENT_RESOLVED"],
  },
];

function categoryStyle(category: AuditCategory): {
  badge: string;
  dot: string;
  Icon: typeof Siren;
} {
  switch (category) {
    case "INCIDENT":
      return {
        badge: "border-nexus-crimson/50 bg-nexus-crimson/15 text-rose-200",
        dot: "border-nexus-crimson bg-nexus-crimson/20 text-rose-200",
        Icon: Siren,
      };
    case "INVESTIGATION":
      return {
        badge: "border-nexus-cyan/40 bg-nexus-cyan/15 text-cyan-200",
        dot: "border-nexus-cyan bg-nexus-cyan/20 text-cyan-200",
        Icon: FileSearch,
      };
    case "POLICY":
      return {
        badge: "border-nexus-amber/50 bg-nexus-amber/15 text-amber-200",
        dot: "border-nexus-amber bg-nexus-amber/20 text-amber-200",
        Icon: ShieldAlert,
      };
    case "RECOVERY":
      return {
        badge: "border-nexus-teal/50 bg-nexus-teal/15 text-teal-200",
        dot: "border-nexus-teal bg-nexus-teal/20 text-teal-200",
        Icon: Wrench,
      };
    case "VERIFICATION":
      return {
        badge: "border-nexus-emerald/50 bg-nexus-emerald/15 text-emerald-200",
        dot: "border-nexus-emerald bg-nexus-emerald/20 text-emerald-200",
        Icon: ShieldCheck,
      };
    default:
      return {
        badge: "border-obsidian-700 bg-obsidian-850 text-slate-300",
        dot: "border-obsidian-700 bg-obsidian-850 text-slate-300",
        Icon: Activity,
      };
  }
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
}

function describeAuditEntry(entry: AuditLogEntry): string {
  const d = entry.details;
  switch (entry.action) {
    case "INCIDENT_DETECTED":
      return `Detected ${String(d.severity ?? "")} incident; candidate root cause: ${String(
        d.root_cause_candidate ?? "unidentified"
      )}.`;
    case "INVESTIGATION_STARTED":
      return "Started evidence-grounded investigation pipeline (Observer → Investigator → Risk Analyst).";
    case "INVESTIGATION_COMPLETED":
      return `Completed ${String(d.inference_mode ?? "DETERMINISTIC")} investigation; root cause: ${String(
        d.probable_root_cause_service ?? "unidentified"
      )} (confidence ${typeof d.confidence_score === "number" ? d.confidence_score.toFixed(2) : "—"}).`;
    case "INVESTIGATION_FAILED":
      return `Investigation failed: ${String(d.error ?? "unknown error")}.`;
    case "INCIDENT_UPDATED":
      return `Incident record updated (investigation status: ${String(d.investigation_status ?? "updated")}).`;
    case "REMEDIATION_PLAN_CREATED":
      return `Proposed allowlisted action '${String(d.action_id ?? "")}' targeting '${String(
        d.target_service ?? ""
      )}' (${String(d.plan_id ?? "")}).`;
    case "POLICY_EVALUATED":
      return `Trust Agent policy decision: ${String(d.policy_decision ?? "")} (approval: ${String(
        d.approval_status ?? ""
      )}).`;
    case "REMEDIATION_APPROVED":
      return `Human approval recorded by ${entry.actor_name} for ${String(d.plan_id ?? "")}${
        d.comment ? ` — "${String(d.comment)}"` : ""
      }.`;
    case "REMEDIATION_REJECTED":
      return `Human rejection recorded by ${entry.actor_name} for ${String(d.plan_id ?? "")}${
        d.comment ? ` — "${String(d.comment)}"` : ""
      }.`;
    case "REMEDIATION_EXECUTION_STARTED":
      return `Started simulated execution of '${String(d.action_id ?? "")}' on '${String(
        d.target_service ?? ""
      )}'.`;
    case "REMEDIATION_EXECUTION_COMPLETED":
      return String(
        d.modeled_effect_summary ??
          `Completed simulated execution (${String(d.execution_id ?? "")}).`
      );
    case "REMEDIATION_EXECUTION_FAILED":
      return `Simulated execution blocked or failed: ${String(d.error ?? "")}.`;
    case "VERIFICATION_STARTED":
      return `Started post-remediation SLO verification for ${String(d.plan_id ?? "")} (applied tick ${String(
        d.applied_tick ?? "—"
      )}).`;
    case "VERIFICATION_COMPLETED":
      return `Recovery verified across ${String(
        d.consecutive_healthy_ticks ?? "—"
      )} consecutive healthy ticks (resilience score ${String(d.resilience_score ?? "—")}).`;
    case "VERIFICATION_FAILED":
      return String(d.summary ?? "Post-remediation verification failed.");
    case "INCIDENT_RESOLVED":
      return `Incident transitioned to RESOLVED after verified recovery (${String(
        d.plan_id ?? ""
      )}).`;
    case "SCENARIO_INJECTED":
      return `Injected local fault scenario '${String(d.scenario_id ?? "")}' at tick ${String(
        d.tick ?? 0
      )}.`;
    case "SIMULATION_STARTED":
      return `Started deterministic simulation loop (${String(d.interval_s ?? 2)}s interval).`;
    case "SIMULATION_STOPPED":
      return `Stopped simulation loop at tick ${String(d.tick ?? 0)}.`;
    case "SIMULATION_RESET":
      return `Reset simulation to healthy baseline (clear_incidents=${String(
        d.clear_incidents ?? true
      )}).`;
    default:
      return `${entry.action} recorded by ${entry.actor_name}.`;
  }
}

export function AuditView({ onOpenIncident }: AuditViewProps) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [incidents, setIncidents] = useState<DetectedIncident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>("ALL");
  const [selectedCategory, setSelectedCategory] = useState<"ALL" | AuditCategory>("ALL");
  const [selectedActor, setSelectedActor] = useState<(typeof ACTOR_TYPES)[number]>("ALL");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [auditRes, incidentList] = await Promise.all([
        fetchAuditLogs({
          incidentId: selectedIncidentId === "ALL" ? null : selectedIncidentId,
          category: selectedCategory === "ALL" ? null : selectedCategory,
          actorType: selectedActor === "ALL" ? null : selectedActor,
          order,
          limit: 300,
        }),
        fetchIncidents().catch(() => [] as DetectedIncident[]),
      ]);
      setEntries(auditRes.entries);
      setIncidents(incidentList);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load persisted audit records");
    } finally {
      setIsLoading(false);
    }
  }, [selectedIncidentId, selectedCategory, selectedActor, order]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Combine known persisted incident IDs from /incidents and audit entries
  const incidentOptions = useMemo(() => {
    const ids = new Set<string>();
    for (const inc of incidents) ids.add(inc.id);
    for (const e of entries) {
      if (e.incident_id) ids.add(e.incident_id);
    }
    return Array.from(ids).sort();
  }, [incidents, entries]);

  // Honest recorded action set for the lifecycle rail (strictly from persisted SQLite entries)
  const recordedActions = useMemo(() => {
    return new Set(entries.map((e) => e.action));
  }, [entries]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6">
      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-nexus-crimson/40 bg-nexus-crimson/10 px-4 py-3 text-xs text-rose-200"
        >
          {error}
        </div>
      ) : null}

      <Panel
        title="Incident Timeline & Immutable Audit Ledger"
        subtitle="Chronological append-only SQLite records — strictly reflects persisted backend events with zero fabricated data"
        rightSlot={
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-nexus-teal/30 bg-nexus-teal/10 px-2.5 py-1 font-mono text-[11px] text-nexus-teal">
              <Lock className="h-3 w-3" aria-hidden="true" />
              APPEND-ONLY · {entries.length} RECORD{entries.length === 1 ? "" : "S"}
            </span>
            <button
              type="button"
              onClick={() => setOrder((prev) => (prev === "asc" ? "desc" : "asc"))}
              className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-2.5 py-1 text-xs text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan"
              aria-label="Toggle chronological sort order"
            >
              <ArrowDownUp className="h-3.5 w-3.5" aria-hidden="true" />
              {order === "asc" ? "Oldest → Newest" : "Newest → Oldest"}
            </button>
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-2.5 py-1 text-xs text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan disabled:opacity-50"
              aria-label="Refresh audit timeline"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`}
                aria-hidden="true"
              />
              Refresh
            </button>
          </div>
        }
      >
        {/* Honest Lifecycle Coverage Rail (only lights up milestones with real persisted events) */}
        <div className="mb-5 rounded-lg border border-obsidian-700/70 bg-obsidian-950/80 p-3.5">
          <div className="mb-2 flex items-center justify-between text-[11px]">
            <span className="font-mono uppercase tracking-wider text-slate-400">
              Recorded Lifecycle Milestones{" "}
              {selectedIncidentId !== "ALL" ? `(${selectedIncidentId})` : "(Current View)"}
            </span>
            <span className="font-mono text-[10px] text-slate-500">
              Derived strictly from persisted SQLite events
            </span>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {LIFECYCLE_MILESTONES.map((stage) => {
              const recorded = stage.actions.some((a) => recordedActions.has(a));
              return (
                <div
                  key={stage.id}
                  className={`flex items-center gap-2 rounded-md border px-2.5 py-2 font-mono text-[11px] ${
                    recorded
                      ? "border-nexus-emerald/40 bg-nexus-emerald/10 text-emerald-200"
                      : "border-obsidian-700/70 bg-obsidian-900/70 text-slate-500"
                  }`}
                >
                  {recorded ? (
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-nexus-emerald" aria-hidden="true" />
                  ) : (
                    <Clock className="h-3.5 w-3.5 shrink-0 text-slate-600" aria-hidden="true" />
                  )}
                  <div className="min-w-0">
                    <div className="truncate font-semibold">{stage.label}</div>
                    <div className="text-[9px] uppercase">
                      {recorded ? "Recorded" : "Not recorded"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Filter Controls */}
        <div className="mb-5 space-y-3 rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-4">
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="audit-incident-filter" className="font-mono text-[11px] uppercase text-slate-400">
              Incident:
            </label>
            <select
              id="audit-incident-filter"
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
              className="rounded-lg border border-obsidian-700 bg-obsidian-900 px-3 py-1.5 font-mono text-xs text-slate-100 focus:border-nexus-cyan focus:outline-none"
            >
              <option value="ALL">All Incidents &amp; System Events</option>
              {incidentOptions.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>

            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[11px] uppercase text-slate-500">Actor:</span>
              {ACTOR_TYPES.map((actor) => (
                <button
                  key={actor}
                  type="button"
                  onClick={() => setSelectedActor(actor)}
                  className={`rounded-md border px-2 py-1 font-mono text-[10px] transition ${
                    selectedActor === actor
                      ? "border-nexus-cyan/50 bg-nexus-cyan/15 text-nexus-cyan"
                      : "border-obsidian-700 bg-obsidian-900 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {actor}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[11px] uppercase text-slate-500">Category:</span>
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`rounded-md border px-2.5 py-1 font-mono text-[10px] transition ${
                  selectedCategory === cat
                    ? "border-nexus-teal/50 bg-nexus-teal/15 text-teal-200"
                    : "border-obsidian-700 bg-obsidian-900 text-slate-400 hover:text-slate-200"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Chronological Timeline */}
        {isLoading && entries.length === 0 ? (
          <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-8 text-center text-xs text-slate-400">
            Loading persisted audit records...
          </div>
        ) : entries.length === 0 ? (
          <div className="rounded-lg border border-dashed border-obsidian-700 bg-obsidian-950/75 p-8 text-center">
            <FileClock className="mx-auto h-6 w-6 text-slate-500" aria-hidden="true" />
            <p className="mt-2 text-sm font-medium text-slate-200">
              No persisted audit records match the current filters.
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Inject a scenario, run an investigation, or execute a policy-gated remediation to
              observe real SQLite audit events here.
            </p>
          </div>
        ) : (
          <ol className="relative space-y-3 border-l border-obsidian-700/80 pl-6">
            {entries.map((entry) => {
              const style = categoryStyle(entry.category);
              const Icon = style.Icon;
              const isExpanded = Boolean(expandedIds[entry.id]);
              const d = entry.details;

              return (
                <li key={entry.id} className="relative">
                  <span
                    className={`absolute -left-[35px] top-3 flex h-6 w-6 items-center justify-center rounded-full border ${style.dot}`}
                    aria-hidden="true"
                  >
                    <Icon className="h-3 w-3" />
                  </span>

                  <div className="rounded-xl border border-obsidian-700/80 bg-obsidian-950/85 p-4 transition hover:border-obsidian-700">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded border px-2 py-0.5 font-mono text-[10px] font-semibold ${style.badge}`}
                        >
                          {entry.category}
                        </span>
                        <span className="font-mono text-xs font-semibold text-slate-100">
                          {entry.action}
                        </span>
                        <span className="rounded bg-obsidian-850 px-2 py-0.5 font-mono text-[10px] text-slate-300">
                          {entry.actor_type}:{entry.actor_name}
                        </span>
                        {entry.incident_id ? (
                          <button
                            type="button"
                            onClick={() => onOpenIncident?.(entry.incident_id!)}
                            className="inline-flex items-center gap-1 rounded border border-nexus-cyan/40 bg-nexus-cyan/10 px-2 py-0.5 font-mono text-[10px] text-nexus-cyan transition hover:bg-nexus-cyan/20"
                            title={`Open ${entry.incident_id} in Incidents`}
                          >
                            {entry.incident_id}
                            <ExternalLink className="h-2.5 w-2.5" aria-hidden="true" />
                          </button>
                        ) : null}
                      </div>

                      <time
                        dateTime={entry.timestamp}
                        title={entry.timestamp}
                        className="font-mono text-[10px] text-slate-400"
                      >
                        {formatTimestamp(entry.timestamp)}
                      </time>
                    </div>

                    <p className="mt-2 text-xs leading-relaxed text-slate-300">
                      {describeAuditEntry(entry)}
                    </p>

                    {/* Key Persisted Metadata Chips */}
                    <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap gap-1.5 font-mono text-[10px]">
                        {d.plan_id ? (
                          <span className="rounded border border-obsidian-700 bg-obsidian-900 px-2 py-0.5 text-slate-300">
                            plan: {String(d.plan_id)}
                          </span>
                        ) : null}
                        {d.action_id ? (
                          <span className="rounded border border-obsidian-700 bg-obsidian-900 px-2 py-0.5 text-nexus-teal">
                            action: {String(d.action_id)}
                          </span>
                        ) : null}
                        {d.policy_decision ? (
                          <span className="rounded border border-nexus-amber/40 bg-nexus-amber/10 px-2 py-0.5 text-amber-200">
                            policy: {String(d.policy_decision)}
                          </span>
                        ) : null}
                        {d.verification_status ? (
                          <span className="rounded border border-nexus-emerald/40 bg-nexus-emerald/10 px-2 py-0.5 text-emerald-200">
                            verification: {String(d.verification_status)}
                          </span>
                        ) : null}
                        {typeof d.tick === "number" ? (
                          <span className="rounded border border-obsidian-700 bg-obsidian-900 px-2 py-0.5 text-slate-400">
                            tick {d.tick}
                          </span>
                        ) : null}
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleExpand(entry.id)}
                        aria-expanded={isExpanded}
                        className="inline-flex items-center gap-1 font-mono text-[10px] text-slate-400 transition hover:text-nexus-cyan"
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-3 w-3" aria-hidden="true" />
                        ) : (
                          <ChevronRight className="h-3 w-3" aria-hidden="true" />
                        )}
                        {isExpanded ? "Hide details" : "Inspect payload"}
                      </button>
                    </div>

                    {isExpanded ? (
                      <div className="mt-3 rounded-lg border border-obsidian-700/70 bg-obsidian-900/90 p-3">
                        <div className="mb-1.5 font-mono text-[10px] text-slate-500">
                          Audit Record ID: {entry.id}
                        </div>
                        <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed text-slate-300">
                          {JSON.stringify(entry.details, null, 2)}
                        </pre>
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </Panel>
    </div>
  );
}
