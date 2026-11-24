import { z } from "zod";

export const serviceStatus = z.enum([
  "operational",
  "degraded",
  "unavailable",
  "unknown",
]);
export type ServiceStatus = z.infer<typeof serviceStatus>;
export const apiError = z.enum([
  "NETWORK_ERROR",
  "TIMEOUT",
  "INVALID_RESPONSE",
  "HTTP_ERROR",
  "CONFIGURATION_ERROR",
]);
export type ApiError = z.infer<typeof apiError>;
const endpoint = z.object({
  status: serviceStatus,
  httpStatus: z.number().int().min(100).max(599).nullable(),
  requestId: z.uuidv4().nullable(),
  durationMs: z.number().nonnegative().nullable(),
  error: apiError.nullable(),
});
export const snapshotSchema = z.object({
  checkedAt: z.iso.datetime(),
  overallStatus: serviceStatus,
  backend: endpoint,
  database: z.object({ status: serviceStatus }),
  readiness: endpoint,
});
export type SystemStatusResponse = z.infer<typeof snapshotSchema>;
export type DiagnosticEndpoint = SystemStatusResponse["backend"];
