// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatusPanel } from "@/features/system-status/panel";
import type { SystemStatusResponse } from "@/features/system-status/contract";

afterEach(cleanup);
const endpoint = {
  status: "operational",
  httpStatus: 200,
  requestId: "b794fe41-a07e-43a2-97c7-26539122f194",
  durationMs: 3,
  error: null,
} as const;
const snapshot: SystemStatusResponse = {
  overallStatus: "operational",
  checkedAt: "2026-09-01T00:00:01.000Z",
  backend: endpoint,
  database: { status: "operational" },
  readiness: { ...endpoint, requestId: "11eb8bea-e284-4b8f-9b92-56371d7895f1" },
};

function setup() {
  const request = vi.fn<typeof fetch>();
  vi.stubGlobal("fetch", request);
  return request;
}
function mount() {
  return render(<StatusPanel projectInfo={null} />);
}
function button() {
  return screen.getByRole("button", { name: "Refresh Status" });
}
const pending = () => new Promise<Response>(() => {});

it("TC-019 shows initial loading while checking", () => {
  setup().mockImplementation(pending);
  mount();
  expect(screen.getByRole("button", { name: "Checking…" })).toBeDisabled();
  expect(screen.getAllByText("Checking")).toHaveLength(4);
});
it("TC-020 displays all confirmed service statuses", async () => {
  setup().mockResolvedValue(Response.json(snapshot));
  mount();
  expect(await screen.findAllByText("Operational")).toHaveLength(4);
  expect(screen.getByText("4 checks")).toBeVisible();
});
it("TC-021 displays the database warning and HTTP 503", async () => {
  setup().mockResolvedValue(
    Response.json({
      ...snapshot,
      overallStatus: "degraded",
      database: { status: "degraded" },
      readiness: { ...endpoint, status: "degraded", httpStatus: 503 },
    }),
  );
  mount();
  expect(await screen.findByText("System degraded")).toBeVisible();
  expect(screen.getAllByText("Not ready")).toHaveLength(2);
  expect(screen.getByText("HTTP 503")).toBeVisible();
});
it("TC-022 exposes a retry control after a network error", async () => {
  setup().mockRejectedValue(new Error("private address"));
  mount();
  expect(await screen.findByText("Status check unavailable")).toBeVisible();
  expect(button()).toBeEnabled();
  expect(screen.queryByText("private address")).toBeNull();
});
it("TC-023 refreshes from the same origin and updates time", async () => {
  const request = setup()
    .mockResolvedValueOnce(Response.json(snapshot))
    .mockResolvedValueOnce(
      Response.json({ ...snapshot, checkedAt: "2026-09-01T00:02:00.000Z" }),
    );
  mount();
  await screen.findByText("00:00:01 UTC");
  await userEvent.click(button());
  expect(await screen.findByText("00:02:00 UTC")).toBeVisible();
  expect(request).toHaveBeenCalledTimes(2);
  expect(request).toHaveBeenLastCalledWith(
    "/api/system/status",
    expect.objectContaining({ cache: "no-store" }),
  );
});
it("TC-024 ignores concurrent refreshes and retains the last check while waiting", async () => {
  const request = setup()
    .mockResolvedValueOnce(Response.json(snapshot))
    .mockImplementation(pending);
  mount();
  await screen.findByText("All systems operational");
  const control = button();
  fireEvent.click(control);
  fireEvent.click(control);
  expect(control).toBeDisabled();
  expect(screen.getByText("00:00:01 UTC")).toBeVisible();
  expect(request).toHaveBeenCalledTimes(2);
});
it("TC-025 recovers on the next successful manual check", async () => {
  setup()
    .mockRejectedValueOnce(new Error())
    .mockResolvedValueOnce(Response.json(snapshot));
  mount();
  await screen.findByText("Status check unavailable");
  await userEvent.click(button());
  expect(await screen.findByText("All systems operational")).toBeVisible();
  expect(screen.queryByText("Status check unavailable")).toBeNull();
});
it("TC-026 renders the separate server request identifiers", async () => {
  setup().mockResolvedValue(Response.json(snapshot));
  mount();
  expect(await screen.findByText(endpoint.requestId)).toBeVisible();
  expect(screen.getByText(snapshot.readiness.requestId!)).toBeVisible();
});
it("TC-027 refresh is keyboard accessible", async () => {
  const request = setup().mockImplementation(async () =>
    Response.json(snapshot),
  );
  mount();
  await screen.findByText("All systems operational");
  const user = userEvent.setup();
  await user.tab();
  expect(button()).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(request).toHaveBeenCalledTimes(2);
});
it("TC-028 never reports operational for missing or invalid data", async () => {
  setup().mockResolvedValue(Response.json({ overallStatus: "operational" }));
  mount();
  expect(screen.queryByText("Operational")).toBeNull();
  await screen.findByText("Status check unavailable");
  expect(screen.getAllByText("Unknown")).toHaveLength(4);
});

it("times out a stalled BFF request, allows a retry and ignores its late result", async () => {
  vi.useFakeTimers();
  try {
    let completeFirst!: (response: Response) => void;
    const request = setup()
      .mockImplementationOnce(
        () => new Promise<Response>((resolve) => { completeFirst = resolve; }),
      )
      .mockResolvedValueOnce(Response.json(snapshot));
    mount();
    const signal = request.mock.calls[0][1]!.signal!;

    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(screen.getByRole("button", { name: "Checking…" })).toBeDisabled();
    expect(signal.aborted).toBe(false);
    await act(() => vi.advanceTimersByTimeAsync(5_000));
    expect(signal.aborted).toBe(true);
    expect(screen.getByText("Status check timed out")).toBeVisible();
    expect(button()).toBeEnabled();

    await act(async () => {
      fireEvent.click(button());
    });
    expect(screen.getByText("All systems operational")).toBeVisible();
    await act(async () => {
      completeFirst(Response.json({}));
    });
    expect(screen.getByText("All systems operational")).toBeVisible();
    expect(request).toHaveBeenCalledTimes(2);
  } finally {
    vi.useRealTimers();
  }
});

it("aborts an in-flight check and clears its deadline on unmount", () => {
  vi.useFakeTimers();
  try {
    const request = setup().mockImplementation(pending);
    const view = mount();
    const signal = request.mock.calls[0][1]!.signal!;
    view.unmount();
    expect(signal.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});
