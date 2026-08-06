import type { OAuthHelpers } from "@cloudflare/workers-oauth-provider";
import type { Env } from "../env.js";
import { parseAccessMode } from "../clockify/access-mode.js";
import { parseRegion } from "../clockify/regions.js";
import type { AuthRequest } from "@cloudflare/workers-oauth-provider";
import { renderConsentPage, renderHomePage, renderRedirectPage } from "./pages.js";
import { decodeOAuthState } from "./pages.js";
import type { ClockifyAuthProps } from "./types.js";
import { escapeHtml } from "./types.js";

export type AuthEnv = Env & { OAUTH_PROVIDER: OAuthHelpers };

function renderErrorPage(message: string): Response {
  const safe = escapeHtml(message);
  return new Response(
    `<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px"><h1>Authorization failed</h1><p>${safe}</p><p><a href="javascript:history.back()">Go back</a></p></body></html>`,
    {
      status: 400,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    },
  );
}

function discoveryJson(env: Env): Response {
  return Response.json({
    name: "clockify-mcp",
    description:
      "Cloudflare Workers companion for Clockify over Streamable HTTP MCP (OAuth + BYO API key).",
    transport: "streamable-http",
    mcp: "/mcp",
    auth: {
      oauth: {
        authorize: "/authorize",
        token: "/oauth/token",
        register: "/oauth/register",
        metadata: "/.well-known/oauth-authorization-server",
      },
      byo: [
        "Authorization: Bearer <CLOCKIFY_API_KEY>",
        "(desktop) same Bearer via mcp-remote — provider resolveExternalToken",
      ],
      optional: [
        "X-Clockify-Access-Mode: read | time-tracking | full",
        "X-Clockify-Region: global | euc1 | use2 | euw2 | apse2",
        "X-Clockify-Workspace-Id",
      ],
    },
    defaults: {
      accessMode: env.DEFAULT_ACCESS_MODE ?? "read",
      region: env.DEFAULT_REGION ?? "global",
    },
    note: "OAuth consent stores your Clockify API key on the grant. Desktop clients may still send the Clockify key as Bearer.",
  });
}

/** Exported for unit tests — builds props from the consent form fields. */
export function propsFromConsentForm(
  form: FormData,
  defaults: { accessMode?: string; region?: string },
): ClockifyAuthProps | null {
  const apiKey = String(form.get("api_key") || "").trim();
  if (!apiKey) return null;
  return {
    apiKey,
    accessMode: parseAccessMode(
      String(form.get("access_mode") || defaults.accessMode || "read"),
    ),
    region: parseRegion(String(form.get("region") || defaults.region || "global")),
    workspaceId: String(form.get("workspace_id") || "").trim() || undefined,
  };
}

export async function handleAuthRequest(
  request: Request,
  env: AuthEnv,
): Promise<Response> {
  const url = new URL(request.url);

  if (request.method === "GET" && url.pathname === "/") {
    const accept = request.headers.get("Accept") || "";
    if (accept.includes("application/json") && !accept.includes("text/html")) {
      return discoveryJson(env);
    }
    return renderHomePage();
  }

  if (url.pathname === "/authorize") {
    if (request.method === "GET") {
      const oauthReqInfo = await env.OAUTH_PROVIDER.parseAuthRequest(request);
      const clientInfo = await env.OAUTH_PROVIDER.lookupClient(
        oauthReqInfo.clientId,
      );
      if (!clientInfo) {
        return new Response("Invalid client_id", { status: 400 });
      }
      return renderConsentPage(oauthReqInfo, clientInfo);
    }

    if (request.method === "POST") {
      const form = await request.formData();
      const state = form.get("state");
      if (!state || typeof state !== "string") {
        return renderErrorPage("Missing state");
      }

      const props = propsFromConsentForm(form, {
        accessMode: env.DEFAULT_ACCESS_MODE,
        region: env.DEFAULT_REGION,
      });
      if (!props) {
        return renderErrorPage("Clockify API key is required");
      }

      let oauthReqInfo: AuthRequest;
      try {
        oauthReqInfo = decodeOAuthState<AuthRequest>(state);
      } catch {
        return renderErrorPage("Invalid state — restart the connection from Claude.");
      }

      try {
        const client = await env.OAUTH_PROVIDER.lookupClient(
          oauthReqInfo.clientId,
        );
        const { redirectTo } = await env.OAUTH_PROVIDER.completeAuthorization({
          request: oauthReqInfo,
          userId: `clockify:${await hashPrefix(props.apiKey)}`,
          metadata: {
            label: "Clockify MCP",
            clientName: client?.clientName || "MCP Client",
          },
          scope: oauthReqInfo.scope,
          props,
        });
        // HTML + JS redirect: Claude WebViews often ignore bare HTTP 302.
        return renderRedirectPage(redirectTo);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Authorization failed";
        return renderErrorPage(message);
      }
    }
  }

  return new Response("Not Found", { status: 404 });
}

async function hashPrefix(apiKey: string): Promise<string> {
  const data = new TextEncoder().encode(apiKey);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)]
    .slice(0, 8)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
