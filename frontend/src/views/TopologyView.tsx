import { GitBranch, Network } from "lucide-react";
import { Panel } from "../components/common/Panel";

const TOPOLOGY_EDGES = [
  { source: "api-gateway", target: "auth-service", protocol: "gRPC" },
  { source: "api-gateway", target: "checkout-api", protocol: "HTTP" },
  { source: "checkout-api", target: "payment-service", protocol: "gRPC" },
  { source: "checkout-api", target: "order-queue", protocol: "AMQP" },
  { source: "checkout-api", target: "postgres-primary", protocol: "TCP/Postgres" },
  { source: "payment-service", target: "postgres-primary", protocol: "TCP/Postgres" },
  { source: "worker-fulfillment", target: "order-queue", protocol: "AMQP" },
  { source: "worker-fulfillment", target: "postgres-primary", protocol: "TCP/Postgres" },
];

export function TopologyView() {
  return (
    <div className="space-y-6">
      <Panel
        title="Interactive Service Dependency Graph"
        subtitle="React Flow (@xyflow/react) live canvas — connects to /api/v1/topology in Phase 1"
        rightSlot={
          <span className="inline-flex items-center gap-1.5 rounded-md border border-nexus-cyan/30 bg-nexus-cyan/10 px-2.5 py-1 font-mono text-[11px] text-nexus-cyan">
            <Network className="h-3.5 w-3.5" />7 NODES · 8 EDGES
          </span>
        }
      >
        <div className="nexus-grid-bg flex min-h-[260px] flex-col items-center justify-center rounded-lg border border-dashed border-obsidian-700 bg-obsidian-950/80 p-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-nexus-cyan/30 bg-nexus-cyan/10 text-nexus-cyan">
            <GitBranch className="h-6 w-6" />
          </div>
          <h3 className="mt-4 text-sm font-semibold text-slate-100">
            Live Dependency Graph Canvas Ready
          </h3>
          <p className="mt-1.5 max-w-md text-xs leading-relaxed text-slate-400">
            In Phase 1 &amp; Phase 3, this canvas renders real-time node latency, error rates,
            blast-radius rings, probable root-cause indicators, and animated cascading failure
            edges.
          </p>
        </div>

        <div className="mt-5 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {TOPOLOGY_EDGES.map((edge) => (
            <div
              key={`${edge.source}-${edge.target}`}
              className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/70 px-3 py-2.5 font-mono text-[11px]"
            >
              <div className="text-slate-200">{edge.source}</div>
              <div className="my-0.5 text-nexus-cyan">→ {edge.target}</div>
              <div className="text-[10px] uppercase tracking-wider text-slate-500">
                {edge.protocol}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

