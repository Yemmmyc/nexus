import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Database,
  Globe,
  Layers,
  Server,
} from "lucide-react";
import type { ServiceNodeState } from "../../types/topology";

export interface ServiceNodeData extends Record<string, unknown> {
  service: ServiceNodeState;
  isSelected: boolean;
}

export type ServiceFlowNode = Node<ServiceNodeData, "serviceNode">;

function TierIcon({ tier }: { tier: string }) {
  switch (tier) {
    case "edge":
      return <Globe className="h-3.5 w-3.5 text-nexus-cyan" aria-hidden="true" />;
    case "database":
      return <Database className="h-3.5 w-3.5 text-nexus-teal" aria-hidden="true" />;
    case "messaging":
      return <Layers className="h-3.5 w-3.5 text-amber-300" aria-hidden="true" />;
    case "worker":
      return <Cpu className="h-3.5 w-3.5 text-cyan-300" aria-hidden="true" />;
    default:
      return <Server className="h-3.5 w-3.5 text-slate-300" aria-hidden="true" />;
  }
}

export function ServiceNodeCard({ data }: NodeProps<ServiceFlowNode>) {
  const { service, isSelected } = data;
  const { metrics } = service;
  const isRoot = service.is_root_cause_candidate;
  const isCritical = service.status === "critical";
  const isDegraded = service.status === "degraded";
  const showQueue = service.tier === "messaging" || metrics.queue_depth > 0;

  let containerStyle =
    "border-obsidian-700/90 bg-obsidian-900/95 hover:border-nexus-cyan/50";
  let statusBadgeStyle =
    "border-nexus-emerald/40 bg-nexus-emerald/15 text-emerald-200";
  let statusLabel = "HEALTHY";
  let StatusIcon = CheckCircle2;

  if (isRoot) {
    containerStyle =
      "border-nexus-crimson bg-obsidian-900/95 ring-2 ring-nexus-crimson/35 shadow-[0_0_26px_-6px_rgba(244,63,94,0.55)]";
    statusBadgeStyle = "border-nexus-crimson/60 bg-nexus-crimson/20 text-rose-100";
    statusLabel = isCritical ? "CRITICAL" : isDegraded ? "DEGRADED" : "HEALTHY";
    StatusIcon = AlertOctagon;
  } else if (isCritical) {
    containerStyle =
      "border-nexus-crimson/75 bg-obsidian-900/95 shadow-[0_0_20px_-8px_rgba(244,63,94,0.4)]";
    statusBadgeStyle = "border-nexus-crimson/50 bg-nexus-crimson/15 text-rose-200";
    statusLabel = "CRITICAL";
    StatusIcon = AlertOctagon;
  } else if (isDegraded) {
    containerStyle =
      "border-nexus-amber/75 bg-obsidian-900/95 shadow-[0_0_20px_-8px_rgba(245,158,11,0.35)]";
    statusBadgeStyle = "border-nexus-amber/50 bg-nexus-amber/15 text-amber-200";
    statusLabel = "DEGRADED";
    StatusIcon = AlertTriangle;
  }

  if (isSelected) {
    containerStyle += " ring-2 ring-nexus-cyan/70";
  }

  return (
    <div
      className={`relative w-[232px] rounded-xl border p-3.5 text-left transition-all ${containerStyle}`}
      role="group"
      aria-label={`${service.name} (${statusLabel})`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2.5 !w-2.5 !border-obsidian-950 !bg-nexus-cyan"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2.5 !w-2.5 !border-obsidian-950 !bg-nexus-teal"
      />

      {isRoot ? (
        <div className="mb-2 flex items-center justify-between rounded-md border border-nexus-crimson/60 bg-nexus-crimson/20 px-2 py-0.5">
          <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold tracking-wider text-rose-100">
            <span className="h-1.5 w-1.5 animate-ping rounded-full bg-nexus-crimson" />
            ROOT CAUSE
          </span>
          <span className="font-mono text-[9px] uppercase text-rose-200">Origin</span>
        </div>
      ) : service.in_blast_radius ? (
        <div className="mb-2 flex items-center justify-between rounded-md border border-nexus-amber/40 bg-nexus-amber/10 px-2 py-0.5">
          <span className="font-mono text-[10px] font-semibold tracking-wider text-amber-200">
            IMPACTED
          </span>
          <span className="font-mono text-[9px] uppercase text-amber-300/80">Cascade</span>
        </div>
      ) : null}

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <TierIcon tier={service.tier} />
            <span className="truncate text-xs font-semibold text-slate-100">
              {service.name}
            </span>
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-slate-400">
            {service.id} · {service.tier}
          </div>
        </div>

        <span
          className={`inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[9px] font-semibold ${statusBadgeStyle}`}
        >
          <StatusIcon className="h-2.5 w-2.5" aria-hidden="true" />
          {statusLabel}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-1.5 border-t border-obsidian-700/70 pt-2.5 font-mono text-[10px]">
        <div className="rounded bg-obsidian-950/80 px-2 py-1">
          <div className="text-[9px] uppercase text-slate-500">Latency</div>
          <div
            className={`font-semibold ${
              metrics.latency_ms >= service.slo_latency_ms * 1.25
                ? "text-rose-300"
                : "text-slate-100"
            }`}
          >
            {metrics.latency_ms.toFixed(0)}ms
          </div>
        </div>

        <div className="rounded bg-obsidian-950/80 px-2 py-1">
          <div className="text-[9px] uppercase text-slate-500">Error Rate</div>
          <div
            className={`font-semibold ${
              metrics.error_rate >= service.slo_error_rate * 2
                ? "text-rose-300"
                : "text-slate-100"
            }`}
          >
            {(metrics.error_rate * 100).toFixed(1)}%
          </div>
        </div>

        <div className="rounded bg-obsidian-950/80 px-2 py-1">
          <div className="text-[9px] uppercase text-slate-500">Saturation</div>
          <div
            className={`font-semibold ${
              metrics.saturation_pct >= 75 ? "text-amber-300" : "text-slate-200"
            }`}
          >
            {metrics.saturation_pct.toFixed(0)}%
          </div>
        </div>

        {showQueue ? (
          <div className="rounded bg-obsidian-950/80 px-2 py-1">
            <div className="text-[9px] uppercase text-slate-500">Queue</div>
            <div
              className={`font-semibold ${
                metrics.queue_depth >= 250 ? "text-amber-300" : "text-slate-200"
              }`}
            >
              {metrics.queue_depth}
            </div>
          </div>
        ) : (
          <div className="rounded bg-obsidian-950/80 px-2 py-1">
            <div className="text-[9px] uppercase text-slate-500">Throughput</div>
            <div className="font-semibold text-slate-200">
              {metrics.throughput_rps.toFixed(0)}/s
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

