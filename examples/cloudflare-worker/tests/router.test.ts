import { describe, expect, it, vi } from "vitest";

vi.mock("agents/mcp/server", () => ({
  createMcpHandler: () =>
    async () =>
      new Response("mcp-ok", { status: 200 }),
}));

import { handleRequest } from "../src/http/router.js";

const env = {
  DEFAULT_ACCESS_MODE: "read",
  DEFAULT_REGION: "global",
};

describe("handleRequest", () => {
  it("returns discovery JSON on GET /", async () => {
    const res = await handleRequest(
      new Request("https://example.test/", { method: "GET" }),
      env,
    );
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({
      name: "clockify-mcp",
      transport: "streamable-http",
      mcp: "/mcp",
    });
    // Discovery must not embed a real secret — only document how to send one.
    expect(JSON.stringify(body)).not.toMatch(/Bearer\s+[A-Za-z0-9_-]{8,}/);
  });

  it("returns 401 missing_api_key for POST /mcp without credentials", async () => {
    const res = await handleRequest(
      new Request("https://example.test/mcp", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
      }),
      env,
    );
    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ error: "missing_api_key" });
  });

  it("returns 404 for unknown paths", async () => {
    const res = await handleRequest(
      new Request("https://example.test/health", { method: "GET" }),
      env,
    );
    expect(res.status).toBe(404);
  });

  it("forwards authenticated /mcp requests to the MCP handler", async () => {
    const res = await handleRequest(
      new Request("https://example.test/mcp", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          Authorization: "Bearer test-key",
        },
        body: "{}",
      }),
      env,
    );
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("mcp-ok");
  });
});
