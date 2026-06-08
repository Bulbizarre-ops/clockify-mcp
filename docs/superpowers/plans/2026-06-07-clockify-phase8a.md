# Phase 8a Implementation Plan — report export + member assignment + time-entry extras

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native report export (PDF/CSV/XLSX), specific member/group assignment for time-off policies & holidays, and two cross-user time-entry write tools.

**Architecture:** A new `client.report_bytes()` (POST to the Reports host, raw bytes) backs a read-only `export_report` tool. A shared `bodies.ids_filter()` builds the `{ids,contains,status}` member filter used by new `users`/`user_groups` params on time-off/holiday writes. Two new full-mode time-entry write tools target an explicit user_id.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx + pytest-asyncio, `uv`, ruff.

---

## Background — verified current state

- `client.py`: `report(self, path, json)` POSTs to `self._config.reports_base` and returns parsed JSON; `get_bytes` already uses a `raw=True` path on `_request`; `patch(self, path, json)` exists.
- `reports.py`: three JSON report fns (`generate_detailed/summary/weekly_report`) + their `register()` wrappers + `*_fn` aliases at the bottom. Bodies: detailed→`detailedFilter`, summary→`summaryFilter {groups}`, weekly→`weeklyFilter {group,subgroup}`.
- `bodies.py`: only `drop_none`.
- `time_off.py` `create_time_off_policy`: body has name/color/icon/timeUnit/allowHalfDay/allowNegativeBalance/everyoneIncludingNew/approve; module fn + wrapper in `_register_writes`. Imports `from ..bodies import drop_none`.
- `holidays.py` `create_holiday`/`update_holiday`: dates nested as `"datePeriod": {"startDate", "endDate"}`; body has name/color/occursAnnually/everyoneIncludingNew/datePeriod; module fns + wrappers. Imports `from ..bodies import drop_none`.
- `time_entries.py`: `_register_writes` (full) registers create/update/delete/duplicate/bulk; `_register_time_tracking_writes` registers the self-scoped subset; `*_fn` aliases at bottom. Imports `from ..bodies import drop_none`.
- Verified API facts: report `exportType` enum includes `PDF, CSV, XLSX`; report responses are `*/*` (binary when exporting). Holiday create AND time-off policy create both accept `users` (UserIdsSchema `{ids,contains,status}`) and `userGroups` (UserGroupIdsSchema). "Add time entry for another user" = POST `workspaces/{ws}/user/{userId}/time-entries`. "Stop running timer" = PATCH `workspaces/{ws}/user/{userId}/time-entries` with `{end}` (end required).

**Baseline:** `uv run pytest -q` → 191 passed, 16 skipped, ruff clean.

---

## File Structure

- Modify: `src/clockify_mcp/client.py` — add `report_bytes`
- Modify: `src/clockify_mcp/bodies.py` — add `ids_filter`
- Modify: `src/clockify_mcp/domains/reports.py` — add `export_report` fn + wrapper
- Modify: `src/clockify_mcp/domains/time_off.py` — `users`/`user_groups` on policy create
- Modify: `src/clockify_mcp/domains/holidays.py` — `users`/`user_groups` on create/update
- Modify: `src/clockify_mcp/domains/time_entries.py` — `create_time_entry_for_user`, `stop_running_timer`
- Tests: `tests/test_client.py`, `tests/test_bodies.py` (new), `tests/test_reports.py`, `tests/test_time_off.py`, `tests/test_holidays.py`, `tests/test_time_entries.py`, `tests/test_server.py`

---

## Task 1: Infra — `client.report_bytes` + `bodies.ids_filter`

**Files:** Modify `src/clockify_mcp/client.py`, `src/clockify_mcp/bodies.py`; Test `tests/test_client.py`, `tests/test_bodies.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bodies.py`:

```python
from clockify_mcp.bodies import drop_none, ids_filter


def test_ids_filter_shape():
    assert ids_filter(["u1", "u2"]) == {
        "ids": ["u1", "u2"],
        "contains": "CONTAINS",
        "status": "ALL",
    }


def test_drop_none_keeps_falsy_but_drops_none():
    assert drop_none({"a": None, "b": False, "c": 0, "d": "x"}) == {
        "b": False,
        "c": 0,
        "d": "x",
    }
```

Append to `tests/test_client.py`:

```python
@respx.mock
async def test_report_bytes_returns_raw_bytes(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/detailed"
    ).mock(return_value=httpx.Response(200, content=b"%PDF-1.4 fake"))
    client = ClockifyClient(config)
    data = await client.report_bytes(
        "workspaces/ws1/reports/detailed", {"exportType": "PDF"}
    )
    assert data == b"%PDF-1.4 fake"
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_bodies.py tests/test_client.py::test_report_bytes_returns_raw_bytes -q`
Expected: FAIL — `ImportError: cannot import name 'ids_filter'` / `AttributeError: ... 'report_bytes'`.

- [ ] **Step 3: Add `ids_filter` to bodies.py**

In `src/clockify_mcp/bodies.py`, append:

```python
def ids_filter(ids: list[str]) -> dict[str, Any]:
    """Build the {ids, contains, status} filter Clockify uses to target members.

    Used for the ``users``/``userGroups`` fields of time-off policies and holidays.
    """
    return {"ids": ids, "contains": "CONTAINS", "status": "ALL"}
```

- [ ] **Step 4: Add `report_bytes` to client.py**

In `src/clockify_mcp/client.py`, immediately after the `report` method (the one that returns `self._request("POST", self._config.reports_base, path, json=json)`), add:

```python
    async def report_bytes(self, path: str, json: dict[str, Any] | None = None) -> bytes:
        """POST to the Reports API host and return raw bytes (PDF/CSV/XLSX exports)."""
        return await self._request(
            "POST", self._config.reports_base, path, json=json, raw=True
        )
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_bodies.py tests/test_client.py -q`
Expected: PASS.

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (≈194 passed, 16 skipped) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/bodies.py src/clockify_mcp/client.py tests/test_bodies.py tests/test_client.py
git commit -m "feat: client.report_bytes (binary report export) + bodies.ids_filter"
```

---

## Task 2: `export_report` tool

**Files:** Modify `src/clockify_mcp/domains/reports.py`; Test `tests/test_reports.py`, `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_reports.py` (it already imports `httpx`, `respx`, `ClockifyClient`, `reports`; add `import pytest` if not present):

```python
@respx.mock
async def test_export_report_detailed_pdf(config, tmp_path):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/detailed"
    ).mock(return_value=httpx.Response(200, content=b"%PDF-1.4 data"))
    client = ClockifyClient(config)
    dest = tmp_path / "report.pdf"
    result = await reports.export_report(
        client, report_type="detailed", fmt="PDF", save_path=str(dest),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-31T23:59:59Z",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["exportType"] == "PDF"
    assert body["detailedFilter"] == {}
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert dest.read_bytes() == b"%PDF-1.4 data"
    assert result == {"path": str(dest), "bytes": len(b"%PDF-1.4 data"), "format": "PDF"}
    await client.aclose()


@respx.mock
async def test_export_report_summary_and_weekly_filters(config, tmp_path):
    client = ClockifyClient(config)
    s = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/summary"
    ).mock(return_value=httpx.Response(200, content=b"x"))
    await reports.export_report(
        client, report_type="summary", fmt="CSV", save_path=str(tmp_path / "s.csv"),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-07T23:59:59Z",
    )
    assert json.loads(s.calls.last.request.content)["summaryFilter"] == {"groups": ["PROJECT"]}
    w = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/weekly"
    ).mock(return_value=httpx.Response(200, content=b"x"))
    await reports.export_report(
        client, report_type="weekly", fmt="XLSX", save_path=str(tmp_path / "w.xlsx"),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-07T23:59:59Z",
    )
    body = json.loads(w.calls.last.request.content)
    assert body["weeklyFilter"] == {"group": "USER", "subgroup": "TIME"}
    assert body["exportType"] == "XLSX"
    await client.aclose()


async def test_export_report_rejects_bad_type(config, tmp_path):
    client = ClockifyClient(config)
    with pytest.raises(ValueError):
        await reports.export_report(
            client, report_type="bogus", fmt="PDF", save_path=str(tmp_path / "x"),
            date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-02T00:00:00Z",
        )
    await client.aclose()
```

Ensure the top of `tests/test_reports.py` has `import json` and `import pytest` (add whichever is missing to the existing import block).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_reports.py -q`
Expected: FAIL — `AttributeError: module 'clockify_mcp.domains.reports' has no attribute 'export_report'`.

- [ ] **Step 3: Implement `export_report`**

In `src/clockify_mcp/domains/reports.py`, add `from pathlib import Path` to the imports (after `from typing import ...`). Add this module-level fn after `generate_weekly_report` (before `def register`):

```python
async def export_report(
    client: ClockifyClient,
    *,
    report_type: str,
    fmt: str,
    save_path: str,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
) -> Any:
    """Export a report as a file (PDF/CSV/XLSX) for a date range.

    report_type is detailed, summary, or weekly. fmt is PDF, CSV, or XLSX. The bytes
    are written to save_path; returns {"path", "bytes", "format"} (the file content is
    kept out of the model context). Uses sensible default grouping per report type;
    for fine-grained JSON results use the generate_*_report tools.
    """
    if report_type == "detailed":
        report_filter = {"detailedFilter": {}}
    elif report_type == "summary":
        report_filter = {"summaryFilter": {"groups": ["PROJECT"]}}
    elif report_type == "weekly":
        report_filter = {"weeklyFilter": {"group": "USER", "subgroup": "TIME"}}
    else:
        raise ValueError(
            f"report_type must be 'detailed', 'summary', or 'weekly'; got {report_type!r}"
        )
    ws = resolve_workspace_id(client, workspace_id)
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        **report_filter,
        "exportType": fmt,
    }
    data = await client.report_bytes(f"workspaces/{ws}/reports/{report_type}", body)
    path = Path(save_path)
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data), "format": fmt}
```

In `register()`, add a wrapper after the `generate_weekly_report` tool (still inside `register`):

```python
    @mcp.tool()
    async def export_report(
        report_type: str,
        fmt: str,
        save_path: str,
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Export a report as a file (PDF/CSV/XLSX). report_type is detailed/summary/
        weekly; fmt is PDF/CSV/XLSX; bytes are written to save_path."""
        return await export_report_fn(
            client,
            report_type=report_type,
            fmt=fmt,
            save_path=save_path,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
        )
```

Add the alias at the bottom (next to the other `*_fn`):

```python
export_report_fn = export_report
```

- [ ] **Step 4: Run the report tests**

Run: `uv run pytest tests/test_reports.py -q`
Expected: PASS.

- [ ] **Step 5: Register-test for export_report**

In `tests/test_server.py`, add `"export_report"` to the asserted set inside `test_build_server_registers_discovery_tools` (it's a read tool, always registered).

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (≈198 passed, 16 skipped) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/reports.py tests/test_reports.py tests/test_server.py
git commit -m "feat: export_report tool (PDF/CSV/XLSX) via Reports host"
```

---

## Task 3: Member/group assignment on time-off policies & holidays

**Files:** Modify `src/clockify_mcp/domains/time_off.py`, `src/clockify_mcp/domains/holidays.py`; Test `tests/test_time_off.py`, `tests/test_holidays.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_time_off.py`:

```python
@respx.mock
async def test_create_policy_with_specific_users(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(201, json={"id": "p1"}))
    client = ClockifyClient(config_writes)
    await time_off.create_time_off_policy(
        client, name="PTO", users=["u1"], user_groups=["g1"]
    )
    body = json.loads(route.calls.last.request.content)
    assert body["users"] == {"ids": ["u1"], "contains": "CONTAINS", "status": "ALL"}
    assert body["userGroups"] == {"ids": ["g1"], "contains": "CONTAINS", "status": "ALL"}
    await client.aclose()
```

Append to `tests/test_holidays.py` (add `import json` to the top import block if missing):

```python
@respx.mock
async def test_create_holiday_with_specific_users(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/holidays").mock(
        return_value=httpx.Response(201, json={"id": "h1"})
    )
    client = ClockifyClient(config_writes)
    await holidays.create_holiday(
        client, name="Xmas", start_date="2026-12-25", end_date="2026-12-25",
        users=["u1"],
    )
    body = json.loads(route.calls.last.request.content)
    assert body["users"] == {"ids": ["u1"], "contains": "CONTAINS", "status": "ALL"}
    await client.aclose()


@respx.mock
async def test_update_holiday_with_user_groups(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/holidays/h1").mock(
        return_value=httpx.Response(200, json={"id": "h1"})
    )
    client = ClockifyClient(config_writes)
    await holidays.update_holiday(
        client, holiday_id="h1", name="Xmas", start_date="2026-12-25",
        end_date="2026-12-25", occurs_annually=True, user_groups=["g1"],
    )
    body = json.loads(route.calls.last.request.content)
    assert body["userGroups"] == {"ids": ["g1"], "contains": "CONTAINS", "status": "ALL"}
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_time_off.py tests/test_holidays.py -q`
Expected: FAIL — `TypeError: ... got an unexpected keyword argument 'users'`.

- [ ] **Step 3: Update `time_off.create_time_off_policy`**

In `src/clockify_mcp/domains/time_off.py`, change the import line `from ..bodies import drop_none` to `from ..bodies import drop_none, ids_filter`.

In the module-level `create_time_off_policy` signature, add two params before `color` (keyword-only, anywhere after `workspace_id` is fine):

```python
    users: list[str] | None = None,
    user_groups: list[str] | None = None,
```

In its `body = drop_none({...})`, add these two keys (e.g. right after `"everyoneIncludingNew": everyone_including_new,`):

```python
            "users": ids_filter(users) if users else None,
            "userGroups": ids_filter(user_groups) if user_groups else None,
```

In the `_register_writes` wrapper `create_time_off_policy`, add the same two params to the signature and pass them through to `create_time_off_policy_fn(... users=users, user_groups=user_groups, ...)`.

Update the module-fn docstring's assignee sentence to: "The policy must be assigned to members — pass everyone_including_new=True, or users/user_groups (member/group ids)."

- [ ] **Step 4: Update `holidays.create_holiday` and `update_holiday`**

In `src/clockify_mcp/domains/holidays.py`, change `from ..bodies import drop_none` to `from ..bodies import drop_none, ids_filter`.

In BOTH module-level `create_holiday` and `update_holiday`: add params

```python
    users: list[str] | None = None,
    user_groups: list[str] | None = None,
```

and add to each `body = drop_none({...})` (after `"everyoneIncludingNew": everyone_including_new,`):

```python
            "users": ids_filter(users) if users else None,
            "userGroups": ids_filter(user_groups) if user_groups else None,
```

Add the same two params to BOTH `_register_writes` wrappers (`create_holiday`, `update_holiday`) and pass them through (`users=users, user_groups=user_groups`). Update both docstrings' assignee sentence to mention "or users/user_groups".

- [ ] **Step 5: Run the domain tests**

Run: `uv run pytest tests/test_time_off.py tests/test_holidays.py -q`
Expected: PASS (existing + 3 new).

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (≈201 passed, 16 skipped) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/time_off.py src/clockify_mcp/domains/holidays.py tests/test_time_off.py tests/test_holidays.py
git commit -m "feat: assign time-off policies & holidays to specific users/groups"
```

---

## Task 4: Time-entry extras (full mode only)

**Files:** Modify `src/clockify_mcp/domains/time_entries.py`; Test `tests/test_time_entries.py`, `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_time_entries.py`:

```python
@respx.mock
async def test_create_time_entry_for_user(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(201, json={"id": "te1"}))
    client = ClockifyClient(config_writes)
    await time_entries.create_time_entry_for_user(
        client, user_id="u1", start="2021-01-01T09:00:00Z", description="work",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2021-01-01T09:00:00Z", "description": "work"}
    await client.aclose()


@respx.mock
async def test_stop_running_timer(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(200, json={"id": "te1"}))
    client = ClockifyClient(config_writes)
    await time_entries.stop_running_timer(
        client, user_id="u1", end="2021-01-01T10:00:00Z"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"end": "2021-01-01T10:00:00Z"}
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: FAIL — `AttributeError: module 'clockify_mcp.domains.time_entries' has no attribute 'create_time_entry_for_user'`.

- [ ] **Step 3: Add the module-level write fns**

In `src/clockify_mcp/domains/time_entries.py`, add after the existing `bulk_update_time_entries` module fn (before `def register`):

```python
async def create_time_entry_for_user(
    client: ClockifyClient,
    *,
    user_id: str,
    start: str,
    workspace_id: str | None = None,
    end: str | None = None,
    description: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    tag_ids: list[str] | None = None,
    billable: bool | None = None,
    type: str | None = None,
) -> Any:
    """Create a time entry for ANOTHER user (admin action). Resolve user_id with
    list_users. start (and optional end) are ISO-8601; omit end for a running timer."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "description": description,
            "projectId": project_id,
            "taskId": task_id,
            "tagIds": tag_ids,
            "billable": billable,
            "type": type,
        }
    )
    return await client.post(f"workspaces/{ws}/user/{user_id}/time-entries", json=body)


async def stop_running_timer(
    client: ClockifyClient, *, user_id: str, end: str, workspace_id: str | None = None
) -> Any:
    """Stop a user's currently running timer by setting its end (ISO-8601). Resolve
    user_id with get_current_user (yourself) or list_users (someone else)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.patch(
        f"workspaces/{ws}/user/{user_id}/time-entries", json={"end": end}
    )
```

- [ ] **Step 4: Register them in `_register_writes` (full only)**

In `time_entries._register_writes`, add two wrappers (after the existing `bulk_update_time_entries` wrapper, still inside `_register_writes`):

```python
    @mcp.tool()
    async def create_time_entry_for_user(
        user_id: str,
        start: str,
        workspace_id: str | None = None,
        end: str | None = None,
        description: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        tag_ids: list[str] | None = None,
        billable: bool | None = None,
        type: str | None = None,
    ) -> Any:
        """Create a time entry for another user (admin). Resolve user_id with list_users."""
        return await create_time_entry_for_user_fn(
            client,
            user_id=user_id,
            start=start,
            workspace_id=workspace_id,
            end=end,
            description=description,
            project_id=project_id,
            task_id=task_id,
            tag_ids=tag_ids,
            billable=billable,
            type=type,
        )

    @mcp.tool()
    async def stop_running_timer(
        user_id: str, end: str, workspace_id: str | None = None
    ) -> Any:
        """Stop a user's currently running timer by setting its end (ISO-8601)."""
        return await stop_running_timer_fn(
            client, user_id=user_id, end=end, workspace_id=workspace_id
        )
```

Do NOT add these to `_register_time_tracking_writes` — they target an arbitrary user_id and are full-mode only.

Add the aliases at the very bottom (next to the other time-entry `*_fn`):

```python
create_time_entry_for_user_fn = create_time_entry_for_user
stop_running_timer_fn = stop_running_timer
```

- [ ] **Step 5: Run the time-entry tests**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: PASS.

- [ ] **Step 6: Extend the server gating tests**

In `tests/test_server.py`:
- In `test_writes_registered_when_enabled`, add to the asserted set: `"create_time_entry_for_user", "stop_running_timer",`.
- In `test_time_tracking_mode_registers_only_time_entry_writes`, add assertions that these two are ABSENT in time-tracking mode:

```python
    assert "create_time_entry_for_user" not in names
    assert "stop_running_timer" not in names
```

- [ ] **Step 7: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (≈203 passed, 16 skipped) and ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/domains/time_entries.py tests/test_time_entries.py tests/test_server.py
git commit -m "feat: create_time_entry_for_user + stop_running_timer (full-mode writes)"
```

---

## Self-Review

**Spec coverage:**
- §2 report export: `client.report_bytes` (Task 1) + `export_report` read tool with per-type filter defaults + bytes-to-file (Task 2) ✓
- §3 member assignment: `bodies.ids_filter` (Task 1) + `users`/`user_groups` on policy create + holiday create/update (Task 3) ✓
- §4 time-entry extras: `create_time_entry_for_user` + `stop_running_timer`, full-mode only, NOT in time-tracking (Task 4) ✓
- §5 testing: report_bytes, ids_filter, export per type + bad type, member-assignment bodies, the two write tools + gating, discovery registration ✓

**Placeholder scan:** none — every code/test step shows complete code; commands show expected output.

**Type/name consistency:** `report_bytes`, `ids_filter`, `export_report`(+`export_report_fn`), `create_time_entry_for_user`(+`_fn`), `stop_running_timer`(+`_fn`) names consistent across impl, wrappers, aliases, and tests. `export_report` is a read tool (no gating); the two time-entry tools are full-only (registered in `_register_writes`, asserted absent in time-tracking). `ids_filter` shape `{ids,contains,status}` matches the tests. Holiday dates stay nested in `datePeriod` (untouched). Test counts are estimates; the implementer confirms actual counts at each step.

**Out of scope (Phase 8b):** attendance/expense reports, shared-reports CRUD, `fetch_all`, advanced export filters.
