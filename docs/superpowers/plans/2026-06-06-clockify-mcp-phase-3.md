# Phase 3 — Time Entries (read) + Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only MCP tools for time entries (list-by-user + get) and the three Clockify report types (detailed, summary, weekly), bringing the server from 15 tools / 7 domains to 20 tools / 9 domains.

**Architecture:** Two new domain modules under `src/clockify_mcp/domains/`. `time_entries.py` follows the established list/get pattern (module-level async fns + `register()` wrapping them as `@mcp.tool()`, `*_fn` aliases, `resolve_workspace_id`, `page_params`). `reports.py` is new in one respect: reports POST a JSON filter body to the **Reports API host** via the existing `client.report(path, json)` method (not `client.get`). No client/config/pagination changes are needed — Phase 0 already provides `client.report` and `config.reports_base`.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx + pytest-asyncio, `uv`, ruff.

---

## Background — verified API facts

All paths, query params, host servers, and report body schemas below were verified against the live Clockify OpenAPI spec (`https://docs.clockify.me/`) on 2026-06-06. **Do not invent or alter names.**

### Time entries (regular host `https://api.clockify.me/api/v1`, GET)

| Tool | Path | Query params (exact) |
|---|---|---|
| `list_time_entries` | `workspaces/{ws}/user/{user_id}/time-entries` | `description`, `start`, `end`, `project`, `task`, `tags` (array), `project-required`, `task-required`, `hydrated`, `in-progress`, `get-week-before`, `page`, `page-size` |
| `get_time_entry` | `workspaces/{ws}/time-entries/{time_entry_id}` | `hydrated` |

- `start`/`end` are ISO-8601 datetimes with offset, e.g. `2021-01-01T00:00:00Z`.
- `project`/`task` filter by a single id; `tags` is a list of tag ids.
- `list_time_entries` requires a `user_id` (resolve it with `get_current_user` or `list_users`).

### Reports (Reports host `https://reports.api.clockify.me/v1`, POST via `client.report`)

All three require `dateRangeStart` + `dateRangeEnd` (ISO-8601 datetime strings) plus their own filter object. **Report request bodies are JSON and use camelCase keys** (unlike the hyphenated query params elsewhere).

| Tool | Path (passed to `client.report`) | Required body | Filter object fields used |
|---|---|---|---|
| `generate_detailed_report` | `workspaces/{ws}/reports/detailed` | `dateRangeStart`, `dateRangeEnd`, `detailedFilter` | `detailedFilter`: `page`, `pageSize`, `sortColumn` |
| `generate_summary_report` | `workspaces/{ws}/reports/summary` | `dateRangeStart`, `dateRangeEnd`, `summaryFilter` | `summaryFilter`: `groups` (array), `sortColumn` |
| `generate_weekly_report` | `workspaces/{ws}/reports/weekly` | `dateRangeStart`, `dateRangeEnd`, `weeklyFilter` | `weeklyFilter`: `group`, `subgroup` |

- `detailedFilter.sortColumn` enum: `ID, DESCRIPTION, USER, DURATION, DATE, ZONED_DATE, NATURAL, USER_DATE`.
- `summaryFilter.groups` are grouping keys, e.g. `PROJECT, CLIENT, USER, TASK, TAG, DATE`. `sortColumn` enum: `GROUP, DURATION, AMOUNT, EARNED, COST, PROFIT`. This plan defaults `groups` to `["PROJECT"]` when the caller omits it (a summary report must group by something).
- `weeklyFilter.group`/`subgroup` are strings; common values are `group="USER"` / `subgroup="TIME"`. This plan defaults to those when omitted.
- `client.report(path, json)` POSTs to `config.reports_base` and returns parsed JSON. For the default region `config.reports_base == "https://reports.api.clockify.me/v1"`, so the detailed report URL is `https://reports.api.clockify.me/v1/workspaces/{ws}/reports/detailed`.

### Confirmed behaviors (reused from Phase 2)
- httpx serializes Python `bool` query values to lowercase `true`/`false`; the client's `_clean()` drops `None`. **Pass bools directly — never `str(...).lower()`.**
- Array query params (`tags`) → repeated keys; read back in tests with `request.url.params.get_list("tags")`.
- `page_params()` already emits hyphenated `page-size` for time-entry query params. (Report pagination is different: it goes in the JSON `detailedFilter` as `page`/`pageSize` camelCase — build that dict by hand.)

**Baseline:** `uv run pytest -q` currently reports **35 passed**.

---

## File Structure

- Create: `src/clockify_mcp/domains/time_entries.py` — `list_time_entries`, `get_time_entry`
- Create: `src/clockify_mcp/domains/reports.py` — `generate_detailed_report`, `generate_summary_report`, `generate_weekly_report`
- Create: `tests/test_time_entries.py`, `tests/test_reports.py`
- Modify: `src/clockify_mcp/server.py` — import + register the two new domains
- Modify: `tests/test_server.py` — extend the asserted tool-name set
- Modify: `README.md`, `CLAUDE.md` — update tool tables/counts

Each task is self-contained and leaves the server shippable.

---

## Task 1: Time entries domain

**Files:**
- Create: `src/clockify_mcp/domains/time_entries.py`
- Test: `tests/test_time_entries.py`
- Modify: `src/clockify_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing unit test**

Create `tests/test_time_entries.py`:

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import time_entries


@respx.mock
async def test_list_time_entries_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(200, json=[{"id": "te1"}]))
    client = ClockifyClient(config)
    result = await time_entries.list_time_entries(
        client,
        user_id="u1",
        description="standup",
        start="2021-01-01T00:00:00Z",
        end="2021-01-31T23:59:59Z",
        project="p1",
        task="t1",
        tags=["g1", "g2"],
        project_required=True,
        task_required=False,
        hydrated=True,
        in_progress=False,
        page=2,
        page_size=20,
    )
    assert result == [{"id": "te1"}]
    params = route.calls.last.request.url.params
    assert params["description"] == "standup"
    assert params["start"] == "2021-01-01T00:00:00Z"
    assert params["end"] == "2021-01-31T23:59:59Z"
    assert params["project"] == "p1"
    assert params["task"] == "t1"
    assert params["project-required"] == "true"
    assert params["task-required"] == "false"
    assert params["hydrated"] == "true"
    assert params["in-progress"] == "false"
    assert params["page"] == "2"
    assert params["page-size"] == "20"
    assert params.get_list("tags") == ["g1", "g2"]
    await client.aclose()


@respx.mock
async def test_get_time_entry_passes_hydrated(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-entries/te1"
    ).mock(return_value=httpx.Response(200, json={"id": "te1"}))
    client = ClockifyClient(config)
    assert await time_entries.get_time_entry(
        client, time_entry_id="te1", hydrated=True
    ) == {"id": "te1"}
    assert dict(route.calls.last.request.url.params)["hydrated"] == "true"
    await client.aclose()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_mcp.domains.time_entries'`.

- [ ] **Step 3: Write the domain module**

Create `src/clockify_mcp/domains/time_entries.py`:

```python
"""Time entries domain (read)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_time_entries(
    client: ClockifyClient,
    *,
    user_id: str,
    workspace_id: str | None = None,
    description: str | None = None,
    start: str | None = None,
    end: str | None = None,
    project: str | None = None,
    task: str | None = None,
    tags: list[str] | None = None,
    project_required: bool | None = None,
    task_required: bool | None = None,
    hydrated: bool | None = None,
    in_progress: bool | None = None,
    get_week_before: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List a user's time entries on the workspace (paginated).

    Resolve user_id with get_current_user or list_users first. start/end are
    ISO-8601 datetimes with offset (e.g. 2021-01-01T00:00:00Z). project/task filter
    by a single id; tags is a list of tag ids. hydrated=True expands project/task/tag
    objects; in_progress=True returns only the running entry. get_week_before is an
    ISO-8601 datetime that returns the entries of the week before it.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "description": description,
        "start": start,
        "end": end,
        "project": project,
        "task": task,
        "tags": tags,
        "project-required": project_required,
        "task-required": task_required,
        "hydrated": hydrated,
        "in-progress": in_progress,
        "get-week-before": get_week_before,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/user/{user_id}/time-entries", params=params)


async def get_time_entry(
    client: ClockifyClient,
    *,
    time_entry_id: str,
    workspace_id: str | None = None,
    hydrated: bool | None = None,
) -> Any:
    """Get a single time entry by id. hydrated=True expands project/task/tag objects."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"hydrated": hydrated}
    return await client.get(f"workspaces/{ws}/time-entries/{time_entry_id}", params=params)


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_time_entries(
        user_id: str,
        workspace_id: str | None = None,
        description: str | None = None,
        start: str | None = None,
        end: str | None = None,
        project: str | None = None,
        task: str | None = None,
        tags: list[str] | None = None,
        project_required: bool | None = None,
        task_required: bool | None = None,
        hydrated: bool | None = None,
        in_progress: bool | None = None,
        get_week_before: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List a user's time entries on the workspace (paginated)."""
        return await list_time_entries_fn(
            client,
            user_id=user_id,
            workspace_id=workspace_id,
            description=description,
            start=start,
            end=end,
            project=project,
            task=task,
            tags=tags,
            project_required=project_required,
            task_required=task_required,
            hydrated=hydrated,
            in_progress=in_progress,
            get_week_before=get_week_before,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_time_entry(
        time_entry_id: str,
        workspace_id: str | None = None,
        hydrated: bool | None = None,
    ) -> Any:
        """Get a single time entry by id."""
        return await get_time_entry_fn(
            client,
            time_entry_id=time_entry_id,
            workspace_id=workspace_id,
            hydrated=hydrated,
        )


list_time_entries_fn = list_time_entries
get_time_entry_fn = get_time_entry
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 5: Register the domain in the server**

In `src/clockify_mcp/server.py`, update the domains import (keep alphabetical):

```python
from .domains import clients, groups, projects, tags, tasks, time_entries, users, workspaces
```

Add the register call after the existing `tasks.register(mcp, client)` line (before `return mcp`):

```python
    tasks.register(mcp, client)
    time_entries.register(mcp, client)
    return mcp
```

- [ ] **Step 6: Extend the server registration test**

In `tests/test_server.py`, inside `test_build_server_registers_discovery_tools`, add to the `{ ... } <= names` set literal:

```python
        "list_time_entries",
        "get_time_entry",
```

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all tests pass (37 passed) and ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/domains/time_entries.py tests/test_time_entries.py src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: time_entries domain (list by user, get)"
```

---

## Task 2: Reports domain

**Files:**
- Create: `src/clockify_mcp/domains/reports.py`
- Test: `tests/test_reports.py`
- Modify: `src/clockify_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing unit test**

Create `tests/test_reports.py`:

```python
import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import reports


def _sent_body(route):
    return json.loads(route.calls.last.request.content)


@respx.mock
async def test_detailed_report_builds_body(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/detailed"
    ).mock(return_value=httpx.Response(200, json={"timeentries": []}))
    client = ClockifyClient(config)
    result = await reports.generate_detailed_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
        page=1,
        page_size=50,
        sort_column="DATE",
    )
    assert result == {"timeentries": []}
    body = _sent_body(route)
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert body["dateRangeEnd"] == "2021-01-31T23:59:59Z"
    assert body["detailedFilter"] == {"page": 1, "pageSize": 50, "sortColumn": "DATE"}
    await client.aclose()


@respx.mock
async def test_summary_report_defaults_groups(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/summary"
    ).mock(return_value=httpx.Response(200, json={"groupOne": []}))
    client = ClockifyClient(config)
    result = await reports.generate_summary_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
    )
    assert result == {"groupOne": []}
    body = _sent_body(route)
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert body["summaryFilter"] == {"groups": ["PROJECT"]}
    await client.aclose()


@respx.mock
async def test_summary_report_custom_groups(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/summary"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config)
    await reports.generate_summary_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
        groups=["USER", "DATE"],
        sort_column="DURATION",
    )
    body = _sent_body(route)
    assert body["summaryFilter"] == {"groups": ["USER", "DATE"], "sortColumn": "DURATION"}
    await client.aclose()


@respx.mock
async def test_weekly_report_defaults(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/weekly"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config)
    await reports.generate_weekly_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-07T23:59:59Z",
    )
    body = _sent_body(route)
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert body["weeklyFilter"] == {"group": "USER", "subgroup": "TIME"}
    await client.aclose()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_reports.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_mcp.domains.reports'`.

- [ ] **Step 3: Write the domain module**

Create `src/clockify_mcp/domains/reports.py`:

```python
"""Reports domain (read). Reports POST a filter body to the Reports API host."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}


async def generate_detailed_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    sort_column: str | None = None,
) -> Any:
    """Generate a detailed report (one row per time entry) for a date range.

    date_range_start/end are ISO-8601 datetimes with offset (e.g.
    2021-01-01T00:00:00Z). sort_column is one of ID, DESCRIPTION, USER, DURATION,
    DATE, ZONED_DATE, NATURAL, USER_DATE. Use page/page_size for large ranges.
    """
    ws = resolve_workspace_id(client, workspace_id)
    detailed_filter = _drop_none(
        {"page": page, "pageSize": page_size, "sortColumn": sort_column}
    )
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "detailedFilter": detailed_filter,
    }
    return await client.report(f"workspaces/{ws}/reports/detailed", body)


async def generate_summary_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    groups: list[str] | None = None,
    sort_column: str | None = None,
) -> Any:
    """Generate a summary report (totals grouped by one or more keys) for a date range.

    groups are grouping keys applied in order, e.g. PROJECT, CLIENT, USER, TASK, TAG,
    DATE; defaults to ["PROJECT"]. sort_column is one of GROUP, DURATION, AMOUNT,
    EARNED, COST, PROFIT.
    """
    ws = resolve_workspace_id(client, workspace_id)
    summary_filter = _drop_none(
        {"groups": groups if groups is not None else ["PROJECT"], "sortColumn": sort_column}
    )
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "summaryFilter": summary_filter,
    }
    return await client.report(f"workspaces/{ws}/reports/summary", body)


async def generate_weekly_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    group: str | None = None,
    subgroup: str | None = None,
) -> Any:
    """Generate a weekly report for a date range.

    group/subgroup control the breakdown; common values are group="USER" and
    subgroup="TIME" (the defaults when omitted).
    """
    ws = resolve_workspace_id(client, workspace_id)
    weekly_filter = {
        "group": group if group is not None else "USER",
        "subgroup": subgroup if subgroup is not None else "TIME",
    }
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "weeklyFilter": weekly_filter,
    }
    return await client.report(f"workspaces/{ws}/reports/weekly", body)


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def generate_detailed_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        sort_column: str | None = None,
    ) -> Any:
        """Generate a detailed report (one row per time entry) for a date range."""
        return await generate_detailed_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
        )

    @mcp.tool()
    async def generate_summary_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        groups: list[str] | None = None,
        sort_column: str | None = None,
    ) -> Any:
        """Generate a summary report (totals grouped by one or more keys) for a date range."""
        return await generate_summary_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            groups=groups,
            sort_column=sort_column,
        )

    @mcp.tool()
    async def generate_weekly_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        group: str | None = None,
        subgroup: str | None = None,
    ) -> Any:
        """Generate a weekly report for a date range."""
        return await generate_weekly_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            group=group,
            subgroup=subgroup,
        )


generate_detailed_report_fn = generate_detailed_report
generate_summary_report_fn = generate_summary_report
generate_weekly_report_fn = generate_weekly_report
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `uv run pytest tests/test_reports.py -q`
Expected: PASS — 4 passed.

- [ ] **Step 5: Register the domain in the server**

In `src/clockify_mcp/server.py`, update the domains import (keep alphabetical — `reports` sorts before `tags`):

```python
from .domains import (
    clients,
    groups,
    projects,
    reports,
    tags,
    tasks,
    time_entries,
    users,
    workspaces,
)
```

Add the register call after the existing `time_entries.register(mcp, client)` line (before `return mcp`):

```python
    time_entries.register(mcp, client)
    reports.register(mcp, client)
    return mcp
```

- [ ] **Step 6: Extend the server registration test**

In `tests/test_server.py`, inside `test_build_server_registers_discovery_tools`, add to the `{ ... } <= names` set literal:

```python
        "generate_detailed_report",
        "generate_summary_report",
        "generate_weekly_report",
```

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all tests pass (41 passed) and ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/domains/reports.py tests/test_reports.py src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: reports domain (detailed/summary/weekly)"
```

---

## Task 3: Docs update + final verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the README tool table**

In `README.md`:
- Line 5 (description): append `, time entries, and reports` so it reads "...clients, projects, tasks, tags, time entries, and reports as ... tools" (keep the markdown link intact).
- "What can it do?" line: change `**15 read-only tools** are available today (Phase 0–2).` to `**20 read-only tools** are available today (Phase 0–3).`
- Append two rows to the tools table (after the existing `**Tags**` row, identical format):

```markdown
| **Time entries** | 2 | `list_time_entries`, `get_time_entry` |
| **Reports** | 3 | `generate_detailed_report`, `generate_summary_report`, `generate_weekly_report` |
```

- The blockquote `> More domains (time entries, reports, time off, expenses, etc.) land in later phases.` → `> More domains (time off, holidays, expenses, approvals, etc.) land in later phases.`
- In the "Notes" section, change `All 15 tools are read-only` → `All 20 tools are read-only`.

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`:
- "Project Overview" → change `Current phase: **Phase 0–2** — 15 read-only tools across 7 domains (Workspaces, Users, Groups, Clients, Projects, Tasks, Tags).` to `Current phase: **Phase 0–3** — 20 read-only tools across 9 domains (Workspaces, Users, Groups, Clients, Projects, Tasks, Tags, Time entries, Reports).` (Keep the rest of the paragraph intact.)
- Under "Key modules", after the `domains/tags.py` line add:

```markdown
- `domains/time_entries.py` — `list_time_entries`, `get_time_entry`
- `domains/reports.py` — `generate_detailed_report`, `generate_summary_report`, `generate_weekly_report` (POST to the Reports host via `client.report`)
```

- In "Development Conventions", change `expect 35 passed` to the actual final count printed in Step 3.

- [ ] **Step 3: Run the full suite and lint one last time**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: 41 passed, ruff clean. Note the exact passed count and ensure CLAUDE.md (Step 2) matches it.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document Phase 3 time_entries + reports tools"
```

---

## Self-Review

**Spec coverage** (design §7 Phase 3 row — `time_entries` read + `reports` detailed/summary/weekly):
- time_entries: `list_time_entries` (by user), `get_time_entry` → Task 1 ✓
- reports: `generate_detailed_report`, `generate_summary_report`, `generate_weekly_report` → Task 2 ✓
- All registered + discoverable (server test) and documented (Task 3) ✓
- Reports use `client.report` (Reports host) per design §3 "dual-host client"; time entries use `client.get` with `page_params` + `resolve_workspace_id` ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output. ✓

**Type consistency:** Module-level fns and their `@mcp.tool()` wrappers share identical signatures per domain; `*_fn` aliases match the module-level names; `user_id`/`time_entry_id`/`date_range_start`/`date_range_end` naming consistent across functions and tests. Time-entry query-param keys are hyphenated (`project-required`, `task-required`, `in-progress`, `get-week-before`, `page-size`); report body keys are camelCase (`dateRangeStart`, `detailedFilter`, `pageSize`, `summaryFilter`, `weeklyFilter`) — matching the verified spec. ✓

**Out of scope (this phase):** No time-entry write tools (create/update/delete/duplicate) — Phase 4, gated by `CLOCKIFY_ENABLE_WRITES`. No attendance/expense reports, no shared-reports CRUD. No `fetch_all` auto-pagination.
