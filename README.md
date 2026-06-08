# clockify-mcp

<!-- mcp-name: io.github.tracegazer/clockify-mcp -->

MCP server for the [Clockify](https://clockify.me) time-tracking API.

Expose Clockify workspaces, users, groups, clients, projects, tasks, tags, time entries, reports, time off, holidays, expenses, approvals, custom fields, scheduling, invoices, and webhooks as [Model Context Protocol](https://modelcontextprotocol.io) tools so any MCP-compatible client (Claude Desktop, Cursor, etc.) can query your time-tracking data in natural language.

## What can it do?

**48 read-only tools** are available today (Phase 0–8b — 18 domains). 64 write tools (create/update/delete across clients, projects, tasks, tags, time entries, holidays, expenses, and expense categories, plus time-off policy/request management, approval submit/resubmit/update, custom-field create/update/delete and project assignment, scheduling assignment management, invoice and payment management, shared-report management, and webhook create/update/delete/token) register when you set `CLOCKIFY_ACCESS_MODE=full` (or the back-compat `CLOCKIFY_ENABLE_WRITES=true`). A middle `time-tracking` mode exposes only the time-entry writes for logging hours — see [Access modes](#configuration).

| Domain | Tools | Tool names |
|--------|------:|------------|
| **Workspaces** | 3 | `get_current_user`, `list_workspaces`, `get_workspace` |
| **Users** | 3 | `list_users`, `get_user_member_profile`, `find_user_team_manager` |
| **Groups** | 1 | `list_user_groups` |
| **Clients** | 2 | `list_clients`, `get_client` |
| **Projects** | 2 | `list_projects`, `get_project` |
| **Tasks** | 2 | `list_tasks`, `get_task` |
| **Tags** | 2 | `list_tags`, `get_tag` |
| **Time entries** | 2 | `list_time_entries`, `get_time_entry` |
| **Reports** | 6 | `generate_detailed_report`, `generate_summary_report`, `generate_weekly_report`, `generate_attendance_report`‡, `generate_expense_report`‡, `export_report` (PDF/CSV/XLSX to a file) |
| **Shared reports** | 2 | `list_shared_reports`, `get_shared_report` |
| **Time off**† | 5 | `list_time_off_policies`, `get_time_off_policy`, `list_time_off_balances_by_policy`, `list_time_off_balances_by_user`, `list_time_off_requests` |
| **Holidays**† | 2 | `list_holidays`, `list_holidays_in_period` |
| **Expenses**† | 4 | `list_expenses`, `get_expense`, `list_expense_categories`, `download_expense_receipt` |
| **Approvals**† | 1 | `list_approval_requests` |
| **Custom fields**† | 2 | `list_workspace_custom_fields`, `list_project_custom_fields` |
| **Scheduling**† | 3 | `list_scheduled_assignments`, `get_project_scheduling_totals`, `get_user_scheduling_totals` |
| **Invoices**† | 3 | `list_invoices`, `get_invoice`, `get_invoice_payments` |
| **Webhooks**† | 3 | `list_webhooks`, `get_webhook`, `get_webhook_logs` |

† **Time off**, **Holidays**, **Expenses**, **Approvals**, **Custom fields**, **Scheduling**, **Invoices**, and **Webhooks** are paid Clockify features — these tools error (HTTP 402/403/404) on plans without them.
‡ `generate_attendance_report` and `generate_expense_report` (and `export_report` for those two types) need the workspace's attendance/Expenses add-ons; the time-based reports (detailed/summary/weekly) and shared reports work on the free plan.

**Write tools** (opt-in — set `CLOCKIFY_ENABLE_WRITES=true`):

| Domain | Tools | Tool names |
|--------|------:|------------|
| **Clients** | 3 | `create_client`, `update_client`, `delete_client` |
| **Projects** | 3 | `create_project`, `update_project`, `delete_project` |
| **Tasks** | 3 | `create_task`, `update_task`, `delete_task` |
| **Tags** | 3 | `create_tag`, `update_tag`, `delete_tag` |
| **Time entries** | 7 | `create_time_entry`, `update_time_entry`, `delete_time_entry`, `duplicate_time_entry`, `bulk_update_time_entries`, `create_time_entry_for_user`, `stop_running_timer` |
| **Shared reports** | 3 | `create_shared_report`, `update_shared_report`, `delete_shared_report` |
| **Time off**† | 5 | `create_time_off_policy`, `create_time_off_request`, `approve_time_off_request`, `reject_time_off_request`, `withdraw_time_off_request` |
| **Holidays**† | 3 | `create_holiday`, `update_holiday`, `delete_holiday` |
| **Expenses**† | 7 | `create_expense`, `update_expense`, `delete_expense`, `create_expense_category`, `update_expense_category`, `delete_expense_category`, `archive_expense_category` |
| **Approvals**† | 4 | `submit_approval_request`, `submit_approval_request_for_user`, `resubmit_approval_entries`, `update_approval_request` |
| **Custom fields**† | 5 | `create_workspace_custom_field`, `update_workspace_custom_field`, `delete_workspace_custom_field`, `set_project_custom_field`, `remove_project_custom_field` |
| **Scheduling**† | 5 | `create_scheduled_assignment`, `update_scheduled_assignment`, `delete_scheduled_assignment`, `publish_scheduled_assignment`, `copy_scheduled_assignment` |
| **Invoices**† | 9 | `create_invoice`, `update_invoice`, `change_invoice_status`, `duplicate_invoice`, `delete_invoice`, `create_invoice_item`, `update_invoice_item`, `delete_invoice_item`, `create_invoice_payment` |
| **Webhooks**† | 4 | `create_webhook`, `update_webhook`, `delete_webhook`, `generate_webhook_token` |

† **Time off**, **Holidays**, **Expenses**, **Approvals**, **Custom fields**, **Scheduling**, **Invoices**, and **Webhooks** are paid Clockify features — these tools error (HTTP 402/403/404) on plans without them.

`create_expense` and `update_expense` accept an optional local receipt file, uploaded via multipart.

## Quick start

### 1. Install

```bash
pip install clockify-mcp
# or run without installing:
uvx clockify-mcp
```

### 2. Get your API key

Log into Clockify → **Profile Settings** → **API** → copy your API key.

### 3. Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent on your platform:

```json
{
  "mcpServers": {
    "clockify": {
      "command": "uvx",
      "args": ["clockify-mcp"],
      "env": {
        "CLOCKIFY_API_KEY": "your-key"
      }
    }
  }
}
```

Restart Claude Desktop. Ask: _"What workspaces do I have in Clockify?"_

## Configuration

Configuration resolves in this order (highest priority first):

1. **Environment variables** (always win)
2. **TOML config** at `~/.config/clockify-mcp/config.toml`

| Env var | TOML key | Description |
|---------|----------|-------------|
| `CLOCKIFY_API_KEY` | `api_key` | Your Clockify API key (required) |
| `CLOCKIFY_REGION` | `region` | `global` (default) \| `euc1` (EU) \| `use2` (USA) \| `euw2` (UK) \| `apse2` (AU) |
| `CLOCKIFY_BASE_URL` | `base_url` | Override for subdomain workspaces, e.g. `https://acme.clockify.me` |
| `CLOCKIFY_DEFAULT_WORKSPACE_ID` | `default_workspace_id` | Fallback workspace when a tool call omits `workspace_id` |
| `CLOCKIFY_ACCESS_MODE` | `access_mode` | `read` (default) \| `time-tracking` (read + log hours) \| `full` (all writes) |
| `CLOCKIFY_ENABLE_WRITES` | `enable_writes` | Back-compat alias: `true` = `access_mode=full`. `CLOCKIFY_ACCESS_MODE` takes precedence. |
| `CLOCKIFY_TELEMETRY` | `telemetry_enabled` | Enable OpenTelemetry — default `false` |
| `CLOCKIFY_TELEMETRY_DETAIL` | `telemetry_detail` | Span detail: `metadata` (default), `ids`, or `full` |

**Access modes:** `read` exposes only read tools. `time-tracking` adds the time-entry write tools (create/update/delete/duplicate/bulk) for logging hours and nothing else — `duplicate`/`bulk` always act on the authenticated user, and for `update`/`delete` by id the assistant is told to confirm before touching an entry that may belong to someone else. `full` exposes all write tools. This gates which MCP tools the server registers; it is not a replacement for the API key's own permissions.

See [`config.toml.example`](config.toml.example) for a copy-paste template.

```toml
# ~/.config/clockify-mcp/config.toml
api_key = "your-clockify-api-key"
# region = "global"
# default_workspace_id = ""
# access_mode = "read"   # read | time-tracking | full
```

> **Tip:** create the config directory first: `mkdir -p ~/.config/clockify-mcp`

## Notes

- **Auth:** Clockify uses a single API key sent as the `X-Api-Key` HTTP header. No OAuth. Get your key from **Profile Settings → API** in the Clockify web app.
- **Regions:** By default the server targets `https://api.clockify.me/api/v1`. Set `CLOCKIFY_REGION` to route to a regional endpoint (e.g. `euc1` → `https://euc1.clockify.me/api/v1`). For custom subdomain workspaces use `CLOCKIFY_BASE_URL`.
- **Workspace scope:** Almost every Clockify operation is scoped to a workspace (`/workspaces/{workspaceId}/...`). Tools accept an optional `workspace_id`; when omitted they fall back to `CLOCKIFY_DEFAULT_WORKSPACE_ID`. If neither is set, the tool asks you to resolve one first via `list_workspaces`.
- **Read-only by default:** The 48 read tools are always available. Set `CLOCKIFY_ACCESS_MODE=time-tracking` to additionally register the 5 time-entry write tools, or `CLOCKIFY_ACCESS_MODE=full` (equivalent: `CLOCKIFY_ENABLE_WRITES=true`) to register all 64 write tools; `delete_*` tools and `withdraw_time_off_request` are irreversible.
- **Pagination:** list tools take optional `page`/`page_size` and return one page. The high-volume lists (`list_time_entries`, `list_projects`, `list_clients`, `list_tasks`, `list_tags`, `list_users`) also accept `fetch_all=true` to follow pagination and return every page concatenated (may make several API calls).
- **Paid features:** Several domains need a paid plan **and** an admin to enable the module in Workspace Settings — see [Paid features & enabling them](#paid-features--enabling-them-in-clockify). The server's error categories tell you which is missing.

## Paid features & enabling them in Clockify

Many domains are gated by **two** independent things — both must be true for the tools to work:

**1. The workspace plan must include the feature.** Otherwise the API returns `402` (or a "subscription" message) and the server raises `ClockifyAPIError` with category `PLAN_REQUIRED`.

| Feature | Minimum plan |
|---------|--------------|
| Reports (detailed/summary/weekly), Shared reports | Free |
| Webhooks | Free (up to 3) — paid for more |
| Time off, Holidays, Invoices, Approvals | Standard |
| Expenses (incl. expense report), Custom fields, Scheduling | Pro |
| Attendance report | Pro (attendance/time-tracking add-on) |

**2. The module must be enabled in the workspace.** Even on the right plan, an admin must turn these on in Clockify → **Workspace Settings**: **Time off, Expenses, Approval, Invoicing, Scheduling**. Until enabled, the API returns `403 "Access Denied"` and the server raises `ClockifyAPIError` with category `ACCESS_DENIED`. (Custom fields, webhooks, and reports need no separate toggle.)

When an operation fails, the error category says what to do:

- `PLAN_REQUIRED` — upgrade the workspace plan (Standard/Pro).
- `ACCESS_DENIED` — enable the feature in Workspace Settings, or check the API key user's role/permission.
- `AUTH` — the API key is missing, invalid, or revoked.

## Observability (optional)

The server exports OpenTelemetry traces, metrics, and logs over OTLP. It is **opt-in and off by default** — when disabled, `opentelemetry` is never imported. Enable it with the optional extra:

```bash
pip install "clockify-mcp[telemetry]"
export CLOCKIFY_TELEMETRY=1
```

When enabled you get a span per MCP tool call (`execute_tool <name>`) and per Clockify API request, plus tool-duration/error metrics and structured logs. `CLOCKIFY_TELEMETRY_DETAIL` controls how much argument/payload data is attached (`metadata` default → `ids` → `full`); the API key is always redacted. OTLP endpoint and headers come from the standard OpenTelemetry env vars (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_SERVICE_NAME`, etc.).

> **Dynatrace:** traces and logs work as-is, but Dynatrace's OTLP metrics ingest requires **delta** temporality — set `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` or metric export fails with `400 Bad Request`. Endpoint: `https://{env-id}.live.dynatrace.com/api/v2/otlp`, header `Authorization=Api-Token dt0c01.…` (token needs the `openTelemetryTrace.ingest`, `metrics.ingest`, `logs.ingest` scopes).

## Development

```bash
git clone https://github.com/tracegazer/clockify-mcp
cd clockify-mcp
uv sync --extra dev

CLOCKIFY_API_KEY=dummy uv run clockify-mcp --help
uv run pytest -q
uv run ruff check src/ tests/
```

## License

MIT
