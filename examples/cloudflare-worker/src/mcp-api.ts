import { createMcpHandler } from "agents/mcp/server";
import type { OAuthHelpers } from "@cloudflare/workers-oauth-provider";
import { parseAccessMode } from "./clockify/access-mode.js";
import { ClockifyClient } from "./clockify/client.js";
import { parseRegion } from "./clockify/regions.js";
import type { Env } from "./env.js";
import type { ClockifyAuthProps } from "./oauth/types.js";
import { createClockifyMcpServer } from "./server.js";

type WorkerEnv = Env & { OAUTH_PROVIDER?: OAuthHelpers };

function propsFromContext(ctx: ExecutionContext): ClockifyAuthProps | null {
  const props = (ctx as ExecutionContext & { props?: ClockifyAuthProps }).props;
  if (!props?.apiKey) return null;
  return {
    apiKey: props.apiKey,
    accessMode: parseAccessMode(props.accessMode),
    region: parseRegion(props.region),
    workspaceId: props.workspaceId || undefined,
  };
}

/**
 * Protected /mcp handler — credentials come from OAuth grant props
 * (or resolveExternalToken for BYO Clockify API key Bearer).
 */
export const mcpApiHandler = {
  async fetch(
    request: Request,
    env: WorkerEnv,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const props = propsFromContext(ctx);
    if (!props) {
      return Response.json(
        { error: "missing_clockify_credentials" },
        { status: 401 },
      );
    }

    const client = new ClockifyClient({
      apiKey: props.apiKey,
      region: props.region,
      defaultWorkspaceId: props.workspaceId,
    });

    return createMcpHandler(
      () => createClockifyMcpServer(client, props.accessMode),
      {
        route: "/mcp",
        corsOptions: {
          origin: "*",
          methods: "GET, POST, DELETE, OPTIONS",
          headers:
            "Content-Type, Accept, Authorization, X-Api-Key, X-Clockify-Access-Mode, X-Clockify-Region, X-Clockify-Workspace-Id, mcp-session-id",
          exposeHeaders: "mcp-session-id",
        },
        allowedOriginHostnames: "*",
      },
    )(request, env, ctx);
  },
};
