import type { AuthRequest, ClientInfo } from "@cloudflare/workers-oauth-provider";
import { escapeHtml, isHttpUrl } from "./types.js";

export function encodeOAuthState(oauthReqInfo: unknown): string {
  const b64 = btoa(JSON.stringify(oauthReqInfo));
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function decodeOAuthState<T = unknown>(state: string): T {
  const padded = state.replace(/-/g, "+").replace(/_/g, "/");
  const pad =
    padded.length % 4 === 0 ? "" : "=".repeat(4 - (padded.length % 4));
  return JSON.parse(atob(padded + pad)) as T;
}

export function renderHomePage(): Response {
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Clockify MCP</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px; line-height: 1.5; color: #111; }
    code { background: #f4f4f5; padding: 2px 6px; border-radius: 4px; }
    .endpoint { background: #f4f4f5; padding: 10px 12px; border-radius: 6px; margin: 8px 0; font-family: ui-monospace, monospace; font-size: 14px; }
  </style>
</head>
<body>
  <h1>Clockify MCP</h1>
  <p>Streamable HTTP MCP on Cloudflare Workers with OAuth 2.1 (for Claude web/mobile) and optional bring-your-own Clockify API key Bearer (desktop).</p>
  <h2>Endpoints</h2>
  <div class="endpoint">GET / — discovery</div>
  <div class="endpoint">POST /mcp — MCP (OAuth Bearer or Clockify API key Bearer)</div>
  <div class="endpoint">/authorize — OAuth consent (paste Clockify API key)</div>
  <div class="endpoint">/oauth/token — token exchange</div>
  <div class="endpoint">/oauth/register — dynamic client registration</div>
  <div class="endpoint">/.well-known/oauth-authorization-server — metadata</div>
  <p>Claude custom connector URL: <code>/mcp</code> on this host.</p>
</body>
</html>`;
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "X-Frame-Options": "DENY",
      "Content-Security-Policy":
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'",
    },
  });
}

export function renderConsentPage(
  oauthReqInfo: AuthRequest,
  clientInfo: ClientInfo,
): Response {
  const clientName = escapeHtml(clientInfo.clientName || "MCP Client");
  const clientId = escapeHtml(clientInfo.clientId);
  const clientUri =
    clientInfo.clientUri && isHttpUrl(clientInfo.clientUri)
      ? escapeHtml(clientInfo.clientUri)
      : "";
  const scopes = escapeHtml(oauthReqInfo.scope?.join(", ") || "none");
  const state = escapeHtml(encodeOAuthState(oauthReqInfo));

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Authorize ${clientName}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 560px; margin: 40px auto; padding: 0 20px; color: #111; line-height: 1.5; }
    .card { border: 1px solid #e4e4e7; border-radius: 12px; padding: 24px; box-shadow: 0 8px 24px rgba(0,0,0,.06); }
    h1 { font-size: 1.35rem; margin: 0 0 12px; }
    label { display: block; font-weight: 600; margin: 16px 0 6px; font-size: 0.9rem; }
    input, select { width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid #d4d4d8; border-radius: 8px; font-size: 15px; }
    .hint { font-size: 0.85rem; color: #52525b; margin: 6px 0 0; }
    .meta { background: #f4f4f5; border-radius: 8px; padding: 12px; margin: 16px 0; font-size: 0.9rem; }
    .actions { display: flex; gap: 10px; margin-top: 20px; }
    button { flex: 1; padding: 12px; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; }
    .approve { background: #111; color: #fff; }
    .deny { background: #e4e4e7; color: #18181b; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Connect Clockify to ${clientName}</h1>
    <p>Paste your Clockify API key. It is stored encrypted with this OAuth grant and never logged.</p>
    <div class="meta">
      <div><strong>Client ID:</strong> ${clientId}</div>
      ${clientUri ? `<div><strong>Website:</strong> ${clientUri}</div>` : ""}
      <div><strong>Scopes:</strong> ${scopes}</div>
    </div>
    <form method="POST" action="/authorize">
      <input type="hidden" name="state" value="${state}" />
      <label for="api_key">Clockify API key</label>
      <input id="api_key" name="api_key" type="password" required autocomplete="off" placeholder="From Clockify → Profile Settings → API" />
      <p class="hint">Get it in Clockify → Profile Settings → Generate API key.</p>
      <label for="access_mode">Access mode</label>
      <select id="access_mode" name="access_mode">
        <option value="read" selected>read — list &amp; reports only</option>
        <option value="time-tracking">time-tracking — + create/update/delete time entries</option>
        <option value="full">full — + stop timer &amp; CRUD clients/projects/tasks/tags</option>
      </select>
      <label for="region">Region</label>
      <select id="region" name="region">
        <option value="global" selected>global</option>
        <option value="euc1">euc1</option>
        <option value="use2">use2</option>
        <option value="euw2">euw2</option>
        <option value="apse2">apse2</option>
      </select>
      <label for="workspace_id">Default workspace id (optional)</label>
      <input id="workspace_id" name="workspace_id" type="text" autocomplete="off" placeholder="Leave empty to pass workspace_id per tool" />
      <div class="actions">
        <button type="button" class="deny" onclick="history.back()">Cancel</button>
        <button type="submit" class="approve">Authorize</button>
      </div>
    </form>
  </div>
</body>
</html>`;

  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "X-Frame-Options": "DENY",
      "Content-Security-Policy":
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' https:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'",
    },
  });
}

/** WebView-friendly redirect after consent (bare 302 often does nothing in Claude). */
export function renderRedirectPage(redirectTo: string): Response {
  const safeUrl = escapeHtml(redirectTo);
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="refresh" content="0;url=${safeUrl}" />
  <title>Redirecting…</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 480px; margin: 48px auto; padding: 0 20px; color: #111; line-height: 1.5; }
    a { color: #111; font-weight: 600; }
  </style>
</head>
<body>
  <p>Authorization approved. Returning to the app…</p>
  <p>If nothing happens, <a id="continue" href="${safeUrl}">tap here to continue</a>.</p>
  <script>
    (function () {
      var url = ${JSON.stringify(redirectTo)};
      try { window.location.replace(url); } catch (e) { window.location.href = url; }
    })();
  </script>
</body>
</html>`;
  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      Refresh: `0;url=${redirectTo}`,
      "X-Frame-Options": "DENY",
      "Content-Security-Policy":
        "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'",
    },
  });
}
