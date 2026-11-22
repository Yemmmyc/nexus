"""Directed service dependency graph built from the approved 7-service topology."""

from collections import deque

from app.db.seed import DEFAULT_DEPENDENCIES, DEFAULT_SERVICES
from app.simulator.models import DependencyLink, ServiceBaseline

# Realistic per-service baseline throughput, CPU, saturation, and queue profiles
_SERVICE_PROFILES: dict[str, dict[str, float | int]] = {
    "api-gateway": {
        "baseline_error_rate": 0.001,
        "baseline_throughput_rps": 420.0,
        "baseline_cpu_pct": 26.0,
        "baseline_saturation_pct": 22.0,
        "baseline_queue_depth": 0,
    },
    "auth-service": {
        "baseline_error_rate": 0.0008,
        "baseline_throughput_rps": 310.0,
        "baseline_cpu_pct": 21.0,
        "baseline_saturation_pct": 18.0,
        "baseline_queue_depth": 0,
    },
    "checkout-api": {
        "baseline_error_rate": 0.0015,
        "baseline_throughput_rps": 190.0,
        "baseline_cpu_pct": 32.0,
        "baseline_saturation_pct": 26.0,
        "baseline_queue_depth": 0,
    },
    "payment-service": {
        "baseline_error_rate": 0.0012,
        "baseline_throughput_rps": 165.0,
        "baseline_cpu_pct": 29.0,
        "baseline_saturation_pct": 24.0,
        "baseline_queue_depth": 0,
    },
    "order-queue": {
        "baseline_error_rate": 0.0002,
        "baseline_throughput_rps": 185.0,
        "baseline_cpu_pct": 16.0,
        "baseline_saturation_pct": 15.0,
        "baseline_queue_depth": 12,
    },
    "worker-fulfillment": {
        "baseline_error_rate": 0.002,
        "baseline_throughput_rps": 185.0,
        "baseline_cpu_pct": 34.0,
        "baseline_saturation_pct": 30.0,
        "baseline_queue_depth": 0,
    },
    "postgres-primary": {
        "baseline_error_rate": 0.0005,
        "baseline_throughput_rps": 540.0,
        "baseline_cpu_pct": 31.0,
        "baseline_saturation_pct": 28.0,
        "baseline_queue_depth": 0,
    },
}


class TopologyGraph:
    """Directed acyclic service dependency graph (source depends on target)."""

    def __init__(
        self,
        services: list[ServiceBaseline] | None = None,
        edges: list[DependencyLink] | None = None,
    ) -> None:
        if services is None:
            services = [
                ServiceBaseline(
                    id=svc["id"],
                    name=svc["name"],
                    tier=svc["tier"],
                    criticality=svc["criticality"],
                    baseline_latency_ms=svc["baseline_latency_ms"],
                    slo_latency_ms=svc["slo_latency_ms"],
                    slo_error_rate=svc["slo_error_rate"],
                    baseline_error_rate=float(_SERVICE_PROFILES[svc["id"]]["baseline_error_rate"]),
                    baseline_throughput_rps=float(_SERVICE_PROFILES[svc["id"]]["baseline_throughput_rps"]),
                    baseline_cpu_pct=float(_SERVICE_PROFILES[svc["id"]]["baseline_cpu_pct"]),
                    baseline_saturation_pct=float(_SERVICE_PROFILES[svc["id"]]["baseline_saturation_pct"]),
                    baseline_queue_depth=int(_SERVICE_PROFILES[svc["id"]]["baseline_queue_depth"]),
                )
                for svc in DEFAULT_SERVICES
            ]
        if edges is None:
            edges = [
                DependencyLink(
                    id=edge["id"],
                    source_id=edge["source_id"],
                    target_id=edge["target_id"],
                    protocol=edge["protocol"],
                    impact_weight=edge["impact_weight"],
                )
                for edge in DEFAULT_DEPENDENCIES
            ]

        self._services: dict[str, ServiceBaseline] = {s.id: s for s in services}
        self._service_order: list[str] = [s.id for s in services]
        self._edges: list[DependencyLink] = list(edges)

        self._outgoing: dict[str, list[DependencyLink]] = {sid: [] for sid in self._services}
        self._incoming: dict[str, list[DependencyLink]] = {sid: [] for sid in self._services}
        for edge in self._edges:
            self._outgoing[edge.source_id].append(edge)
            self._incoming[edge.target_id].append(edge)

        self._bottom_up_order: list[str] = self._compute_bottom_up_order()

    @property
    def services(self) -> list[ServiceBaseline]:
        """Return all service baselines in canonical order."""
        return [self._services[sid] for sid in self._service_order]

    @property
    def edges(self) -> list[DependencyLink]:
        """Return all directed dependency edges."""
        return list(self._edges)

    def get_service(self, service_id: str) -> ServiceBaseline:
        """Retrieve a service baseline by ID."""
        return self._services[service_id]

    def dependencies_of(self, service_id: str) -> list[DependencyLink]:
        """Return outgoing edges (services that service_id depends on)."""
        return list(self._outgoing.get(service_id, []))

    def dependents_of(self, service_id: str) -> list[DependencyLink]:
        """Return incoming edges (services that depend on service_id)."""
        return list(self._incoming.get(service_id, []))

    def bottom_up_order(self) -> list[str]:
        """Return service IDs ordered so dependencies are evaluated before callers."""
        return list(self._bottom_up_order)

    def blast_radius(self, root_service_id: str) -> list[str]:
        """Return root service and all transitive callers/dependents (BFS)."""
        if root_service_id not in self._services:
            return []
        visited: set[str] = {root_service_id}
        queue: deque[str] = deque([root_service_id])
        ordered: list[str] = []

        while queue:
            current = queue.popleft()
            ordered.append(current)
            for edge in self._incoming.get(current, []):
                if edge.source_id not in visited:
                    visited.add(edge.source_id)
                    queue.append(edge.source_id)
        return ordered

    def are_connected(self, service_a: str, service_b: str) -> bool:
        """Return True if two services are connected in the undirected topology."""
        if service_a == service_b:
            return True
        if service_a not in self._services or service_b not in self._services:
            return False

        visited: set[str] = {service_a}
        queue: deque[str] = deque([service_a])
        while queue:
            current = queue.popleft()
            neighbors = [e.target_id for e in self._outgoing[current]] + [
                e.source_id for e in self._incoming[current]
            ]
            for nxt in neighbors:
                if nxt == service_b:
                    return True
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return False

    def _compute_bottom_up_order(self) -> list[str]:
        """Kahn's algorithm evaluating dependency targets before their callers."""
        remaining_deps = {sid: len(self._outgoing[sid]) for sid in self._service_order}
        ready = deque(sid for sid in self._service_order if remaining_deps[sid] == 0)
        order: list[str] = []

        while ready:
            node = ready.popleft()
            order.append(node)
            for incoming_edge in self._incoming[node]:
                caller = incoming_edge.source_id
                remaining_deps[caller] -= 1
                if remaining_deps[caller] == 0:
                    ready.append(caller)

        if len(order) != len(self._service_order):
            raise ValueError("Topology dependency graph contains a cycle.")
        return order

