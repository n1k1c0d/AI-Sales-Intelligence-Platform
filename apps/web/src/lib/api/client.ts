import "server-only";
import { z } from "zod";
import type { ApiError } from "@/features/system-status/contract";
import type { ServerConfig } from "@/lib/config/server";
import { healthSchema, readinessSchema } from "./schemas";

type Metadata = {
  httpStatus: number | null;
  requestId: string | null;
  durationMs: number | null;
};
export type EndpointResult<T> = Metadata &
  ({ data: T; error: null } | { data: null; error: ApiError });

async function probe<T>(
  config: ServerConfig | null,
  path: "/api/v1/health" | "/api/v1/ready",
  schema: z.ZodType<T>,
  accepts: (status: number, data: T) => boolean,
): Promise<EndpointResult<T>> {
  if (!config)
    return {
      data: null,
      error: "CONFIGURATION_ERROR",
      httpStatus: null,
      durationMs: null,
      requestId: null,
    };
  const started = performance.now();
  const signal = AbortSignal.timeout(config.timeoutMs);
  let httpStatus: number | null = null;
  let requestId: string | null = null;
  const meta = () => ({
    httpStatus,
    requestId,
    durationMs: Math.round(performance.now() - started),
  });
  const fail = (error: ApiError) => ({ ...meta(), data: null, error });
  try {
    const response = await fetch(config.origin + path, {
      signal,
      cache: "no-store",
      redirect: "manual",
      headers: { Accept: "application/json" },
    });
    httpStatus = response.status;
    requestId =
      z.uuidv4().safeParse(response.headers.get("x-request-id")).data ?? null;
    if (httpStatus !== 200 && !(path === "/api/v1/ready" && httpStatus === 503))
      return fail("HTTP_ERROR");
    if (
      response.headers
        .get("content-type")
        ?.split(";")[0]
        .trim()
        .toLowerCase() !== "application/json"
    )
      return fail("INVALID_RESPONSE");
    const payload: unknown = await response.json();
    const result = schema.safeParse(payload);
    if (!result.success || !accepts(httpStatus, result.data))
      return fail("INVALID_RESPONSE");
    return { ...meta(), data: result.data, error: null };
  } catch (error) {
    return fail(
      signal.aborted
        ? "TIMEOUT"
        : error instanceof SyntaxError
          ? "INVALID_RESPONSE"
          : "NETWORK_ERROR",
    );
  }
}

export function getBackendHealth(config: ServerConfig | null) {
  return probe(
    config,
    "/api/v1/health",
    healthSchema,
    (status) => status === 200,
  );
}
export function getBackendReadiness(config: ServerConfig | null) {
  return probe(
    config,
    "/api/v1/ready",
    readinessSchema,
    (status, data) => status === (data.status === "ready" ? 200 : 503),
  );
}
