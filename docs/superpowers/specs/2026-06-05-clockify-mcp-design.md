# Clockify MCP Server — Design

**Date:** 2026-06-05
**Status:** Approved (pending spec review)
**Author:** Alan (tracegazer)

## 1. Overview

Open-source [Model Context Protocol](https://modelcontextprotocol.io) server for
**Clockify** (time tracking). Exposes Clockify REST API operations as MCP tools so
AI assistants can query and manage workspaces, projects, tasks, time entries,
reports, time off, expenses, and more through natural language.

Built to mirror the proven architecture of `invgate-service-desk-mcp`: Python +
FastMCP, modular per-domain, read-only by default with write tools behind explicit
opt-in, optional OpenTelemetry telemetry.

- **Package / repo name:** `clockify-mcp` (module `clockify_mcp`, script `clockify-mcp`)
- **Scope:** broad coverage (~90+ tools across ~17 domains)
- **Distribution:** PyPI, runnable via `uvx clockify-mcp`

## 2. Clockify API — key facts

- **Auth:** header `X-Api-Key` (single API key; no OAuth). Subdomain workspaces
  need a workspace-specific key generated in Profile Settings.
- **Two hosts:**
  - Regular API: `https://api.clockify.me/api/v1`
  - **Reports API (separate host):** `https://reports.api.clockify.me/v1`
- **Regional prefixes:** `euc1` (EU), `use2` (USA), `euw2` (UK), `apse2` (AU);
  subdomain workspaces use `https://{subdomain}.clockify.me/...`. Configurable.
- **Rate limit:** ~50 req/s. Client retries `429 Too many requests` with light
  exponential backoff (small fixed number of attempts, honoring `Retry-After` when
  present); surfaces a clear error if retries are exhausted.
- **Pagination:** `page` (1-indexed) + `pageSize` query params; response carries a
  `Last-Page` header (`true`/`false`). No collection envelopes (unlike InvGate).
- **Workspace-centric:** almost every endpoint is under
  `/workspaces/{workspaceId}/...`.

## 3. Architecture

Same mold as `invgate-service-desk-mcp`. Each domain module owns its tools and
registers them via `register(mcp, client)`, keeping the server layer thin.

```
src/clockify_mcp/
  __init__.py
  config.py        # env > TOML; api_key, region/base_url, default_workspace_id,
                   # enable_writes, telemetry_*
  client.py        # httpx async; dual-host (regular + reports); X-Api-Key header;
                   # secret sanitization + error truncation; JSON bodies
  pagination.py    # page/pageSize helpers + Last-Page handling; optional fetch_all()
  telemetry.py     # ported from invgate (OTel facade)
  _otel.py         # ported from invgate (OTel SDK wiring)
  server.py        # build_server(): registers all enabled domains; INSTRUCTIONS
  domains/
    __init__.py
    workspaces.py   users.py   groups.py
    clients.py      projects.py  tasks.py   tags.py
    time_entries.py reports.py
    time_off.py     holidays.py
    expenses.py     approvals.py
    custom_fields.py scheduling.py invoices.py webhooks.py
tests/              # pytest + pytest-asyncio + respx; test_live_smoke.py (gated)
docs/
base_conocimiento/  # Clockify API reference notes (endpoint map / OpenAPI extract)
config.toml.example
pyproject.toml      # hatchling; deps mcp + httpx; extras: telemetry, dev
.github/workflows/ci.yml  # uv + ruff + pytest on 3.12/3.13 (ported)
README.md  LICENSE (MIT)  CLAUDE.md  .gitignore
```

### Differences vs invgate (justified by Clockify's API)

1. **Dual-host client.** `client.get/post/put/delete(...)` hit `api.clockify.me`;
   `client.report(path, body)` hits `reports.api.clockify.me`. The active host base
   (regional prefix / subdomain) comes from config.
2. **Header auth** `X-Api-Key` instead of HTTP Basic.
3. **JSON request bodies** (Clockify writes use JSON, not form-encoded).
4. **`pagination.py` replaces `normalize.py`.** Clockify paginates with
   `page`/`pageSize` + `Last-Page` header rather than InvGate's keyed envelopes.
   List tools expose `page`/`page_size`; an optional `fetch_all()` helper auto-
   follows pages up to a safety cap (to avoid flooding the LLM).

### Client responsibilities (unchanged from invgate)

- Async `httpx.AsyncClient`, 30s timeout.
- Sanitize secrets (the API key) out of any surfaced error text; cap error length.
- `writes_enabled` property gates write-tool registration.
- Light backoff retry on `429` (bounded attempts, honor `Retry-After`).

## 4. Workspace resolution (discovery pattern)

- `default_workspace_id` optional in config.
- Discovery tools always registered: `get_current_user`, `list_workspaces`.
- Every workspace-scoped tool accepts an **optional** `workspace_id`:
  - if omitted → use `default_workspace_id`;
  - if neither present → raise a clear error instructing the agent to call
    `list_workspaces` first.
- `server.INSTRUCTIONS` guides the agent: resolve workspace via `list_workspaces`,
  users via `list_users`, projects via `list_projects` before filtering/creating;
  when a name match is ambiguous, present all options and let the user choose
  (same disambiguation rule as invgate).

## 5. Writes opt-in

- Read-only by default. `CLOCKIFY_ENABLE_WRITES=true` (or `enable_writes` in TOML)
  registers write tools via the `if client.writes_enabled: _register_writes(...)`
  pattern.
- Destructive verbs (`delete_*`) carry explicit "irreversible" warnings in
  docstrings.
- **Live write verification is in scope:** smoke tests will exercise real
  create/update/delete against the user's actual workspace (gated by env), since
  the user authorized live create tests.

## 6. Telemetry

- Port `telemetry.py` / `_otel.py` from invgate verbatim (renamed service).
- Opt-in via `CLOCKIFY_TELEMETRY=true`. Per-call client spans, low-cardinality
  metrics, logs. Dynatrace integration via standard OTel env vars
  (`OTEL_EXPORTER_OTLP_ENDPOINT`, etc.). Optional `telemetry` extra in pyproject.

## 7. Domain & tool inventory (~90+ tools)

| Domain | Read tools | Write tools (opt-in) |
|---|---|---|
| **workspaces** | get_current_user, list_workspaces, get_workspace | — |
| **users** | list_users (filter), get_user_member_profile, find_user_team_manager | update_member_profile, set_user_custom_field |
| **groups** | list_user_groups | create/update/delete_user_group |
| **clients** | list_clients, get_client | create/update/delete_client |
| **projects** | list_projects, get_project | create/update/delete_project |
| **tasks** | list_tasks, get_task | create/update/delete_task |
| **tags** | list_tags, get_tag | create/update/delete_tag |
| **time_entries** | list_time_entries (by user), get_time_entry | create/update/delete/duplicate_time_entry, bulk |
| **reports** | generate_detailed_report, generate_summary_report, generate_weekly_report | — |
| **time_off** | list_policies, get_policy, list_balances, list_time_off_requests | create_policy, create/approve/reject/withdraw_request |
| **holidays** | list_holidays, list_holidays_in_period | create/update/delete_holiday |
| **expenses** | list_expenses, get_expense, list_categories, download_receipt | create/update/delete_expense, create/update/delete/archive_category |
| **approvals** | list_approval_requests | submit/update_approval_request |
| **custom_fields** | list_workspace_custom_fields, list_project_custom_fields | create/update/delete (ws), update/remove (project) |
| **scheduling** | list_assignments, project_totals | create_recurring/update/delete_assignment |
| **invoices** | list_invoices, get_invoice, get_payments | create/update/delete/duplicate_invoice |
| **webhooks** | list_webhooks, get_webhook, get_webhook_logs | create/update/delete_webhook, generate_token |

Final counts settle during implementation; this is the target surface.

## 8. Implementation phases

Each phase: read tools first, write tools (opt-in) after, per-domain unit tests
(respx), and a live smoke check against the real API key. Read tools land before
their writes so the server is always shippable.

| Phase | Contents | Type |
|---|---|---|
| **0** | Scaffolding: pyproject, config, dual-host client, pagination, telemetry port, server skeleton, CI, test harness | infra |
| **1** | Discovery + base read: `workspaces`, `users`, `groups` | read |
| **2** | Core entities read: `projects`, `tasks`, `clients`, `tags` | read |
| **3** | `time_entries` (read) + `reports` (detailed/summary/weekly) | read |
| **4** | Core writes opt-in: time entries, projects, tasks, clients, tags (+ live create tests) | write |
| **5** | `time_off` + `holidays` (read + write) | mixed |
| **6** | `expenses` + `approvals` (read + write) | mixed |
| **7** | `custom_fields`, `scheduling`, `invoices`, `webhooks` | mixed |

## 9. Configuration

`config.toml.example` (mirrors invgate):

```toml
api_key = "your-clockify-api-key"
# region = "global"            # global | euc1 | use2 | euw2 | apse2
# base_url = ""                # override for subdomain workspaces
# default_workspace_id = ""    # optional; tools fall back to this
# enable_writes = false        # true registers create/update/delete tools
# telemetry_enabled = false
# telemetry_detail = "metadata"  # metadata | ids | full
```

Env vars override TOML: `CLOCKIFY_API_KEY`, `CLOCKIFY_REGION`,
`CLOCKIFY_BASE_URL`, `CLOCKIFY_DEFAULT_WORKSPACE_ID`, `CLOCKIFY_ENABLE_WRITES`,
`CLOCKIFY_TELEMETRY`, `CLOCKIFY_TELEMETRY_DETAIL`.

## 10. Testing & distribution

- **Unit:** `pytest` + `pytest-asyncio` + `respx` mocks per domain.
- **Live smoke:** `test_live_smoke.py`, gated by env (real `CLOCKIFY_API_KEY` +
  test workspace), including authorized create/update/delete round-trips.
- **CI:** GitHub Actions `ci.yml` ported — `uv sync --extra dev`, `ruff check`,
  `pytest` on Python 3.12 & 3.13.
- **Build:** `hatchling`; publish to PyPI as `clockify-mcp`; `uvx clockify-mcp`.
- **Docs:** README with domain/tool table, `config.toml.example`, MIT LICENSE,
  CLAUDE.md, `base_conocimiento/` API reference.

## 11. Out of scope (v1)

- No webhook *receiver* server (only Clockify webhook management tools).
- No automatic full-history export beyond paginated reads + reports.
- No caching layer; each tool call hits the API live.
