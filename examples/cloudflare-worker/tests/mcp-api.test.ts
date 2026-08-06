import { describe, expect, it, vi } from "vitest";

vi.mock("agents/mcp/server", () => ({
  createMcpHandler: () =>
    async () =>
      new Response("mcp-ok", { status: 200 }),
}));

import { mcpApiHandler } from "../src/mcp-api.js";

const env = {
  DEFAULT_ACCESS_MODE: "read",
  DEFAULT_REGION: "global",
  DEFAULT_PLAN: "free",
  OAUTH_KV: {} as KVNamespace,
};

describe("mcpApiHandler", () => {
  it("returns 401 when ctx.props has no apiKey", async () => {
    const res = await mcpApiHandler.fetch!(
      new Request("https://example.test/mcp", { method: "POST" }),
      env,
      { props: {} } as unknown as ExecutionContext,
    );
    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({
      error: "missing_clockify_credentials",
    });
  });

  it("serves MCP when props include a Clockify apiKey", async () => {
    const res = await mcpApiHandler.fetch!(
      new Request("https://example.test/mcp", { method: "POST" }),
      env,
      {
        props: {
          apiKey: "test-key-12345678",
          accessMode: "read",
          region: "global",
        },
      } as unknown as ExecutionContext,
    );
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("mcp-ok");
  });
});
