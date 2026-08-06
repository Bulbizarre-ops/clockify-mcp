import type { OAuthHelpers } from "@cloudflare/workers-oauth-provider";
import { OAuthProvider } from "@cloudflare/workers-oauth-provider";
import { parseAccessMode } from "./clockify/access-mode.js";
import { parseClockifyPlan } from "./clockify/plan.js";
import { parseRegion } from "./clockify/regions.js";
import type { Env } from "./env.js";
import { mcpApiHandler } from "./mcp-api.js";
import { handleAuthRequest } from "./oauth/auth-handler.js";
import type { ClockifyAuthProps } from "./oauth/types.js";

type WorkerEnv = Env & { OAUTH_PROVIDER: OAuthHelpers };

/**
 * Resolve a raw Clockify API key sent as Bearer (desktop BYO),
 * when it is not a provider-issued OAuth access token.
 */
async function resolveExternalToken({
  token,
  request,
  env,
}: {
  token: string;
  request: Request;
  env: WorkerEnv;
}): Promise<{ props: ClockifyAuthProps } | null> {
  const apiKey = token.trim();
  if (!apiKey || apiKey.length < 8) return null;

  const props: ClockifyAuthProps = {
    apiKey,
    accessMode: parseAccessMode(
      request.headers.get("X-Clockify-Access-Mode") ?? env.DEFAULT_ACCESS_MODE,
    ),
    region: parseRegion(
      request.headers.get("X-Clockify-Region") ?? env.DEFAULT_REGION,
    ),
    plan: parseClockifyPlan(
      request.headers.get("X-Clockify-Plan") ?? env.DEFAULT_PLAN,
    ),
    workspaceId:
      request.headers.get("X-Clockify-Workspace-Id")?.trim() || undefined,
  };
  return { props };
}

export default new OAuthProvider<WorkerEnv>({
  apiRoute: "/mcp",
  apiHandler: mcpApiHandler,
  defaultHandler: {
    async fetch(request, env, _ctx) {
      return handleAuthRequest(request, env);
    },
  },
  authorizeEndpoint: "/authorize",
  tokenEndpoint: "/oauth/token",
  clientRegistrationEndpoint: "/oauth/register",
  // Pin RFC 8707 resource / aud to the MCP endpoint Claude registers.
  resourceMetadata: {
    resource: "https://clockify-mcp.aymeric-veyron.workers.dev/mcp",
    resource_name: "Clockify MCP",
    scopes_supported: ["read", "time-tracking", "full"],
  },
  resolveExternalToken,
});