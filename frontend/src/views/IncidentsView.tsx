import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  Bot,
  CheckCircle2,
  Clock,
  FileSearch,
  Info,
  ListChecks,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  fetchIncidents,
  fetchIncidentTimeline,
  fetchInvestigation,
  investigateIncident,
} from "../api/client";
import { Panel } from "../components/common/Panel";
import type {
  DetectedIncident,
  InvestigationResult,
  ServiceCausalRole,
  SeverityLevel,
  TimelineEntry,
} from "../types/incidents";

function severityBadgeClass(severity: SeverityLevel): string {
  switch (severity) {
    case "CRITICAL":
      return "border-nexus-crimson/40 bg-nexus-crimson/15 text-rose-200";
    case "HIGH":
      return "border-nexus-amber/40 bg-nexus-amber/15 text-amber-200";
    case "MEDIUM":
      return "border-nexus-cyan/40 bg-nexus-cyan/15 text-cyan-200";
    default:
      return "border-obsidian-700 bg-obsidian-850 text-slate-300";
  }
}

function roleBadge(role: ServiceCausalRole): { label: string; cls: string } {
  switch (role) {
    case "probable_root_cause":
      return {
        label: "PROBABLE ROOT CAUSE",
        cls: "border-nexus-crimson/50 bg-nexus-crimson/15 text-rose-200",
      };
    case "contributing_cause":
      return {
        label: "CONTRIBUTING CAUSE",
        cls: "border-nexus-amber/50 bg-nexus-amber/15 text-amber-200",
      };
    case "downstream_symptom":
      return {
        label: "DOWNSTREAM SYMPTOM",
        cls: "border-nexus-cyan/40 bg-nexus-cyan/10 text-cyan-200",
      };
    default:
      return {
        label: "UNAFFECTED",
        cls: "border-nexus-emerald/40 bg-nexus-emerald/10 text-emerald-200",
      };
  }
}

export function IncidentsView() {
  const [incidents, setIncidents] = useState<DetectedIncident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadIncidents = useCallback(async () => {
    setIsLoading(true);
    try {
      const list = await fetchIncidents();
      setIncidents(list);
      setSelectedId((prev) => {
        if (prev && list.some((i) => i.id === prev)) return prev;
        return list.length > 0 ? list[0].id : null;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incidents");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadIncidentDetails = useCallback(async (incidentId: string) => {
    try {
      const [inv, tl] = await Promise.all([
        fetchInvestigation(incidentId),
        fetchIncidentTimeline(incidentId),
      ]);
      setInvestigation(inv);
      setTimeline(tl.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incident details");
    }
  }, []);

  useEffect(() => {
    void loadIncidents();
  }, [loadIncidents]);

  useEffect(() => {
    if (!selectedId) {
      setInvestigation(null);
      setTimeline([]);
      return;
    }
    void loadIncidentDetails(selectedId);
  }, [selectedId, loadIncidentDetails]);

  const handleInvestigate = async (incidentId: string) => {
    setIsInvestigating(true);
    setError(null);
    try {
      const result = await investigateIncident(incidentId);
      setInvestigation(result);
      await Promise.all([loadIncidents(), loadIncidentDetails(incidentId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Investigation failed");
    } finally {
      setIsInvestigating(false);
    }
  };

  const selectedIncident = incidents.find((i) => i.id === selectedId) ?? null;

  return (
    <div className="space-y-6">
      {error ? (
        <div className="rounded-lg border border-nexus-crimson/40 bg-nexus-crimson/10 px-4 py-3 text-xs text-rose-200">
          {error}
        </div>
      ) : null}

      <Panel
        title="Detected Incidents"
        subtitle="Persisted incidents synchronized with the deterministic simulator"
        rightSlot={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-obsidian-700 bg-obsidian-950 px-2.5 py-1 font-mono text-[11px] text-slate-300">
              <ShieldAlert className="h-3.5 w-3.5 text-nexus-teal" />
              {incidents.length} INCIDENT{incidents.length === 1 ? "" : "S"}
            </span>
            <button
              type="button"
              onClick={() => void loadIncidents()}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-2.5 py-1 text-xs text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        }
      >
        {incidents.length === 0 ? (
          <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-6 text-center">
            <p className="text-sm font-medium text-slate-200">No incidents detected yet.</p>
            <p className="mt-1 text-xs text-slate-400">
              Use the Overview tab to inject <span className="font-mono text-nexus-cyan">db_latency_cascade</span> and
              advance ticks to trigger correlated incident detection.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {incidents.map((inc) => {
              const isSelected = inc.id === selectedId;
              return (
                <button
                  key={inc.id}
                  type="button"
                  onClick={() => setSelectedId(inc.id)}
                  className={`flex w-full flex-wrap items-center justify-between gap-3 rounded-lg border p-4 text-left transition ${
                    isSelected
                      ? "border-nexus-cyan/50 bg-nexus-cyan/10 shadow-cyan-subtle"
                      : "border-obsidian-700/70 bg-obsidian-950/75 hover:border-obsidian-700 hover:bg-obsidian-850"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-nexus-cyan">
                        {inc.id}
                      </span>
                      <span
                        className={`rounded border px-2 py-0.5 font-mono text-[10px] font-semibold ${severityBadgeClass(
                          inc.severity
                        )}`}
                      >
                        {inc.severity}
                      </span>
                      <span className="rounded border border-obsidian-700 bg-obsidian-900 px-2 py-0.5 font-mono text-[10px] text-slate-300">
                        {inc.status}
                      </span>
                      <span className="rounded border border-nexus-teal/30 bg-nexus-teal/10 px-2 py-0.5 font-mono text-[10px] text-nexus-teal">
                        INVESTIGATION: {inc.investigation_status}
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm font-medium text-slate-100">{inc.title}</p>
                    <p className="mt-1 font-mono text-[11px] text-slate-400">
                      Detected tick {inc.detected_tick} (t={inc.detected_sim_time_s.toFixed(1)}s) ·{" "}
                      {inc.affected_services.length} affected services · Candidate:{" "}
                      {inc.root_cause_candidate ?? "unknown"}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </Panel>

      {selectedIncident ? (
        <div className="space-y-6">
          <Panel
            title={`${selectedIncident.id} — Incident Intelligence Dossier`}
            subtitle={`Detected at tick ${selectedIncident.detected_tick} (t=${selectedIncident.detected_sim_time_s.toFixed(
              1
            )}s) · Status: ${selectedIncident.status}`}
            rightSlot={
              <button
                type="button"
                disabled={isInvestigating}
                onClick={() => void handleInvestigate(selectedIncident.id)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-cyan/50 bg-nexus-cyan/15 px-3.5 py-2 text-xs font-medium text-cyan-100 transition hover:bg-nexus-cyan/25 disabled:opacity-50"
              >
                <Sparkles className={`h-3.5 w-3.5 ${isInvestigating ? "animate-pulse" : ""}`} />
                {isInvestigating
                  ? "Investigating..."
                  : investigation
                    ? "Re-run Investigation"
                    : "Run Investigation"}
              </button>
            }
          >
            {!investigation ? (
              <div className="rounded-lg border border-dashed border-obsidian-700 bg-obsidian-950/75 p-6 text-center">
                <FileSearch className="mx-auto h-6 w-6 text-nexus-cyan" />
                <p className="mt-2 text-sm font-medium text-slate-200">
                  Evidence ready for investigation.
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Click <span className="font-semibold text-nexus-cyan">Run Investigation</span> to
                  execute the Observer → Investigator → Risk Analyst pipeline and generate
                  evidence-grounded root-cause findings.
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Summary + Root Cause Hypothesis */}
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="space-y-3 rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4 lg:col-span-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-[11px] uppercase tracking-wider text-nexus-cyan">
                        Root-Cause Hypothesis
                      </span>
                      <span className="rounded border border-obsidian-700 bg-obsidian-900 px-2 py-0.5 font-mono text-[10px] text-slate-300">
                        MODE: {investigation.inference_mode} ({investigation.model_name})
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-relaxed text-slate-100">
                      {investigation.root_cause_hypothesis}
                    </p>
                    <p className="text-xs leading-relaxed text-slate-400">{investigation.summary}</p>
                  </div>

                  {/* Confidence Assessment */}
                  <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
                        Confidence
                      </span>
                      <span className="font-mono text-sm font-semibold text-nexus-cyan">
                        {Math.round(investigation.confidence.score * 100)}% (
                        {investigation.confidence.level})
                      </span>
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-obsidian-800">
                      <div
                        className="h-full rounded-full bg-nexus-cyan"
                        style={{ width: `${Math.round(investigation.confidence.score * 100)}%` }}
                      />
                    </div>
                    <ul className="mt-3 space-y-2">
                      {investigation.confidence.criteria.map((c) => (
                        <li key={c.name} className="text-[11px]">
                          <div className="flex justify-between font-mono text-slate-300">
                            <span>{c.name}</span>
                            <span>
                              {Math.round(c.score * 100)}% (w={c.weight})
                            </span>
                          </div>
                          <p className="text-slate-500">{c.explanation}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Blast Radius & Causal Service Roles */}
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
                        Blast Radius &amp; Risk
                      </span>
                      <span
                        className={`rounded border px-2 py-0.5 font-mono text-[10px] font-semibold ${severityBadgeClass(
                          investigation.blast_radius.risk_level
                        )}`}
                      >
                        {investigation.blast_radius.risk_score}/100{" "}
                        {investigation.blast_radius.risk_level}
                      </span>
                    </div>
                    <p className="mt-2.5 text-xs leading-relaxed text-slate-300">
                      {investigation.blast_radius.business_impact_summary}
                    </p>
                    <div className="mt-3 space-y-1.5">
                      {Object.entries(investigation.blast_radius.factors).map(([k, v]) => (
                        <div key={k} className="flex items-center justify-between font-mono text-[11px]">
                          <span className="text-slate-400">{k}</span>
                          <span className="text-slate-200">{v.toFixed(1)} pts</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4 lg:col-span-2">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
                      Service Causal Classification (Root vs Contributing vs Symptom)
                    </span>
                    <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
                      {investigation.service_roles.map((sr) => {
                        const badge = roleBadge(sr.role);
                        return (
                          <div
                            key={sr.service_id}
                            className="rounded-lg border border-obsidian-700/70 bg-obsidian-900/80 p-3"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-xs font-semibold text-slate-100">
                                {sr.service_id}
                              </span>
                              <span
                                className={`rounded border px-1.5 py-0.5 font-mono text-[9px] font-semibold ${badge.cls}`}
                              >
                                {badge.label}
                              </span>
                            </div>
                            <p className="mt-1.5 text-[11px] leading-relaxed text-slate-400">
                              {sr.rationale}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Contributing Factors, Recommended Next Steps & Limiting Evidence */}
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
                    <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-amber-300">
                      <AlertOctagon className="h-3.5 w-3.5" />
                      Contributing Factors
                    </div>
                    <ul className="mt-2.5 space-y-2 text-xs text-slate-300">
                      {investigation.contributing_factors.map((f, idx) => (
                        <li key={idx} className="leading-relaxed">
                          • {f}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
                    <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-nexus-emerald">
                      <ListChecks className="h-3.5 w-3.5" />
                      Recommended Next Steps
                    </div>
                    <ul className="mt-2.5 space-y-2 text-xs text-slate-300">
                      {investigation.recommended_next_steps.map((s, idx) => (
                        <li key={idx} className="leading-relaxed">
                          {idx + 1}. {s}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
                    <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-slate-400">
                      <Info className="h-3.5 w-3.5" />
                      Limiting Evidence &amp; Scope
                    </div>
                    <ul className="mt-2.5 space-y-2 text-xs text-slate-400">
                      {investigation.limiting_evidence.map((l, idx) => (
                        <li key={idx} className="leading-relaxed">
                          • {l}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Logical Agent Trace */}
                <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
                  <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-nexus-cyan">
                    <Bot className="h-3.5 w-3.5" />
                    Logical Investigation Pipeline
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                    {investigation.agent_trace.map((step) => (
                      <div
                        key={step.agent_role}
                        className="rounded-lg border border-obsidian-700/70 bg-obsidian-900/80 p-3"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-semibold text-slate-100">
                            {step.agent_role}
                          </span>
                          <span className="inline-flex items-center gap-1 font-mono text-[10px] text-nexus-emerald">
                            <CheckCircle2 className="h-3 w-3" />
                            {step.duration_ms}ms
                          </span>
                        </div>
                        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-400">
                          {step.summary}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Traceable Supporting Evidence */}
                <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
                      Traceable Supporting Evidence ({investigation.supporting_evidence.length} items)
                    </span>
                    <Activity className="h-3.5 w-3.5 text-nexus-teal" />
                  </div>
                  <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
                    {investigation.supporting_evidence.map((ev) => (
                      <div
                        key={ev.evidence_id}
                        className="flex flex-wrap items-start gap-2 rounded border border-obsidian-700/60 bg-obsidian-900/70 px-3 py-2 text-xs"
                      >
                        <span className="shrink-0 font-mono text-[10px] font-semibold text-nexus-cyan">
                          {ev.evidence_id}
                        </span>
                        <span className="shrink-0 rounded bg-obsidian-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                          {ev.source_type}
                        </span>
                        <span className="min-w-0 flex-1 text-slate-300">{ev.observation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </Panel>

          {/* Incident Timeline */}
          <Panel
            title="Incident Timeline"
            subtitle="Chronological monitoring events and persisted SQLite audit trail entries"
            rightSlot={<Clock className="h-4 w-4 text-nexus-cyan" />}
          >
            {timeline.length === 0 ? (
              <p className="text-xs text-slate-400">No timeline entries recorded yet.</p>
            ) : (
              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {timeline.map((entry, idx) => (
                  <div
                    key={`${entry.source}-${entry.event_type}-${idx}`}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-obsidian-700/60 bg-obsidian-950/75 px-3.5 py-2.5 text-xs"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
                          entry.source === "AUDIT_LOG"
                            ? "border-nexus-teal/40 bg-nexus-teal/10 text-nexus-teal"
                            : "border-nexus-amber/40 bg-nexus-amber/10 text-amber-200"
                        }`}
                      >
                        {entry.source}
                      </span>
                      <span className="font-mono text-[11px] font-semibold text-slate-200">
                        {entry.event_type}
                      </span>
                      <span className="text-slate-300">{entry.summary}</span>
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">
                      {entry.tick !== null ? `tick ${entry.tick} · ` : ""}
                      {entry.actor}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      ) : null}
    </div>
  );
}
