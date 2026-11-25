import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { DependencyEdgeState, ServiceNodeState } from "../../types/topology";
import { ServiceNodeCard, type ServiceFlowNode } from "./ServiceNodeCard";

interface DependencyGraphProps {
  nodes: ServiceNodeState[];
  edges: DependencyEdgeState[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
}

const NODE_TYPES = {
  serviceNode: ServiceNodeCard,
};

/**
 * Deterministic left-to-right architectural placement derived from node tiers and
 * dependency structure (no hardcoded mock metrics; gracefully positions any service).
 */
function computeNodePositions(
  nodes: ServiceNodeState[],
  edges: DependencyEdgeState[]
): Record<string, { x: number; y: number }> {
  const incomingCount: Record<string, number> = {};
  const outgoingCount: Record<string, number> = {};
  for (const n of nodes) {
    incomingCount[n.id] = 0;
    outgoingCount[n.id] = 0;
  }
  for (const e of edges) {
    outgoingCount[e.source] = (outgoingCount[e.source] ?? 0) + 1;
    incomingCount[e.target] = (incomingCount[e.target] ?? 0) + 1;
  }

  // Assign columns left-to-right: Edge (0) -> App Entry (1) -> Downstream App/Queue/Worker (2) -> Database (3)
  const columns: Record<number, ServiceNodeState[]> = { 0: [], 1: [], 2: [], 3: [] };
  for (const n of nodes) {
    let col = 1;
    if (n.tier === "edge") {
      col = 0;
    } else if (n.tier === "database") {
      col = 3;
    } else if (n.tier === "messaging" || n.tier === "worker") {
      col = 2;
    } else if (n.tier === "application") {
      // Application services that are called by another application go to column 2
      const calledByApp = edges.some(
        (e) =>
          e.target === n.id &&
          nodes.find((src) => src.id === e.source)?.tier === "application"
      );
      col = calledByApp ? 2 : 1;
    }
    columns[col].push(n);
  }

  const colSpacing = 310;
  const rowSpacing = 205;
  const positions: Record<string, { x: number; y: number }> = {};

  for (const colKey of [0, 1, 2, 3]) {
    const colNodes = columns[colKey];
    const totalHeight = Math.max(0, (colNodes.length - 1) * rowSpacing);
    const startY = Math.max(40, (440 - totalHeight) / 2);
    colNodes.forEach((n, idx) => {
      positions[n.id] = {
        x: 36 + colKey * colSpacing,
        y: startY + idx * rowSpacing,
      };
    });
  }

  return positions;
}

export function DependencyGraph({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
}: DependencyGraphProps) {
  const flowNodes: ServiceFlowNode[] = useMemo(() => {
    const positions = computeNodePositions(nodes, edges);
    return nodes.map((service) => ({
      id: service.id,
      type: "serviceNode",
      position: positions[service.id] ?? { x: 40, y: 40 },
      data: {
        service,
        isSelected: service.id === selectedNodeId,
      },
      draggable: true,
    }));
  }, [nodes, edges, selectedNodeId]);

  const flowEdges: Edge[] = useMemo(() => {
    const nodesById = new Map(nodes.map((n) => [n.id, n]));
    return edges.map((edge) => {
      const targetNode = nodesById.get(edge.target);
      const effectiveStatus =
        targetNode && targetNode.status === "healthy" ? "healthy" : edge.status;
      const isCritical = effectiveStatus === "critical";
      const isDegraded = effectiveStatus === "degraded";
      const stroke = isCritical ? "#f43f5e" : isDegraded ? "#f59e0b" : "#3b5274";

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: isCritical || isDegraded,
        label: `${edge.protocol} · ${edge.latency_ms.toFixed(0)}ms`,
        labelStyle: {
          fill: isCritical ? "#fecdd3" : isDegraded ? "#fde68a" : "#94a3b8",
          fontSize: 10,
          fontFamily: "JetBrains Mono, ui-monospace, monospace",
        },
        labelBgStyle: {
          fill: "#070b11",
          fillOpacity: 0.9,
        },
        labelBgPadding: [5, 3] as [number, number],
        labelBgBorderRadius: 4,
        style: {
          stroke,
          strokeWidth: isCritical ? 2.5 : isDegraded ? 2 : 1.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: stroke,
          width: 16,
          height: 16,
        },
      };
    });
  }, [edges, nodes]);

  return (
    <div
      className="h-[540px] w-full overflow-hidden rounded-xl border border-obsidian-700/80 bg-obsidian-950"
      aria-label="Interactive service dependency topology graph"
    >
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={NODE_TYPES}
        onNodeClick={(_event, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.45}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={22}
          size={1}
          color="#223047"
        />
        <Controls
          showInteractive={false}
          className="nexus-rf-controls"
        />
        <MiniMap
          pannable
          zoomable
          className="nexus-rf-minimap"
          maskColor="rgba(7, 11, 17, 0.72)"
          nodeColor={(node) => {
            const svc = (node.data as ServiceFlowNode["data"] | undefined)?.service;
            if (!svc) return "#334155";
            if (svc.is_root_cause_candidate || svc.status === "critical") return "#f43f5e";
            if (svc.status === "degraded") return "#f59e0b";
            return "#10b981";
          }}
        />
      </ReactFlow>
    </div>
  );
}

