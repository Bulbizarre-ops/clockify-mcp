import { createMcpHandler } from "agents/mcp";
import { extractClockifyCredentials } from "../auth/request-credentials.js";
import { ClockifyClient } from "../clockify/client.js";
import type { Env } from "../env.js";
import { createClockifyMcpServer } from "../server.js";

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Accept, Authorization, X-Api-Key, X-Clockify-Access-Mode, X-Clockify-Region, X-Clockify-Workspace-Id, mcp-session-id",
  "Access-Control-Expose-Headers": "mcp-session-id",
};

function withCors(response: Response): Response {
  const headers = new Headers(response.headers);
  for (const [key, value] of Object.entries(CORS_HEADERS)) {
    headers.set(key, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function discoveryResponse(): Response {
  return Response.json(
    {
      name: "clockify-mcp",
      description:
        "Cloudflare Workers companion for Clockify over Streamable HTTP MCP (BYO API key).",
      transport: "streamable-http",
      mcp: "/mcp",
      auth: {
        required: ["Authorization: Bearer <CLOCKIFY_API_KEY> | X-Api-Key"],
        optional: [
          "X-Clockify-Access-Mode: read | time-tracking | full",
          "X-Clockify-Region: global | euc1 | use2 | euw2 | apse2",
          "X-Clockify-Workspace-Id",
        ],
      },
      note: "This Worker does not store Clockify API keys. Keys are required on every /mcp request.",
    },
    { headers: CORS_HEADERS },
  );
}

export async function handleRequest(
  request: Request,
  env: Env,
  ctx?: ExecutionContext,
): Promise<Response> {
  const url = new URL(request.url);

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  if (request.method === "GET" && url.pathname === "/") {
    return discoveryResponse();
  }

  if (url.pathname === "/mcp") {
    const credentials = extractClockifyCredentials(request, {
      defaultAccessMode: env.DEFAULT_ACCESS_MODE,
      defaultRegion: env.DEFAULT_REGION,
    });
    if (!credentials) {
      return withCors(
        Response.json({ error: "missing_api_key" }, { status: 401 }),
      );
    }

    const client = new ClockifyClient({
      apiKey: credentials.apiKey,
      region: credentials.region,
      defaultWorkspaceId: credentials.workspaceId,
    });
    const server = createClockifyMcpServer(client, credentials.accessMode);
    const mcpFetch = createMcpHandler(server, { route: "/mcp" });
    const executionCtx =
      ctx ??
      ({
        waitUntil() {},
        passThroughOnException() {},
        props: {},
        exports: {},
        tracing: undefined as never,
      } as unknown as ExecutionContext);
    const response = await mcpFetch(request, env, executionCtx);
    return withCors(response);
  }

  return withCors(new Response("Not Found", { status: 404 }));
}
