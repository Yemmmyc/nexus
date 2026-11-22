"""Internal runtime state dataclasses for the deterministic infrastructure simulator."""

from dataclasses import dataclass, field

from app.schemas.telemetry import ServiceHealthStatus, ServiceMetrics, SeverityLevel


@dataclass(frozen=True)
class ServiceBaseline:
    """Static baseline operating characteristics for a simulated service."""

    id: str
    name: str
    tier: str
    criticality: int
    baseline_latency_ms: float
    slo_latency_ms: float
    slo_error_rate: float
    baseline_error_rate: float
    baseline_throughput_rps: float
    baseline_cpu_pct: float
    baseline_saturation_pct: float
    baseline_queue_depth: int = 0


@dataclass(frozen=True)
class DependencyLink:
    """Directed dependency link: source depends on target."""

    id: str
    source_id: str
    target_id: str
    protocol: str
    impact_weight: float


@dataclass(frozen=True)
class FaultSpec:
    """Mathematical fault pressure parameters applied to a target service."""

    target_service_id: str
    ramp_tau_ticks: float
    latency_linear_gain: float
    latency_quadratic_gain: float
    saturation_delta_pct: float
    cpu_delta_pct: float
    error_rate_delta: float


@dataclass(frozen=True)
class ScenarioSpec:
    """Definition of a repeatable fault scenario."""

    id: str
    name: str
    description: str
    root_service: str
    expected_severity: SeverityLevel
    faults: tuple[FaultSpec, ...]


@dataclass
class ActiveFault:
    """Runtime instance of an injected fault."""

    scenario_id: str
    spec: FaultSpec
    injected_tick: int


@dataclass
class ServiceRuntimeState:
    """Mutable per-service state updated on every simulation tick."""

    baseline: ServiceBaseline
    status: ServiceHealthStatus = "healthy"
    metrics: ServiceMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.metrics = ServiceMetrics(
            latency_ms=self.baseline.baseline_latency_ms,
            error_rate=self.baseline.baseline_error_rate,
            throughput_rps=self.baseline.baseline_throughput_rps,
            cpu_pct=self.baseline.baseline_cpu_pct,
            saturation_pct=self.baseline.baseline_saturation_pct,
            queue_depth=self.baseline.baseline_queue_depth,
        )

