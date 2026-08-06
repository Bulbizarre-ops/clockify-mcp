# Clockify MCP — Cloudflare Worker (example)

Streamable HTTP MCP companion for [clockify-mcp](https://github.com/tracegazer/clockify-mcp) on **Cloudflare Workers**.

This is **not** the Python server running in a Worker. It is a TypeScript example that speaks the same tool dialect (names + access modes) over remote HTTP with a **bring-your-own Clockify API key** per request.

## Quick start

```bash
cd examples/cloudflare-worker
npm ci
npm test
npm run typecheck
npm run dev          # wrangler dev → http://127.0.0.1:8787/mcp
npx wrangler deploy  # optional
```

## Auth

### OAuth 2.1 (Claude web / mobile custom connector)

1. Add custom connector URL: `https://<your-worker>.workers.dev/mcp`
2. Claude opens `/authorize`
3. Paste your **Clockify API key** (+ access mode / region)
4. Approve — the key is stored on the OAuth grant (encrypted by the provider)

### BYO API key (Claude Desktop / mcp-remote)

Send on every `/mcp` request:

- `Authorization: Bearer <CLOCKIFY_API_KEY>`

Optional headers: `X-Clockify-Access-Mode`, `X-Clockify-Region`, `X-Clockify-Workspace-Id`.

The Worker never logs the API key. `GET /` returns discovery JSON (use `Accept: application/json`).

### Access modes (aligned with the Python server)

| Mode | Reads | Writes |
|------|-------|--------|
| `read` (default) | All wave-1 reads | none |
| `time-tracking` | same | `create_time_entry`, `update_time_entry`, `delete_time_entry` |
| `full` | same | + `stop_running_timer` + CRUD clients/projects/tasks/tags |

`stop_running_timer` is **full-only**, matching the Python server.

## Wave 1 tools (32)

See [WAVES.md](./WAVES.md).

## Architecture

```
Client  --OAuth or Bearer Clockify key-->  Worker (OAuthProvider)
                                           ├─ /authorize consent (paste Clockify key → grant props)
                                           ├─ resolveExternalToken (desktop BYO)
                                           ├─ createMcpHandler(factory)  # agents/mcp/server + MCP SDK v2
                                           └─ Clockify REST / Reports API
```

Requires Wrangler KV binding `OAUTH_KV` (see `wrangler.toml`).

## Contribute upstream

See [FORK.md](./FORK.md). Open a PR that adds only `examples/cloudflare-worker/` (plus a short README link) — do not rewrite the Python runtime.

## Security notes

- `full` can create/update/delete Clockify data — treat it carefully.
- Never log API keys.
- Before public multi-tenant hosting: rate limits, tighter CORS, monitoring.
- For OAuth-style MCP auth instead of BYO Clockify key, see Cloudflare’s `mcp-worker-authenticated` example.
