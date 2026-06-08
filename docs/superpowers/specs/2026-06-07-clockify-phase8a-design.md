# Clockify MCP — Phase 8a Design (report export + member assignment + time-entry extras)

**Date:** 2026-06-07
**Status:** Approved
**Author:** Alan (tracegazer)

## 1. Overview

Phase 8a closes three deferred coverage gaps, all verified against the live Clockify OpenAPI 3.0.1:

1. **Report export** — the report endpoints accept an `exportType` (`JSON|PDF|CSV|XLSX|ZIP`); a new `export_report` tool returns a real PDF/CSV/XLSX file ("professional reports") instead of JSON.
2. **Member assignment** — `create_time_off_policy`, `create_holiday`, `update_holiday` currently only expose `everyone_including_new`; add `users`/`user_groups` to assign specific members (both schemas accept `users`/`userGroups`).
3. **Time-entry extras** — `create_time_entry_for_user` (log time for another user) and `stop_running_timer` (stop a user's running timer).

Phase 8b (later) covers attendance/expense reports, shared-reports CRUD, and a `fetch_all` pagination helper — out of scope here.

## 2. Report export

**Client infra:** add `ClockifyClient.report_bytes(path, json) -> bytes` — POST to the Reports host returning raw bytes, i.e. `self._request("POST", self._config.reports_base, path, json=json, raw=True)`. The `raw=True` path already exists (used by `get_bytes`).

**Tool:** `reports.export_report(report_type, fmt, save_path, date_range_start, date_range_end, workspace_id=None)`:
- `report_type` ∈ `detailed | summary | weekly` (validated — it's a URL segment; raise `ValueError` otherwise).
- `fmt` ∈ `PDF | CSV | XLSX` (passed as `exportType`).
- Builds the same body as the matching JSON report tool plus `"exportType": fmt`, with sensible defaults for the required per-type filter object: `detailed` → `detailedFilter: {}`; `summary` → `summaryFilter: {"groups": ["PROJECT"]}`; `weekly` → `weeklyFilter: {"group": "USER", "subgroup": "TIME"}`.
- Calls `client.report_bytes(f"workspaces/{ws}/reports/{report_type}", body)`, writes the bytes to `save_path`, returns `{"path": save_path, "bytes": <len>, "format": fmt}` (keeps the binary out of the model context, mirroring `download_expense_receipt`).
- Registered as a **read** tool (always available; reports are reads). Advanced filtering is intentionally not exposed here — date range + format is the v1 surface.

## 3. Member assignment (time off / holidays)

**Helper:** add `bodies.ids_filter(ids: list[str]) -> dict` → `{"ids": ids, "contains": "CONTAINS", "status": "ALL"}` (the shape `UserIdsSchema`/`UserGroupIdsSchema` expect).

**Changes** (module fn + its `@mcp.tool()` wrapper + docstring, keeping `everyone_including_new`):
- `create_time_off_policy`: add `users: list[str] | None = None`, `user_groups: list[str] | None = None` → body `"users": ids_filter(users) if users else None`, `"userGroups": ids_filter(user_groups) if user_groups else None`.
- `create_holiday`, `update_holiday`: same two params → same body keys.

Docstrings: note the holiday/policy must be assigned to someone — pass `everyone_including_new=True` **or** `users`/`user_groups`.

## 4. Time-entry extras (write, full mode only)

Both go in `time_entries._register_writes` (full `CLOCKIFY_ENABLE_WRITES`/`access_mode=full` only) — NOT in the time-tracking set, since they target an arbitrary `user_id`.

- `create_time_entry_for_user(user_id, start, workspace_id=None, end=None, description=None, project_id=None, task_id=None, tag_ids=None, billable=None, type=None)` → POST `workspaces/{ws}/user/{user_id}/time-entries` with the same camelCase body as `create_time_entry` (start required; omit end for a running timer).
- `stop_running_timer(user_id, end, workspace_id=None)` → PATCH `workspaces/{ws}/user/{user_id}/time-entries` with `{"end": end}` (the API's "stop currently running timer" endpoint; `end` is an ISO-8601 datetime, required).

Module-level fns + wrappers + `*_fn` aliases at the file bottom, per the established pattern.

## 5. Testing

- `tests/test_reports.py`: `export_report` for each `report_type` builds the right body (correct filter object + `exportType`) and writes the mocked bytes to `save_path` (respx mocks the Reports host returning bytes); invalid `report_type` raises `ValueError`.
- `tests/test_time_off.py` / `tests/test_holidays.py`: passing `users=["u1"]` / `user_groups=["g1"]` produces `users: {"ids": ["u1"], "contains": "CONTAINS", "status": "ALL"}` etc. in the body.
- `tests/test_time_entries.py`: `create_time_entry_for_user` hits `/user/u1/time-entries` with the camelCase body; `stop_running_timer` PATCHes `/user/u1/time-entries` with `{"end": ...}`.
- `tests/test_server.py`: `export_report` present in the default discovery set; `create_time_entry_for_user`/`stop_running_timer` present in the writes-enabled set and ABSENT in time-tracking mode and read mode.
- `tests/test_client.py`: `report_bytes` returns bytes from a mocked Reports-host POST.

## 6. Out of scope (Phase 8b or later)

- `generate_attendance_report` (POST `/reports/attendance`, `AttendanceReportFilterV1`), `generate_expenses_report` (POST `/reports/expenses/detailed`, `ExpenseReportFilterV1`).
- Shared-reports CRUD (`/shared-reports`).
- `fetch_all` pagination helper (deferred; for an MCP, returning all pages risks flooding the model — revisit whether it earns its place).
- Advanced report-export filters (projects/users/tags); `ZIP`/`JSON_V1` export formats.
- Stopping/creating time entries via the self-scoped time-tracking tier (these are admin/cross-user, full-mode only).
