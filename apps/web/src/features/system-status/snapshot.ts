import "server-only";
import {
  getBackendHealth,
  getBackendReadiness,
  type EndpointResult,
} from "@/lib/api/client";
import { getConfig } from "@/lib/config/server";
import type { HealthResponse, ReadinessResponse } from "@/lib/api/schemas";
import type {
  DiagnosticEndpoint,
  ServiceStatus,
  SystemStatusResponse,
} from "./contract";

function diagnostic<T>(
  result: EndpointResult<T>,
  status: ServiceStatus,
): DiagnosticEndpoint {
  const { httpStatus, requestId, durationMs, error } = result;
  return { httpStatus, requestId, durationMs, error, status };
}
export function summarize(
  health: EndpointResult<HealthResponse>,
  ready: EndpointResult<ReadinessResponse>,
): SystemStatusResponse {
  const transportFailed = (error: string | null) =>
    error === "NETWORK_ERROR" || error === "TIMEOUT";
  const unreachable =
    health.httpStatus === null &&
    ready.httpStatus === null &&
    transportFailed(health.error) &&
    transportFailed(ready.error);
  const noEvidence = unreachable ? "unavailable" : "unknown";
  let backend: ServiceStatus = noEvidence;
  let readiness: ServiceStatus = "unknown";
  let database: ServiceStatus = "unknown";
  let overallStatus: ServiceStatus = noEvidence;

  if (health.data) backend = "operational";
  if (ready.data) {
    if (!health.data) backend = "degraded";
    readiness = ready.data.status === "ready" ? "operational" : "degraded";
    if (ready.data.checks.application === "ok") {
      database =
        ready.data.checks.database === "ok" ? "operational" : "degraded";
    }
  }
  if (health.data || ready.data) {
    overallStatus =
      backend === "operational" && readiness === "operational"
        ? "operational"
        : "degraded";
  }
  return {
    checkedAt: new Date().toISOString(),
    overallStatus,
    backend: diagnostic(health, backend),
    database: { status: database },
    readiness: diagnostic(ready, readiness),
  };
}

export async function getSystemStatus() {
  const config = getConfig();
  const [health, ready] = await Promise.all([
    getBackendHealth(config),
    getBackendReadiness(config),
  ]);
  return summarize(health, ready);
}
