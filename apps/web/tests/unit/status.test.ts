import { describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/system/status/route";
import { getBackendHealth, getBackendReadiness } from "@/lib/api/client";
import { getConfig } from "@/lib/config/server";
import { getSystemStatus } from "@/features/system-status/snapshot";

const config = { origin: "http://localhost:8000", timeoutMs: 100 };
const health = { status: "ok", service: "dealmind-api" };
const ready = {
  status: "ready",
  checks: { application: "ok", database: "ok" },
};
const down = {
  status: "not_ready",
  checks: { application: "ok", database: "not_ready" },
};
const id = "4d5325fe-09fa-4744-8a3d-b446ce117af0";

function mockFetch() {
  const request = vi.fn<typeof fetch>();
  vi.stubGlobal("fetch", request);
  vi.stubEnv("API_BASE_URL", config.origin);
  return request;
}
function json(data: unknown, status = 200, headers?: HeadersInit) {
  return Response.json(data, { status, headers });
}

describe("FastAPI contracts", () => {
  it("TC-001 parses health", async () => {
    mockFetch().mockResolvedValue(json(health));
    expect(await getBackendHealth(config)).toMatchObject({
      data: health,
      error: null,
      httpStatus: 200,
    });
  });
  it("TC-002 parses readiness", async () => {
    mockFetch().mockResolvedValue(json(ready));
    expect((await getBackendReadiness(config)).data).toEqual(ready);
  });
  it("TC-003 preserves valid readiness 503", async () => {
    mockFetch().mockResolvedValue(json(down, 503));
    expect(await getBackendReadiness(config)).toMatchObject({
      data: down,
      error: null,
      httpStatus: 503,
    });
  });
  it("TC-004 safely normalizes connection errors", async () => {
    mockFetch().mockRejectedValue(new Error("private upstream address"));
    const result = await getBackendHealth(config);
    expect(result.error).toBe("NETWORK_ERROR");
    expect(JSON.stringify(result)).not.toContain("private upstream");
  });
  it("TC-005 bounds reading the body after headers arrive", async () => {
    mockFetch().mockImplementation(async (_, init) => {
      const body = new ReadableStream({
        start(controller) {
          init?.signal?.addEventListener("abort", () =>
            controller.error(init.signal?.reason),
          );
        },
      });
      return new Response(body, {
        headers: { "Content-Type": "application/json" },
      });
    });
    expect(await getBackendHealth({ ...config, timeoutMs: 15 })).toMatchObject({
      error: "TIMEOUT",
      httpStatus: 200,
    });
  });
  it("TC-006 rejects malformed JSON and HTML", async () => {
    const request = mockFetch();
    for (const mime of ["application/json", "text/html"]) {
      request.mockResolvedValueOnce(
        new Response("<html>", { headers: { "Content-Type": mime } }),
      );
      expect((await getBackendHealth(config)).error).toBe("INVALID_RESPONSE");
    }
  });
  it("TC-007 rejects missing fields, unknown states and mismatched HTTP status", async () => {
    const request = mockFetch();
    for (const [body, status] of [
      [{}, 200],
      [{ ...ready, status: "maybe" }, 200],
      [down, 200],
      [ready, 503],
      [{ ...ready, checks: down.checks }, 200],
    ] as const) {
      request.mockResolvedValueOnce(json(body, status));
      expect((await getBackendReadiness(config)).error).toBe(
        "INVALID_RESPONSE",
      );
    }
    request.mockResolvedValueOnce(json({}, 502));
    expect((await getBackendReadiness(config)).error).toBe("HTTP_ERROR");
  });
  it("TC-008 reads request IDs case-insensitively", async () => {
    mockFetch().mockResolvedValue(json(health, 200, { "X-Request-ID": id }));
    expect((await getBackendHealth(config)).requestId).toBe(id);
  });
  it("TC-009 treats missing or malformed request IDs as absent", async () => {
    const request = mockFetch();
    for (const headers of [undefined, { "X-Request-ID": "bad" }]) {
      request.mockResolvedValueOnce(json(health, 200, headers));
      expect(await getBackendHealth(config)).toMatchObject({
        data: health,
        requestId: null,
      });
    }
  });
  it("TC-010 validates runtime configuration before fetching", async () => {
    const request = mockFetch();
    expect(getConfig({})).toEqual({
      origin: "http://127.0.0.1:8000",
      timeoutMs: 8000,
    });
    for (const url of [
      "",
      "ftp://host",
      "http://*.internal",
      "http://api..internal",
      "http://-node",
      "http://user:pass@host",
      "https://host?",
      "https://host/#",
      "https://host/api/v1",
    ]) {
      expect(getConfig({ API_BASE_URL: url })).toBeNull();
    }
    expect(getConfig({ API_BASE_URL: "http://[::1]:8000/" })?.origin).toBe(
      "http://[::1]:8000",
    );
    for (const timeout of ["0", "-1", "60001", "1.2", "NaN", ""]) {
      expect(getConfig({ API_REQUEST_TIMEOUT_MS: timeout })).toBeNull();
    }
    expect((await getBackendHealth(null)).error).toBe("CONFIGURATION_ERROR");
    expect(request).not.toHaveBeenCalled();
  });
  it("TC-011 uses only the configured origin and two fixed routes", async () => {
    const request = mockFetch()
      .mockResolvedValueOnce(json(health))
      .mockResolvedValueOnce(json(ready));
    await GET();
    expect(request.mock.calls.map((call) => call[0])).toEqual([
      config.origin + "/api/v1/health",
      config.origin + "/api/v1/ready",
    ]);
    expect(
      request.mock.calls.every((call) => call[1]?.redirect === "manual"),
    ).toBe(true);
  });
});
describe("System status route", () => {
  it("TC-012 maps two successful responses to operational", async () => {
    mockFetch()
      .mockResolvedValueOnce(json(health))
      .mockResolvedValueOnce(json(ready));
    expect(await getSystemStatus()).toMatchObject({
      overallStatus: "operational",
      database: { status: "operational" },
    });
  });
  it("TC-013 reports database degradation separately from liveness", async () => {
    mockFetch()
      .mockResolvedValueOnce(json(health))
      .mockResolvedValueOnce(json(down, 503));
    expect(await getSystemStatus()).toMatchObject({
      overallStatus: "degraded",
      backend: { status: "operational" },
      database: { status: "degraded" },
      readiness: { httpStatus: 503 },
    });
  });
  it("keeps database unknown when application startup is incomplete", async () => {
    const startup = {
      status: "not_ready",
      checks: { application: "not_ready", database: "not_ready" },
    };
    mockFetch()
      .mockResolvedValueOnce(json(health))
      .mockResolvedValueOnce(json(startup, 503));
    expect(await getSystemStatus()).toMatchObject({
      overallStatus: "degraded",
      database: { status: "unknown" },
    });
  });
  it("TC-014 distinguishes an unreachable API from unknown database state", async () => {
    mockFetch().mockRejectedValue(new TypeError("connection"));
    expect(await getSystemStatus()).toMatchObject({
      overallStatus: "unavailable",
      backend: { status: "unavailable" },
      database: { status: "unknown" },
    });
  });
  it("TC-015 preserves either successful probe on partial failure", async () => {
    const request = mockFetch()
      .mockResolvedValueOnce(json(health))
      .mockRejectedValueOnce(new Error());
    expect(await getSystemStatus()).toMatchObject({
      overallStatus: "degraded",
      backend: { status: "operational" },
      database: { status: "unknown" },
    });
    request
      .mockRejectedValueOnce(new Error())
      .mockResolvedValueOnce(json(ready));
    expect(await getSystemStatus()).toMatchObject({
      overallStatus: "degraded",
      backend: { status: "degraded" },
      database: { status: "operational" },
    });
  });
  it("TC-016 rejects unconfirmed contracts", async () => {
    mockFetch().mockImplementation(async () => json({ status: "online" }));
    expect(await getSystemStatus()).toMatchObject({
      overallStatus: "unknown",
      database: { status: "unknown" },
    });
  });
  it("TC-017 timestamps the completed check", async () => {
    const start = Date.now();
    mockFetch().mockRejectedValue(new Error());
    const now = Date.parse((await getSystemStatus()).checkedAt);
    expect(now).toBeGreaterThanOrEqual(start);
    expect(now).toBeLessThanOrEqual(Date.now());
  });
  it("TC-018 issues fresh requests and disables HTTP caching on each snapshot", async () => {
    const request = mockFetch().mockRejectedValue(new Error());
    for (let i = 0; i < 2; i++)
      expect((await GET()).headers.get("cache-control")).toBe("no-store");
    expect(request).toHaveBeenCalledTimes(4);
    expect(
      request.mock.calls.every((call) => call[1]?.cache === "no-store"),
    ).toBe(true);
  });
});
