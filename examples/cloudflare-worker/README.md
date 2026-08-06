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

## Auth (BYO key)

Every `POST /mcp` request must include one of:

- `Authorization: Bearer <CLOCKIFY_API_KEY>`
- `X-Api-Key: <CLOCKIFY_API_KEY>`

Optional headers:

| Header | Values | Effect |
|--------|--------|--------|
| `X-Clockify-Access-Mode` | `read` \| `time-tracking` \| `full` | Which tools are registered (default: Worker `DEFAULT_ACCESS_MODE` / `read`) |
| `X-Clockify-Region` | `global` \| `euc1` \| `use2` \| `euw2` \| `apse2` | Clockify API hosts |
| `X-Clockify-Workspace-Id` | opaque id | Fallback `workspace_id` for tools |

The Worker **never stores** the API key. `GET /` returns discovery JSON without secrets. Missing key on `/mcp` → `401 {"error":"missing_api_key"}`.

### Access modes (aligned with the Python server)

| Mode | Reads | Writes |
|------|-------|--------|
| `read` (default) | All wave-1 reads | none |
| `time-tracking` | same | `create_time_entry`, `update_time_entry`, `delete_time_entry` |
| `full` | same | + `stop_running_timer` + CRUD clients/projects/tasks/tags |

`stop_running_timer` is **full-only**, matching the Python server (time-tracking can start a timer via `create_time_entry` without `end`; stop with `update_time_entry` or use `full`).

## Wave 1 tools (32)

See [WAVES.md](./WAVES.md).

## Architecture

```
Client  --POST /mcp + API key-->  Worker
                                  ├─ extractClockifyCredentials
                                  ├─ access mode filter
                                  ├─ createMcpHandler(factory)  # agents/mcp/server + MCP SDK v2
                                  └─ Clockify REST / Reports API
```

## Contribute upstream

See [FORK.md](./FORK.md). Open a PR that adds only `examples/cloudflare-worker/` (plus a short README link) — do not rewrite the Python runtime.

## Security notes

- `full` can create/update/delete Clockify data — treat it carefully.
- Never log API keys.
- Before public multi-tenant hosting: rate limits, tighter CORS, monitoring.
- For OAuth-style MCP auth instead of BYO Clockify key, see Cloudflare’s `mcp-worker-authenticated` example.
