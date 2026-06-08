# CLAUDE.md

## Project Overview

`clockify-mcp` is an MCP server for the [Clockify](https://clockify.me) time-tracking API. It exposes Clockify workspaces, users, groups, clients, projects, tasks, and tags as Model Context Protocol tools so any MCP-compatible client (Claude Desktop, Cursor, etc.) can query time-tracking data in natural language.

Current phase: **Phase 0–7 (v1 complete)** — 43 read tools + 59 opt-in write tools across 17 domains (Workspaces, Users, Groups, Clients, Projects, Tasks, Tags, Time entries, Reports, Time off, Holidays, Expenses, Approvals, Custom fields, Scheduling, Invoices, Webhooks). Writes (create/update/delete for clients/projects/tasks/tags/time_entries/holidays, plus time-entry duplicate/bulk, time-off policy/request create/approve/reject/withdraw, expense + expense-category create/update/delete/archive, approval submit/resubmit/update, custom-field create/update/delete and project set/remove, scheduling assignment create/update/delete/publish/copy, invoice create/update/change-status/duplicate/delete and item/payment management, and webhook create/update/delete/generate-token) register according to CLOCKIFY_ACCESS_MODE: `read` (default, none), `time-tracking` (only time-entry writes — duplicate/bulk self-scoped to the authenticated user), or `full` (all writes; CLOCKIFY_ENABLE_WRITES=true is an alias for `full`). All planned v1 domains are implemented; OpenTelemetry OTLP export (traces, metrics, logs) is implemented and opt-in via CLOCKIFY_TELEMETRY.

## Architecture

Python-based MCP server using the `mcp` package (FastMCP). Modular by domain: each `src/clockify_mcp/domains/*.py` module owns its tools and registers them via `register(mcp, client)`. The server layer (`server.py`) is thin — it builds the client + telemetry, calls each domain's `register()`, and exposes a `main()` entry point with argparse.

Key modules:

- `config.py` — loads `Config` from env vars → TOML file (env always wins); validates required fields and resolves hosts.
- `client.py` — async `ClockifyClient` wrapping `httpx.AsyncClient`; sets `X-Api-Key` header; handles 429 backoff; dual-host (regular API + Reports API). Includes `post_multipart`/`put_multipart` (multipart receipt upload) and `get_bytes` (binary download).
- `pagination.py` — `page_params(page, page_size)` builds paginated query params (hyphenated `page-size`); `is_last_page(headers)` reads the `Last-Page` response header. Pagination is caller-driven: list tools take optional `page`/`page_size` and return a single page.
- `telemetry.py` — `InstrumentedFastMCP` + no-op `Telemetry` base + `build_telemetry`; `InstrumentedFastMCP.call_tool` wraps each tool call in a span. Real OTLP export lives in `_otel.py`, imported lazily only when `CLOCKIFY_TELEMETRY=true`.
- `_otel.py` — `OTelTelemetry`: OTLP traces/metrics/logs (tool + client spans, durations, error counters), `CLOCKIFY_TELEMETRY_DETAIL` tiers (`metadata`/`ids`/`full`), API-key redaction. Ported from `mcp_invgate`.
- `bodies.py` — `drop_none()` for building JSON write request bodies.
- `domains/workspaces.py` — `get_current_user`, `list_workspaces`, `get_workspace`
- `domains/users.py` — `list_users`, `get_user_member_profile`, `find_user_team_manager`
- `domains/groups.py` — `list_user_groups`
- `domains/clients.py` — `list_clients`, `get_client` (+ create/update/delete when writes enabled)
- `domains/projects.py` — `list_projects`, `get_project` (+ create/update/delete when writes enabled)
- `domains/tasks.py` — `list_tasks`, `get_task` (+ create/update/delete when writes enabled)
- `domains/tags.py` — `list_tags`, `get_tag` (+ create/update/delete when writes enabled)
- `domains/time_entries.py` — `list_time_entries`, `get_time_entry` (+ create/update/delete/duplicate/bulk when writes enabled)
- `domains/reports.py` — `generate_detailed_report`, `generate_summary_report`, `generate_weekly_report` (POST to the Reports host via `client.report`)
- `domains/time_off.py` — `list_time_off_policies`, `get_time_off_policy`, `list_time_off_balances_by_policy`, `list_time_off_balances_by_user`, `list_time_off_requests` (+ create_policy/create/approve/reject/withdraw_request when writes enabled)
- `domains/holidays.py` — `list_holidays`, `list_holidays_in_period` (+ create/update/delete when writes enabled)
- `domains/expenses.py` — `list_expenses`, `get_expense`, `list_expense_categories`, `download_expense_receipt` (+ create/update/delete expense and create/update/delete/archive category when writes enabled; create/update use multipart with an optional receipt)
- `domains/approvals.py` — `list_approval_requests` (+ submit/submit-for-user/resubmit/update when writes enabled)
- `domains/custom_fields.py` — `list_workspace_custom_fields`, `list_project_custom_fields` (+ create/update/delete workspace field and set/remove on project when writes enabled)
- `domains/scheduling.py` — `list_scheduled_assignments`, `get_project_scheduling_totals`, `get_user_scheduling_totals` (+ create/update/delete/publish/copy assignment when writes enabled)
- `domains/invoices.py` — `list_invoices`, `get_invoice`, `get_invoice_payments` (+ create/update/change-status/duplicate/delete and item/payment management when writes enabled)
- `domains/webhooks.py` — `list_webhooks`, `get_webhook`, `get_webhook_logs` (+ create/update/delete/generate-token when writes enabled)

Read-only by default; write tools register per CLOCKIFY_ACCESS_MODE (gated in each domain's `register()` via `client.writes_enabled` / `client.time_tracking_enabled`). Each domain that has writes exposes a `_register_writes(mcp, client)` called from `register()` only when `client.writes_enabled`; JSON write bodies are built with `bodies.drop_none()`.

## Clockify API Notes

- **Auth:** Single API key via HTTP header `X-Api-Key`. No OAuth. Key obtained from Clockify Profile Settings → API.
- **Hosts:**
  - Regular API: `https://api.clockify.me/api/v1`
  - Reports API: `https://reports.api.clockify.me/v1`
  - Regional prefixes: `euc1`, `use2`, `euw2`, `apse2` (e.g. `https://euc1.clockify.me/api/v1` + `https://euc1.clockify.me/report/v1`)
  - Subdomain workspaces: override via `CLOCKIFY_BASE_URL` / `base_url` config key.
- **Workspace scope:** Almost every endpoint is `/workspaces/{workspaceId}/...`. Tools accept an optional `workspace_id`; fall back to `default_workspace_id` from config.
- **Pagination:** Query params `page` (1-based) and `page-size`; response includes `Last-Page` header. Use `pagination.page_params()` to build the params; check `pagination.is_last_page(response_headers)` if you need to detect the final page.
- **Rate limit:** ~50 req/s. The client retries on 429 with backoff; do not add extra sleeps in tool code.
- **IDs:** All IDs are opaque strings (MongoDB ObjectId-like hex). Never construct or guess them.

## Development Conventions

- `uv run` for all commands — do not activate the venv manually.
- Tests: `uv run pytest -q` → expect 176 passed, 11 skipped. Add tests for every new tool in `tests/`.
- Lint: `uv run ruff check src/ tests/` must be clean before commit.
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- Never document or register tools that don't exist yet. Keep README accurate to implemented state.
