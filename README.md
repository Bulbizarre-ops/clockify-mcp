# clockify-mcp

<!-- mcp-name: io.github.tracegazer/clockify-mcp -->

> A [Model Context Protocol](https://modelcontextprotocol.io) server for the [Clockify](https://clockify.me) **time-tracking API**.

Give your AI assistant access to your Clockify data — query workspaces, projects, and time entries, generate reports, log hours, and manage clients, invoices, and more — all through natural language.

**117 tools** across 18 domains. Read-only by default, with optional write operations behind explicit opt-in.

## Install in one click

The easiest way to use this server with **Claude Desktop** (and other MCPB-compatible clients) is the prebuilt bundle:

**➡️ [Download `clockify-mcp.mcpb`](https://github.com/tracegazer/clockify-mcp/releases/latest/download/clockify-mcp.mcpb)** — then double-click it. Claude Desktop opens the installer, prompts for your Clockify API key, and you're done. No Python, no `npx`/`uvx`, no config files.

The `.mcpb` is attached to every [GitHub Release](https://github.com/tracegazer/clockify-mcp/releases) and mirrored on [Smithery](https://smithery.ai/). Prefer a package manager or container? See [Quick start](#quick-start) below.

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
```

Or run without installing (requires [uv](https://docs.astral.sh/uv/)):

```bash
uvx clockify-mcp
```

Or use the container image (published to GHCR on every release):

```bash
docker run --rm -i -e CLOCKIFY_API_KEY=your-key ghcr.io/tracegazer/clockify-mcp:latest
```

### 2. Connect to Claude Desktop

Add this to your `claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "clockify": {
      "command": "uvx",
      "args": ["clockify-mcp"],
      "env": {
        "CLOCKIFY_API_KEY": "your-api-key"
      }
    }
  }
}
```

Restart Claude Desktop. Ask: _"What workspaces do I have in Clockify?"_

<details>
<summary>Using pip install instead of uvx</summary>

```jsonc
{
  "mcpServers": {
    "clockify": {
      "command": "clockify-mcp",
      "env": {
        "CLOCKIFY_API_KEY": "your-api-key"
      }
    }
  }
}
```

</details>

<details>
<summary>Enabling write operations</summary>

By default the server is **read-only**. Opt into writes with `CLOCKIFY_ACCESS_MODE`:

| Mode | Reads | Writes |
|------|------------|--------|
| `read` (default) | everything | nothing |
| `time-tracking` | everything | time-entry writes only (log & edit hours) |
| `full` | everything | all write tools (clients, projects, invoices, …) |

```jsonc
{
  "mcpServers": {
    "clockify": {
      "command": "uvx",
      "args": ["clockify-mcp"],
      "env": {
        "CLOCKIFY_API_KEY": "your-api-key",
        "CLOCKIFY_ACCESS_MODE": "full"
      }
    }
  }
}
```

> **Compatibility:** the legacy `CLOCKIFY_ENABLE_WRITES=true` still works and maps to `full`.
> If both are set, `CLOCKIFY_ACCESS_MODE` wins. In `time-tracking` mode, `duplicate`/`bulk`
> always act on the authenticated user; for `update`/`delete` by id the assistant is told to
> confirm before touching an entry that may belong to someone else.

> **Warning:** write mode lets the connected agent create, modify, and delete real data through
> your Clockify credential. `delete_*` tools and `withdraw_time_off_request` are irreversible.

</details>

### 3. Get your API key

Log into Clockify → **Profile Settings** → **API** → copy your API key.

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

## Running the server

```bash
clockify-mcp                       # STDIO transport (default)
clockify-mcp --transport sse       # SSE/HTTP transport
```

> **Security note:** STDIO (the default) keeps everything local. The `sse` and `streamable-http` transports have no built-in authentication — only use them bound to loopback or behind an authenticated reverse proxy.

## Notes

- **Workspace scope:** Almost every Clockify operation is scoped to a workspace (`/workspaces/{workspaceId}/...`). Tools accept an optional `workspace_id`; when omitted they fall back to `CLOCKIFY_DEFAULT_WORKSPACE_ID`. If neither is set, the tool asks you to resolve one first via `list_workspaces`.
- **Pagination:** list tools take optional `page`/`page_size` and return one page. The high-volume lists (`list_time_entries`, `list_projects`, `list_clients`, `list_tasks`, `list_tags`, `list_users`) also accept `fetch_all=true` to follow pagination and return every page concatenated (may make several API calls).
- **Errors:** failures carry a category — `PLAN_REQUIRED`, `ACCESS_DENIED`, or `AUTH` — so the assistant knows whether to ask you to upgrade the plan, enable a module, or fix the key. See [Paid features](#paid-features--enabling-them-in-clockify).

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

The server can emit OpenTelemetry traces, metrics, and logs — completely opt-in and vendor-neutral. Export to any OTLP-compatible backend (Dynatrace, Grafana, Datadog, Jaeger, etc.). When disabled, `opentelemetry` is never imported.

```bash
pip install "clockify-mcp[telemetry]"

export CLOCKIFY_TELEMETRY=1
```

OTLP endpoint and headers are configured via standard OpenTelemetry env vars (not in the TOML file). `CLOCKIFY_TELEMETRY_DETAIL` controls how much argument/payload data is attached (`metadata` default → `ids` → `full`); the API key is always redacted.

<details>
<summary>Dynatrace setup</summary>

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://<your-env>.live.dynatrace.com/api/v2/otlp"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token <YOUR_DT_TOKEN>"
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta
export OTEL_SERVICE_NAME=clockify-mcp
```

Token scopes needed: `openTelemetryTrace.ingest`, `metrics.ingest`, `logs.ingest`. Dynatrace's OTLP metrics ingest requires **delta** temporality — without that env var, metric export fails with `400 Bad Request`.

</details>

<details>
<summary>Generic OTLP collector</summary>

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME=clockify-mcp
```

</details>

**Signals emitted:**

- **Traces** — a span per MCP tool call (`execute_tool <name>`) and per Clockify API request
- **Metrics** — `mcp.tool.duration`, `mcp.tool.errors`, and Clockify client request durations
- **Logs** — tool errors and unexpected API response shapes, correlated to traces (OTLP only, never stdout)

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

[MIT](LICENSE)
