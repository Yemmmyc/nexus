import { useCallback, useEffect, useState } from "react";
import {
  advanceSimulation,
  fetchHealth,
  fetchSimulationStatus,
  injectScenario,
  resetSimulation,
  startSimulation,
  stopSimulation,
} from "./api/client";
import { Sidebar } from "./components/layout/Sidebar";
import { TopBar } from "./components/layout/TopBar";
import type { HealthResponse, NavSection, SimulationStatusResponse } from "./types/health";
import { AuditView } from "./views/AuditView";
import { DashboardView } from "./views/DashboardView";
import { IncidentsView } from "./views/IncidentsView";
import { TopologyView } from "./views/TopologyView";

export function App() {
  const [activeSection, setActiveSection] = useState<NavSection>("overview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [simStatus, setSimStatus] = useState<SimulationStatusResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [isSimBusy, setIsSimBusy] = useState(false);

  const loadStatus = useCallback(async () => {
    setIsCheckingHealth(true);
    try {
      const [healthData, statusData] = await Promise.all([
        fetchHealth(),
        fetchSimulationStatus(),
      ]);
      setHealth(healthData);
      setSimStatus(statusData);
      setHealthError(null);
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : "Backend unreachable");
    } finally {
      setIsCheckingHealth(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (!simStatus?.running) return;
    const timer = window.setInterval(() => {
      void fetchSimulationStatus().then(setSimStatus).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [simStatus?.running]);

  const runSimAction = useCallback(
    async (action: () => Promise<SimulationStatusResponse>) => {
      setIsSimBusy(true);
      try {
        const updated = await action();
        setSimStatus(updated);
        const h = await fetchHealth();
        setHealth(h);
        setHealthError(null);
      } catch (err) {
        setHealthError(err instanceof Error ? err.message : "Simulation action failed");
      } finally {
        setIsSimBusy(false);
      }
    },
    []
  );

  return (
    <div className="flex min-h-screen flex-col bg-obsidian-950 text-slate-100 lg:flex-row">
      <Sidebar
        activeSection={activeSection}
        onSelectSection={setActiveSection}
        aiMode={health?.ai_mode ?? "deterministic"}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          activeSection={activeSection}
          health={health}
          healthError={healthError}
          isCheckingHealth={isCheckingHealth}
          onRefreshHealth={() => void loadStatus()}
        />

        <main className="flex-1 p-6">
          {activeSection === "overview" && (
            <DashboardView
              health={health}
              simStatus={simStatus}
              isSimBusy={isSimBusy}
              onStartSim={() => void runSimAction(startSimulation)}
              onStopSim={() => void runSimAction(stopSimulation)}
              onAdvanceTick={() => void runSimAction(() => advanceSimulation(1))}
              onInjectDbCascade={() =>
                void runSimAction(() => injectScenario("db_latency_cascade"))
              }
              onResetSim={() => void runSimAction(resetSimulation)}
            />
          )}
          {activeSection === "topology" && (
            <TopologyView
              simStatus={simStatus}
              isSimBusy={isSimBusy}
              onStartSim={() => void runSimAction(startSimulation)}
              onStopSim={() => void runSimAction(stopSimulation)}
              onAdvanceTick={() => void runSimAction(() => advanceSimulation(1))}
              onInjectDbCascade={() =>
                void runSimAction(() => injectScenario("db_latency_cascade"))
              }
              onResetSim={() => void runSimAction(resetSimulation)}
            />
          )}
          {activeSection === "incidents" && <IncidentsView />}
          {activeSection === "audit" && <AuditView />}
        </main>
      </div>
    </div>
  );
}

export default App;
