import { afterEach, describe, expect, it, vi } from "vitest";
import { ClockifyAPIError, ClockifyClient } from "../src/clockify/client.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ClockifyClient", () => {
  it("sends X-Api-Key and GETs against the regular host", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({ id: "u1", name: "Ada" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new ClockifyClient({
      apiKey: "secret",
      region: "global",
    });
    const body = await client.get("user");
    expect(body).toEqual({ id: "u1", name: "Ada" });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.clockify.me/api/v1/user",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ "X-Api-Key": "secret" }),
      }),
    );
  });

  it("POSTs JSON to the reports host via report()", async () => {
    const fetchMock = vi.fn(async () => Response.json({ totals: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const client = new ClockifyClient({ apiKey: "k", region: "euc1" });
    await client.report("workspaces/ws/reports/summary", { dateRangeStart: "a" });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://euc1.clockify.me/report/v1/workspaces/ws/reports/summary",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("raises ClockifyAPIError with status on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 401 })),
    );
    const client = new ClockifyClient({ apiKey: "bad", region: "global" });
    await expect(client.get("user")).rejects.toBeInstanceOf(ClockifyAPIError);
    await expect(client.get("user")).rejects.toMatchObject({
      statusCode: 401,
      category: "AUTH",
    });
  });

  it("classifies 403 as ACCESS_DENIED", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ message: "Access Denied" }, { status: 403 }),
      ),
    );
    const client = new ClockifyClient({ apiKey: "k", region: "global" });
    await expect(client.get("user")).rejects.toMatchObject({
      statusCode: 403,
      category: "ACCESS_DENIED",
      hint: expect.stringContaining("Workspace Settings"),
    });
  });

  it("classifies subscription messages as PLAN_REQUIRED", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ message: "No active subscription" }, { status: 400 }),
      ),
    );
    const client = new ClockifyClient({ apiKey: "k", region: "global" });
    await expect(client.get("user")).rejects.toMatchObject({
      category: "PLAN_REQUIRED",
      hint: expect.stringContaining("plan"),
    });
  });

  it("calls globalThis.fetch through a wrapper instead of an unbound reference", async () => {
    const fetchMock = vi.fn(async () => Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    // Default path must not store bare `fetch` (Workers Illegal invocation).
    const client = new ClockifyClient({ apiKey: "k", region: "global" });
    await expect(client.get("user")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.clockify.me/api/v1/user",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
