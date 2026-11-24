"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Activity,
  Check,
  CircleAlert,
  Database,
  Globe2,
  Monitor,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  SquareTerminal,
  Timer,
} from "lucide-react";
import { Button, StatusCard, type DisplayStatus } from "@/components/ui";
import {
  snapshotSchema,
  type ApiError,
  type DiagnosticEndpoint,
  type SystemStatusResponse,
} from "./contract";

const messages: Record<ApiError, string> = {
  NETWORK_ERROR: "Connection failed",
  TIMEOUT: "Check timed out",
  INVALID_RESPONSE: "Invalid response",
  HTTP_ERROR: "Unexpected HTTP status",
  CONFIGURATION_ERROR: "Check server configuration",
};
const summary = {
  operational: [
    "All systems operational",
    "All four service checks are passing.",
  ],
  degraded: [
    "System degraded",
    "One or more checks need attention. Review the diagnostics below.",
  ],
  unavailable: [
    "Backend unavailable",
    "The web app is online. Database readiness could not be confirmed.",
  ],
  unknown: [
    "System status unknown",
    "The available checks could not confirm the system state.",
  ],
  checking: [
    "Checking system status",
    "Contacting the backend for the latest service checks.",
  ],
};

function Diagnostics({ data }: { data: SystemStatusResponse | null }) {
  function row(name: string, path: string, endpoint?: DiagnosticEndpoint) {
    return (
      <div className="diagnostic-row">
        <div className="probe-icon">
          <Activity size={17} />
        </div>
        <div className="probe-data">
          <h3>
            {name} <code>{path}</code>
          </h3>
          <p>
            <span>Request ID</span> <code>{endpoint?.requestId ?? "—"}</code>
          </p>
          {endpoint?.error && (
            <small className="error-note">{messages[endpoint.error]}</small>
          )}
        </div>
        <div className="probe-result">
          <code
            className={endpoint?.httpStatus === 200 ? "http-ok" : "http-other"}
          >
            {endpoint?.httpStatus ? `HTTP ${endpoint.httpStatus}` : "—"}
          </code>
          <small>
            {endpoint?.durationMs != null ? `${endpoint.durationMs} ms` : "—"}
          </small>
        </div>
      </div>
    );
  }
  return (
    <section className="panel diagnostics" aria-labelledby="diag-heading">
      <div className="panel-heading">
        <SquareTerminal size={18} />
        <h2 id="diag-heading">Request diagnostics</h2>
      </div>
      {row("Liveness", "/api/v1/health", data?.backend)}
      {row("Readiness", "/api/v1/ready", data?.readiness)}
    </section>
  );
}

async function readSnapshot(signal: AbortSignal) {
  const response = await fetch("/api/system/status", {
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Snapshot unavailable");
  return snapshotSchema.parse(await response.json());
}

export function StatusPanel({ projectInfo }: { projectInfo: ReactNode }) {
  const [snapshot, setSnapshot] = useState<SystemStatusResponse | null>(null);
  const [busy, setBusy] = useState(true);
  const [failed, setFailed] = useState(false);
  const current = useRef<AbortController | null>(null);

  function checkStatus() {
    if (current.current) return;
    const controller = new AbortController();
    current.current = controller;
    function finish(result: SystemStatusResponse | null) {
      if (controller.signal.aborted) return;
      current.current = null;
      setSnapshot(result);
      setFailed(result === null);
      setBusy(false);
    }
    void readSnapshot(controller.signal).then(finish, () => finish(null));
  }
  useEffect(() => {
    checkStatus();
    return () => {
      current.current?.abort();
      current.current = null;
    };
  }, []);

  function refresh() {
    if (current.current) return;
    setBusy(true);
    checkStatus();
  }

  const fallback: DisplayStatus = failed ? "unknown" : "checking";
  const overall = snapshot?.overallStatus ?? fallback;
  const web: DisplayStatus = snapshot ? "operational" : fallback;
  const backend = snapshot?.backend.status ?? fallback;
  const database = snapshot?.database.status ?? fallback;
  const readiness = snapshot?.readiness.status ?? fallback;
  const Icon =
    overall === "operational"
      ? Check
      : overall === "checking"
        ? Radio
        : CircleAlert;
  const time = snapshot
    ? new Date(snapshot.checkedAt).toISOString().slice(11, 19) + " UTC"
    : "—";
  return (
    <>
      <div className="toolbar">
        <div className="check-time">
          <Timer size={14} />
          <span>Last checked</span>
          <time dateTime={snapshot?.checkedAt} title={snapshot?.checkedAt}>
            {time}
          </time>
        </div>
        <Button onClick={refresh} disabled={busy}>
          <RefreshCw size={15} className={busy ? "spin" : ""} />
          {busy ? "Checking…" : "Refresh Status"}
        </Button>
      </div>
      <section
        className={`summary tone-${overall}`}
        aria-label="Overall system status"
      >
        <div className="summary-main" role="status" aria-live="polite">
          <div className="state-symbol">
            <Icon size={28} />
          </div>
          <div>
            <span className="kicker">System status</span>
            <h2>{failed ? "Status check unavailable" : summary[overall][0]}</h2>
            <p>
              {failed
                ? "The web app could not retrieve diagnostics. Refresh to try again."
                : summary[overall][1]}
            </p>
          </div>
        </div>
        <div className="topology" aria-hidden="true">
          {[
            { icon: Monitor, label: "Web", status: web },
            { icon: Server, label: "API", status: backend },
            { icon: Database, label: "Database", status: database },
          ].map(({ icon: Node, label, status }) => (
            <div className={`topo-node tone-${status}`} key={label}>
              <span>
                <Node size={18} />
              </span>
              <small>{label}</small>
            </div>
          ))}
        </div>
      </section>
      <section aria-labelledby="services-title" className="services">
        <div className="section-title">
          <h2 id="services-title">Service health</h2>
          <span className="count">4 services</span>
        </div>
        <div className="cards">
          <StatusCard
            name="Backend API"
            icon={Server}
            color="mint"
            status={backend}
            description="FastAPI process availability"
            detail="GET /api/v1/health"
          />
          <StatusCard
            name="PostgreSQL"
            icon={Database}
            color="blue"
            status={database}
            label={database === "degraded" ? "Not ready" : undefined}
            description="Database connectivity"
            detail="checks.database"
          />
          <StatusCard
            name="System Readiness"
            icon={ShieldCheck}
            color="violet"
            status={readiness}
            label={readiness === "degraded" ? "Not ready" : undefined}
            description="Application and database checks"
            detail="GET /api/v1/ready"
          />
          <StatusCard
            name="Web Application"
            icon={Globe2}
            color="peach"
            status={web}
            description="Next.js diagnostics availability"
            detail="GET /api/system/status"
          />
        </div>
      </section>
      <div className="details-grid">
        <Diagnostics data={snapshot} />
        {projectInfo}
      </div>
      <span className="sr-only" role="status">
        {busy ? "Checking services" : "Status check complete"}
      </span>
    </>
  );
}
