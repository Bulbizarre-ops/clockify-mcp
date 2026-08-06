# Waves — Cloudflare Worker tool coverage

Companion to the Python server’s phased coverage. Tool **names** and **access tiers** stay aligned with [tracegazer/clockify-mcp](https://github.com/tracegazer/clockify-mcp).

## Wave 1 (shipped) — 32 tools

### Read (always)

`get_current_user`, `list_workspaces`, `get_workspace`, `list_users`,
`list_clients`, `get_client`, `list_projects`, `get_project`,
`list_tasks`, `get_task`, `list_tags`, `get_tag`,
`list_time_entries`, `get_time_entry`,
`generate_summary_report`, `generate_detailed_report`

### Time-tracking writes

`create_time_entry`, `update_time_entry`, `delete_time_entry`

### Full writes

`stop_running_timer`,
`create_client`, `update_client`, `delete_client`,
`create_project`, `update_project`, `delete_project`,
`create_task`, `update_task`, `delete_task`,
`create_tag`, `update_tag`, `delete_tag`

## Wave 2 (planned)

Time-off, holidays, expenses, approvals, invoices (subset), scheduling, custom fields.
Also consider Python time-entry extras already in full/time-tracking upstream:
`duplicate_time_entry`, `bulk_update_time_entries`, `create_time_entry_for_user`.

## Wave 3 (planned)

Webhooks, shared reports, weekly/attendance/expense reports, exports (Workers-safe variant — no local `save_path`).

## Adding a tool (TDD)

1. Registry test — name appears in the correct mode (red).
2. Handler test — mock `ClockifyClient` (red).
3. Entry in `src/domains/registry.ts` (tier + wave).
4. Handler in `src/domains/handlers.ts`.
5. Zod schema + `registerTool` wiring in `src/server.ts`.
6. `npm test` green; update this file + README if user-facing.

Never invent Clockify IDs. Always require `workspace_id` or `X-Clockify-Workspace-Id`.
