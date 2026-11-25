import { useCallback, useEffect, useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  FastForward,
  Flame,
  LayoutGrid,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Square,
} from "lucide-react";
import { fetchAllRemediations, fetchTopology } from "../api/client";
import { Panel } from "../components/common/Panel";
import { DependencyGraph } from "../components/graph/DependencyGraph";
import type { SimulationStatusResponse } from "../types/health";
import type { RemediationPlan } from "../types/remediation";
import type { ServiceNodeState, TopologyResponse } from "../types/topology";

interface TopologyViewProps {
  simStatus: SimulationStatusResponse | null;
  isSimBusy: boolean;
  onStartSim: () => void;
  onStopSim: () => void;
  onAdvanceTick: () => void;
  onInjectDbCascade: () => void;
  onResetSim: () => void;
}

function statusPillClasses(status: ServiceNodeState["status"]): string {
  if (status === "critical") {
    return "border-nexus-crimson/50 bg-nexus-crimson/15 text-rose-200";
  }
  if (status === "degraded") {
    return "border-nexus-amber/50 bg-nexus-amber/15 text-amber-200";
  }
  return "border-nexus-emerald/40 bg-nexus-emerald/10 text-emerald-200";
}

export function TopologyView({
  simStatus,
  isSimBusy,
  onStartSim,
  onStopSim,
  onAdvanceTick,
  onInjectDbCascade,
  onResetSim,
}: TopologyViewProps) {
  const [topology, setTopology] = useState<TopologyResponse | null>(null);
  const [latestPlan, setLatestPlan] = useState<RemediationPlan | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTopology = useCallback(async () => {
    setIsLoading(true);
    try {
      const [topoData, plans] = await Promise.all([
        fetchTopology(),
        fetchAllRemediations().catch(() => [] as RemediationPlan[]),
      ]);
      setTopology(topoData);
      setLatestPlan(plans[0] ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load infrastructure topology");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Re-fetch whenever authoritative simulation status from App.tsx changes
  useEffect(() => {
    void loadTopology();
  }, [loadTopology, simStatus?.tick, simStatus?.active_scenario, simStatus?.active_incidents_count]);

  const nodes = topology?.nodes ?? [];
  const edges = topology?.edges ?? [];
  const rootNode = nodes.find((n) => n.is_root_cause_candidate) ?? null;
  const impactedCount = nodes.filter((n) => n.in_blast_radius).length;
  const healthyCount = nodes.filter((n) => n.status === "healthy").length;
  const degradedCount = nodes.filter((n) => n.status === "degraded").length;
  const criticalCount = nodes.filter((n) => n.status === "critical").length;
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

  const selectedUpstream = selectedNode
    ? edges.filter((e) => e.source === selectedNode.id)
    : [];
  const selectedDownstream = selectedNode
    ? edges.filter((e) => e.target === selectedNode.id)
    : [];

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

      {/* Compact Simulation Controls + Live Health & Recovery Awareness Strip */}
      <Panel
        title="Live Topology Telemetry & Controls"
        subtitle="Real-time view of backend /api/v1/topology — updates on fault injection, ticks, recovery, and reset"
        rightSlot={
          <div className="flex flex-wrap items-center gap-2">
            {rootNode ? (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-nexus-crimson/50 bg-nexus-crimson/15 px-2.5 py-1 font-mono text-[11px] font-semibold text-rose-200">
                <AlertOctagon className="h-3.5 w-3.5" aria-hidden="true" />
                ROOT CAUSE: {rootNode.id}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-nexus-emerald/40 bg-nexus-emerald/10 px-2.5 py-1 font-mono text-[11px] text-emerald-200">
                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                NO ACTIVE ROOT FAULT
              </span>
            )}
            {latestPlan ? (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-nexus-cyan/40 bg-nexus-cyan/10 px-2.5 py-1 font-mono text-[11px] text-cyan-200">
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                RECOVERY: {latestPlan.verification_status}
              </span>
            ) : null}
          </div>
        }
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            {!simStatus?.running ? (
              <button
                type="button"
                disabled={isSimBusy}
                onClick={onStartSim}
                className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-emerald/40 bg-nexus-emerald/15 px-3 py-1.5 text-xs font-medium text-emerald-200 transition hover:bg-nexus-emerald/25 disabled:opacity-50"
              >
                <Play className="h-3.5 w-3.5" aria-hidden="true" />
                Start
              </button>
            ) : (
              <button
                type="button"
                disabled={isSimBusy}
                onClick={onStopSim}
                className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-amber/40 bg-nexus-amber/15 px-3 py-1.5 text-xs font-medium text-amber-200 transition hover:bg-nexus-amber/25 disabled:opacity-50"
              >
                <Square className="h-3.5 w-3.5" aria-hidden="true" />
                Stop
              </button>
            )}
            <button
              type="button"
              disabled={isSimBusy}
              onClick={onAdvanceTick}
              className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan disabled:opacity-50"
            >
              <FastForward className="h-3.5 w-3.5" aria-hidden="true" />
              +1 Tick
            </button>
            <button
              type="button"
              disabled={isSimBusy}
              onClick={onInjectDbCascade}
              className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-crimson/40 bg-nexus-crimson/15 px-3 py-1.5 text-xs font-medium text-rose-200 transition hover:bg-nexus-crimson/25 disabled:opacity-50"
            >
              <Flame className="h-3.5 w-3.5" aria-hidden="true" />
              Inject db_latency_cascade
            </button>
            <button
              type="button"
              disabled={isSimBusy}
              onClick={onResetSim}
              className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-950 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-slate-500 hover:text-slate-100 disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Reset
            </button>
            <button
              type="button"
              disabled={isLoading}
              onClick={() => void loadTopology()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-3 py-1.5 text-xs text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan disabled:opacity-50"
              aria-label="Refresh topology"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} aria-hidden="true" />
              Sync
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3 font-mono text-[11px] text-slate-300">
            <span>Tick {topology?.tick ?? 0} ({(topology?.sim_time_s ?? 0).toFixed(0)}s)</span>
            <span className="text-nexus-emerald">{healthyCount} Healthy</span>
            <span className="text-nexus-amber">{degradedCount} Degraded</span>
            <span className="text-nexus-crimson">{criticalCount} Critical</span>
            <span className="text-nexus-cyan">{impactedCount} Impacted</span>
          </div>
        </div>
      </Panel>

      {/* Main Interactive Topology Panel */}
      <Panel
        title="Interactive Service Dependency Graph"
        subtitle="Arrows indicate caller → dependency direction. Click any node to inspect live metrics and dependencies."
        rightSlot={
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-md border border-obsidian-700 bg-obsidian-950 px-2.5 py-1 font-mono text-[11px] text-slate-300 sm:inline-flex">
              <Network className="h-3.5 w-3.5 text-nexus-cyan" aria-hidden="true" />
              {nodes.length} NODES · {edges.length} EDGES
            </span>
            <div className="inline-flex rounded-lg border border-obsidian-700 bg-obsidian-950 p-0.5 text-[11px]">
              <button
                type="button"
                onClick={() => setViewMode("graph")}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 font-mono transition ${
                  viewMode === "graph"
                    ? "bg-nexus-cyan/15 text-nexus-cyan"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Network className="h-3 w-3" aria-hidden="true" />
                Graph
              </button>
              <button
                type="button"
                onClick={() => setViewMode("list")}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 font-mono transition ${
                  viewMode === "list"
                    ? "bg-nexus-cyan/15 text-nexus-cyan"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <LayoutGrid className="h-3 w-3" aria-hidden="true" />
                List
              </button>
            </div>
          </div>
        }
      >
        {/* Accessible Legend */}
        <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-obsidian-700/70 bg-obsidian-950/80 px-3.5 py-2 text-[11px] text-slate-300">
          <span className="inline-flex items-center gap-1.5 font-mono">
            <AlertOctagon className="h-3.5 w-3.5 text-nexus-crimson" aria-hidden="true" />
            Root Cause / Critical
          </span>
          <span className="inline-flex items-center gap-1.5 font-mono">
            <AlertTriangle className="h-3.5 w-3.5 text-nexus-amber" aria-hidden="true" />
            Degraded / Impacted
          </span>
          <span className="inline-flex items-center gap-1.5 font-mono">
            <CheckCircle2 className="h-3.5 w-3.5 text-nexus-emerald" aria-hidden="true" />
            Healthy / Isolated
          </span>
          <span className="font-mono text-slate-400">
            Animated Edge = Active Failure Propagation
          </span>
        </div>

        {nodes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-obsidian-700 bg-obsidian-950/75 p-8 text-center text-xs text-slate-400">
            {isLoading ? "Loading infrastructure topology..." : "No topology nodes available."}
          </div>
        ) : (
          <>
            {/* Interactive React Flow Graph (hidden on very narrow screens unless Graph mode, with accessible List fallback below) */}
            {viewMode === "graph" ? (
              <div className="hidden md:block">
                <DependencyGraph
                  nodes={nodes}
                  edges={edges}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={setSelectedNodeId}
                />
              </div>
            ) : null}

            {/* Accessible Structured Card Fallback (always shown on < md screens or when List mode is selected) */}
            <div className={viewMode === "graph" ? "md:hidden" : "block"}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {nodes.map((node) => (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => setSelectedNodeId(node.id)}
                    className={`rounded-xl border p-4 text-left transition ${
                      node.is_root_cause_candidate
                        ? "border-nexus-crimson bg-obsidian-950"
                        : node.in_blast_radius
                          ? "border-nexus-amber/60 bg-obsidian-950"
                          : "border-obsidian-700/80 bg-obsidian-950/80 hover:border-nexus-cyan/40"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-slate-100">{node.name}</span>
                      <span
                        className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${statusPillClasses(
                          node.status
                        )}`}
                      >
                        {node.is_root_cause_candidate ? "ROOT CAUSE" : node.status}
                      </span>
                    </div>
                    <div className="mt-1 font-mono text-[10px] text-slate-400">
                      {node.id} · {node.tier}
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[11px] text-slate-200">
                      <span>Lat: {node.metrics.latency_ms.toFixed(0)}ms</span>
                      <span>Err: {(node.metrics.error_rate * 100).toFixed(1)}%</span>
                      <span>Sat: {node.metrics.saturation_pct.toFixed(0)}%</span>
                      <span>
                        {node.tier === "messaging" || node.metrics.queue_depth > 0
                          ? `Queue: ${node.metrics.queue_depth}`
                          : `RPS: ${node.metrics.throughput_rps.toFixed(0)}`}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </Panel>

      {/* Selected Service Inspector */}
      {selectedNode ? (
        <Panel
          title={`Service Inspector — ${selectedNode.name} (${selectedNode.id})`}
          subtitle={`Tier: ${selectedNode.tier} · Criticality: ${selectedNode.criticality}/5 · SLO Latency: ${selectedNode.slo_latency_ms}ms`}
          rightSlot={
            <span
              className={`rounded border px-2 py-0.5 font-mono text-[11px] font-semibold uppercase ${statusPillClasses(
                selectedNode.status
              )}`}
            >
              {selectedNode.is_root_cause_candidate
                ? `ROOT CAUSE · ${selectedNode.status}`
                : selectedNode.in_blast_radius
                  ? `IMPACTED · ${selectedNode.status}`
                  : selectedNode.status}
            </span>
          }
        >
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="grid grid-cols-2 gap-2.5 rounded-lg border border-obsidian-700/70 bg-obsidian-950/80 p-3.5 font-mono text-xs">
              <div>
                <div className="text-[10px] uppercase text-slate-500">Latency</div>
                <div className="mt-0.5 text-slate-100">
                  {selectedNode.metrics.latency_ms.toFixed(1)}ms
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase text-slate-500">Error Rate</div>
                <div className="mt-0.5 text-slate-100">
                  {(selectedNode.metrics.error_rate * 100).toFixed(2)}%
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase text-slate-500">Saturation / CPU</div>
                <div className="mt-0.5 text-slate-100">
                  {selectedNode.metrics.saturation_pct.toFixed(1)}% /{" "}
                  {selectedNode.metrics.cpu_pct.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase text-slate-500">Queue / RPS</div>
                <div className="mt-0.5 text-slate-100">
                  q={selectedNode.metrics.queue_depth} ·{" "}
                  {selectedNode.metrics.throughput_rps.toFixed(0)}/s
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/80 p-3.5 text-xs">
              <div className="font-mono text-[10px] uppercase tracking-wider text-nexus-cyan">
                Depends On ({selectedUpstream.length})
              </div>
              {selectedUpstream.length === 0 ? (
                <p className="mt-2 text-slate-500">Leaf dependency (no outgoing calls).</p>
              ) : (
                <ul className="mt-2 space-y-1.5 font-mono text-[11px] text-slate-300">
                  {selectedUpstream.map((e) => (
                    <li key={e.id}>
                      → {e.target} ({e.protocol}, {e.latency_ms.toFixed(0)}ms, {e.status})
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/80 p-3.5 text-xs">
              <div className="font-mono text-[10px] uppercase tracking-wider text-nexus-teal">
                Called By ({selectedDownstream.length})
              </div>
              {selectedDownstream.length === 0 ? (
                <p className="mt-2 text-slate-500">Edge entry service (no internal callers).</p>
              ) : (
                <ul className="mt-2 space-y-1.5 font-mono text-[11px] text-slate-300">
                  {selectedDownstream.map((e) => (
                    <li key={e.id}>
                      ← {e.source} ({e.protocol}, weight={e.impact_weight})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
