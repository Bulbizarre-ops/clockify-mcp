# Phase 4 — Core Writes (opt-in) + Live Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in write tools (create/update/delete + time-entry duplicate/bulk) for clients, projects, tasks, tags, and time entries — registered only when `CLOCKIFY_ENABLE_WRITES=true` — plus a gated live smoke-test suite that exercises real round-trips.

**Architecture:** Each domain module gains a `_register_writes(mcp, client)` function that defines the write `@mcp.tool()`s; the existing `register()` calls it only when `client.writes_enabled`. Module-level write async fns (testable directly) sit alongside the read fns, with `*_fn` aliases at the bottom. Write bodies are JSON in camelCase, built with a new shared `bodies.drop_none()` helper. A gated `tests/test_live_smoke.py` performs create→update→delete round-trips against a real workspace.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx + pytest-asyncio, `uv`, ruff.

---

## Background — verified API facts

All paths and request-body field names verified against the live Clockify OpenAPI spec (`https://docs.clockify.me/`) on 2026-06-06. **Write request bodies are JSON in camelCase** (e.g. `clientId`, `projectId`, `tagIds`, `isPublic`) — do not hyphenate. Drop `None` keys before sending. Endpoints (regular host, via `client.post/put/delete`):

| Tool | Method + path | Body fields exposed |
|---|---|---|
| `create_client` | POST `workspaces/{ws}/clients` | `name`*, `email`, `address`, `note` |
| `update_client` | PUT `workspaces/{ws}/clients/{client_id}` | `name`, `email`, `address`, `note`, `archived` |
| `delete_client` | DELETE `workspaces/{ws}/clients/{client_id}` | — |
| `create_project` | POST `workspaces/{ws}/projects` | `name`*, `clientId`, `color`, `note`, `billable`, `isPublic` |
| `update_project` | PUT `workspaces/{ws}/projects/{project_id}` | `name`, `clientId`, `color`, `note`, `billable`, `isPublic`, `archived` |
| `delete_project` | DELETE `workspaces/{ws}/projects/{project_id}` | — |
| `create_task` | POST `workspaces/{ws}/projects/{project_id}/tasks` | `name`*, `assigneeIds`, `estimate`, `status` |
| `update_task` | PUT `workspaces/{ws}/projects/{project_id}/tasks/{task_id}` | `name`*, `assigneeIds`, `estimate`, `status`, `billable` |
| `delete_task` | DELETE `workspaces/{ws}/projects/{project_id}/tasks/{task_id}` | — |
| `create_tag` | POST `workspaces/{ws}/tags` | `name`* |
| `update_tag` | PUT `workspaces/{ws}/tags/{tag_id}` | `name`, `archived` |
| `delete_tag` | DELETE `workspaces/{ws}/tags/{tag_id}` | — |
| `create_time_entry` | POST `workspaces/{ws}/time-entries` | `start`*, `end`, `description`, `projectId`, `taskId`, `tagIds`, `billable`, `type` |
| `update_time_entry` | PUT `workspaces/{ws}/time-entries/{time_entry_id}` | `start`*, `end`, `description`, `projectId`, `taskId`, `tagIds`, `billable`, `type` |
| `delete_time_entry` | DELETE `workspaces/{ws}/time-entries/{time_entry_id}` | — |
| `duplicate_time_entry` | POST `workspaces/{ws}/user/{user_id}/time-entries/{time_entry_id}/duplicate` | — (no body) |
| `bulk_update_time_entries` | PUT `workspaces/{ws}/user/{user_id}/time-entries` | JSON **array** of entry objects, each `{id*, …}` |

Enums: task `status` ∈ `ACTIVE, DONE` (the API also lists `ALL` for filtering); time-entry `type` ∈ `REGULAR, BREAK`. `start`/`end` are ISO-8601 datetimes with offset (e.g. `2021-01-01T09:00:00Z`). `create_time_entry` with only `start` (no `end`) starts a running timer; with both it records a finished entry. `name` is required by the API for client/project/task/tag creation even though the OpenAPI schema doesn't always flag it — make it a required tool parameter.

### Gating pattern (verified against current code)
- `ClockifyClient` exposes `writes_enabled` (reads `config.enable_writes`). Config sets it from `CLOCKIFY_ENABLE_WRITES` / `enable_writes` (TOML). The `config_writes` pytest fixture (tests/conftest.py) already provides an enabled config with workspace `ws1`.
- Each domain's `register()` currently registers reads. Add at the end: `if client.writes_enabled: _register_writes(mcp, client)`.
- `client.post(path, json=...)`, `client.put(path, json=...)`, `client.delete(path)` already exist and return parsed JSON (or `None` on empty body). `client._clean` drops `None` from query params only — request bodies must be cleaned by the domain via `bodies.drop_none()`.

**Baseline:** `uv run pytest -q` currently reports **41 passed**.

---

## File Structure

- Create: `src/clockify_mcp/bodies.py` — `drop_none()` shared request-body helper
- Modify: `src/clockify_mcp/domains/clients.py`, `projects.py`, `tasks.py`, `tags.py`, `time_entries.py` — add write fns + `_register_writes` + gate
- Modify: `src/clockify_mcp/domains/reports.py` — use shared `drop_none` (remove its local copy)
- Modify: `tests/test_clients.py`, `test_projects.py`, `test_tasks.py`, `test_tags.py`, `test_time_entries.py` — add write tests (use `config_writes` where building a client, or call the module fns directly with any client)
- Modify: `tests/test_server.py` — assert writes gated off by default and on when enabled
- Create: `tests/test_live_smoke.py` — gated real round-trips
- Modify: `README.md`, `CLAUDE.md` — document write tools + the `CLOCKIFY_ENABLE_WRITES` opt-in

Each task leaves the server shippable (reads always work; writes appear only when enabled).

---

## Task 1: Shared body helper + clients writes + gate pattern

**Files:**
- Create: `src/clockify_mcp/bodies.py`
- Modify: `src/clockify_mcp/domains/clients.py`, `src/clockify_mcp/domains/reports.py`
- Modify: `tests/test_clients.py`, `tests/test_server.py`

- [ ] **Step 1: Create the shared helper**

Create `src/clockify_mcp/bodies.py`:

```python
"""Helpers for building JSON request bodies for write endpoints."""

from __future__ import annotations

from typing import Any


def drop_none(values: dict[str, Any]) -> dict[str, Any]:
    """Return values without keys whose value is None.

    Clockify write bodies are JSON; omit unset fields rather than sending null.
    """
    return {k: v for k, v in values.items() if v is not None}
```

- [ ] **Step 2: Point reports.py at the shared helper**

In `src/clockify_mcp/domains/reports.py`, remove the local `_drop_none` function and import the shared one. Change the import block to add:

```python
from ..bodies import drop_none
```

Delete the `def _drop_none(...)` definition, and replace the two `_drop_none(` call sites with `drop_none(`.

- [ ] **Step 3: Write the failing clients write tests**

Append to `tests/test_clients.py`:

```python
import json


@respx.mock
async def test_create_client_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/clients").mock(
        return_value=httpx.Response(201, json={"id": "c1", "name": "Acme"})
    )
    client = ClockifyClient(config_writes)
    result = await clients.create_client(client, name="Acme", email="a@b.com")
    assert result == {"id": "c1", "name": "Acme"}
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Acme", "email": "a@b.com"}
    await client.aclose()


@respx.mock
async def test_update_client_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(200, json={"id": "c1"})
    )
    client = ClockifyClient(config_writes)
    await clients.update_client(client, client_id="c1", name="New", archived=True)
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "New", "archived": True}
    await client.aclose()


@respx.mock
async def test_delete_client(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(200, json={"id": "c1"})
    )
    client = ClockifyClient(config_writes)
    assert await clients.delete_client(client, client_id="c1") == {"id": "c1"}
    assert route.called
    await client.aclose()
```

- [ ] **Step 4: Run to verify failure**

Run: `uv run pytest tests/test_clients.py -q`
Expected: FAIL — `AttributeError: module 'clockify_mcp.domains.clients' has no attribute 'create_client'`.

- [ ] **Step 5: Implement clients writes + gate**

In `src/clockify_mcp/domains/clients.py`, add the import near the top (after the existing `from ..pagination import page_params` line):

```python
from ..bodies import drop_none
```

Add these three module-level async functions after the existing `get_client` function (before `def register`):

```python
async def create_client(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    email: str | None = None,
    address: str | None = None,
    note: str | None = None,
) -> Any:
    """Create a client on the workspace."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"name": name, "email": email, "address": address, "note": note})
    return await client.post(f"workspaces/{ws}/clients", json=body)


async def update_client(
    client: ClockifyClient,
    *,
    client_id: str,
    workspace_id: str | None = None,
    name: str | None = None,
    email: str | None = None,
    address: str | None = None,
    note: str | None = None,
    archived: bool | None = None,
) -> Any:
    """Update a client. Pass archived=True/False to archive or restore it."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "email": email,
            "address": address,
            "note": note,
            "archived": archived,
        }
    )
    return await client.put(f"workspaces/{ws}/clients/{client_id}", json=body)


async def delete_client(
    client: ClockifyClient, *, client_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a client. IRREVERSIBLE — the client is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/clients/{client_id}")
```

In the existing `register()` function, add a gated call at the very end of the function body (after the last read `@mcp.tool()` definition, still inside `register`):

```python
    if client.writes_enabled:
        _register_writes(mcp, client)
```

Add a new `_register_writes` function after `register()`:

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_client(
        name: str,
        workspace_id: str | None = None,
        email: str | None = None,
        address: str | None = None,
        note: str | None = None,
    ) -> Any:
        """Create a client on the workspace."""
        return await create_client_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            email=email,
            address=address,
            note=note,
        )

    @mcp.tool()
    async def update_client(
        client_id: str,
        workspace_id: str | None = None,
        name: str | None = None,
        email: str | None = None,
        address: str | None = None,
        note: str | None = None,
        archived: bool | None = None,
    ) -> Any:
        """Update a client. Pass archived=True/False to archive or restore it."""
        return await update_client_fn(
            client,
            client_id=client_id,
            workspace_id=workspace_id,
            name=name,
            email=email,
            address=address,
            note=note,
            archived=archived,
        )

    @mcp.tool()
    async def delete_client(client_id: str, workspace_id: str | None = None) -> Any:
        """Delete a client. IRREVERSIBLE — the client is permanently removed."""
        return await delete_client_fn(client, client_id=client_id, workspace_id=workspace_id)
```

Add the alias lines at the very bottom of the file (next to the existing `list_clients_fn`/`get_client_fn` aliases):

```python
create_client_fn = create_client
update_client_fn = update_client
delete_client_fn = delete_client
```

- [ ] **Step 6: Run the clients tests**

Run: `uv run pytest tests/test_clients.py -q`
Expected: PASS — 5 passed (2 read + 3 write).

- [ ] **Step 7: Add the server gating tests**

In `tests/test_server.py`, append two tests:

```python
async def test_writes_not_registered_by_default(config):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server

    client = ClockifyClient(config)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert "create_client" not in names
    assert "delete_client" not in names


async def test_writes_registered_when_enabled(config_writes):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server

    client = ClockifyClient(config_writes)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert {"create_client", "update_client", "delete_client"} <= names
```

- [ ] **Step 8: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (48 passed) and ruff clean.

- [ ] **Step 9: Commit**

```bash
git add src/clockify_mcp/bodies.py src/clockify_mcp/domains/clients.py src/clockify_mcp/domains/reports.py tests/test_clients.py tests/test_server.py
git commit -m "feat: clients write tools (create/update/delete), gated by CLOCKIFY_ENABLE_WRITES"
```

---

## Task 2: Projects writes

**Files:**
- Modify: `src/clockify_mcp/domains/projects.py`
- Modify: `tests/test_projects.py`, `tests/test_server.py`

- [ ] **Step 1: Write the failing projects write tests**

Append to `tests/test_projects.py`:

```python
import json


@respx.mock
async def test_create_project_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/projects").mock(
        return_value=httpx.Response(201, json={"id": "p1"})
    )
    client = ClockifyClient(config_writes)
    await projects.create_project(
        client, name="Site", client_id="c1", billable=True, is_public=False
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Site", "clientId": "c1", "billable": True, "isPublic": False}
    await client.aclose()


@respx.mock
async def test_update_project_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/projects/p1").mock(
        return_value=httpx.Response(200, json={"id": "p1"})
    )
    client = ClockifyClient(config_writes)
    await projects.update_project(client, project_id="p1", name="New", archived=True)
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "New", "archived": True}
    await client.aclose()


@respx.mock
async def test_delete_project(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/projects/p1").mock(
        return_value=httpx.Response(200, json={"id": "p1"})
    )
    client = ClockifyClient(config_writes)
    assert await projects.delete_project(client, project_id="p1") == {"id": "p1"}
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_projects.py -q`
Expected: FAIL — `AttributeError: module 'clockify_mcp.domains.projects' has no attribute 'create_project'`.

- [ ] **Step 3: Implement projects writes + gate**

In `src/clockify_mcp/domains/projects.py`, add after the existing `from ..pagination import page_params` line:

```python
from ..bodies import drop_none
```

Add these module-level async functions after `get_project` (before `def register`):

```python
async def create_project(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    client_id: str | None = None,
    color: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    is_public: bool | None = None,
) -> Any:
    """Create a project on the workspace. client_id links it to a client."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "clientId": client_id,
            "color": color,
            "note": note,
            "billable": billable,
            "isPublic": is_public,
        }
    )
    return await client.post(f"workspaces/{ws}/projects", json=body)


async def update_project(
    client: ClockifyClient,
    *,
    project_id: str,
    workspace_id: str | None = None,
    name: str | None = None,
    client_id: str | None = None,
    color: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    is_public: bool | None = None,
    archived: bool | None = None,
) -> Any:
    """Update a project. Pass archived=True/False to archive or restore it."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "clientId": client_id,
            "color": color,
            "note": note,
            "billable": billable,
            "isPublic": is_public,
            "archived": archived,
        }
    )
    return await client.put(f"workspaces/{ws}/projects/{project_id}", json=body)


async def delete_project(
    client: ClockifyClient, *, project_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a project. IRREVERSIBLE — the project and its tasks are removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/projects/{project_id}")
```

In `register()`, add at the end of the function body:

```python
    if client.writes_enabled:
        _register_writes(mcp, client)
```

Add `_register_writes` after `register()`:

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_project(
        name: str,
        workspace_id: str | None = None,
        client_id: str | None = None,
        color: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        is_public: bool | None = None,
    ) -> Any:
        """Create a project on the workspace. client_id links it to a client."""
        return await create_project_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            client_id=client_id,
            color=color,
            note=note,
            billable=billable,
            is_public=is_public,
        )

    @mcp.tool()
    async def update_project(
        project_id: str,
        workspace_id: str | None = None,
        name: str | None = None,
        client_id: str | None = None,
        color: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        is_public: bool | None = None,
        archived: bool | None = None,
    ) -> Any:
        """Update a project. Pass archived=True/False to archive or restore it."""
        return await update_project_fn(
            client,
            project_id=project_id,
            workspace_id=workspace_id,
            name=name,
            client_id=client_id,
            color=color,
            note=note,
            billable=billable,
            is_public=is_public,
            archived=archived,
        )

    @mcp.tool()
    async def delete_project(project_id: str, workspace_id: str | None = None) -> Any:
        """Delete a project. IRREVERSIBLE — the project and its tasks are removed."""
        return await delete_project_fn(
            client, project_id=project_id, workspace_id=workspace_id
        )
```

Add aliases at the bottom (next to existing `list_projects_fn`/`get_project_fn`):

```python
create_project_fn = create_project
update_project_fn = update_project
delete_project_fn = delete_project
```

- [ ] **Step 4: Run the projects tests**

Run: `uv run pytest tests/test_projects.py -q`
Expected: PASS — 5 passed.

- [ ] **Step 5: Extend the server enabled-writes assertion**

In `tests/test_server.py`, in `test_writes_registered_when_enabled`, extend the asserted set:

```python
    assert {
        "create_client", "update_client", "delete_client",
        "create_project", "update_project", "delete_project",
    } <= names
```

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (51 passed) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/projects.py tests/test_projects.py tests/test_server.py
git commit -m "feat: projects write tools (create/update/delete)"
```

---

## Task 3: Tasks writes

**Files:**
- Modify: `src/clockify_mcp/domains/tasks.py`
- Modify: `tests/test_tasks.py`, `tests/test_server.py`

- [ ] **Step 1: Write the failing tasks write tests**

Append to `tests/test_tasks.py`:

```python
import json


@respx.mock
async def test_create_task_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks"
    ).mock(return_value=httpx.Response(201, json={"id": "t1"}))
    client = ClockifyClient(config_writes)
    await tasks.create_task(
        client, project_id="p1", name="Design", assignee_ids=["u1"], status="ACTIVE"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Design", "assigneeIds": ["u1"], "status": "ACTIVE"}
    await client.aclose()


@respx.mock
async def test_update_task_builds_body(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks/t1"
    ).mock(return_value=httpx.Response(200, json={"id": "t1"}))
    client = ClockifyClient(config_writes)
    await tasks.update_task(
        client, project_id="p1", task_id="t1", name="Done", status="DONE", billable=False
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Done", "status": "DONE", "billable": False}
    await client.aclose()


@respx.mock
async def test_delete_task(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks/t1"
    ).mock(return_value=httpx.Response(200, json={"id": "t1"}))
    client = ClockifyClient(config_writes)
    assert await tasks.delete_task(client, project_id="p1", task_id="t1") == {"id": "t1"}
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tasks.py -q`
Expected: FAIL — `AttributeError: module 'clockify_mcp.domains.tasks' has no attribute 'create_task'`.

- [ ] **Step 3: Implement tasks writes + gate**

In `src/clockify_mcp/domains/tasks.py`, add after `from ..pagination import page_params`:

```python
from ..bodies import drop_none
```

Add module-level async functions after `get_task` (before `def register`):

```python
async def create_task(
    client: ClockifyClient,
    *,
    project_id: str,
    name: str,
    workspace_id: str | None = None,
    assignee_ids: list[str] | None = None,
    estimate: str | None = None,
    status: str | None = None,
) -> Any:
    """Create a task on a project. status is ACTIVE or DONE; estimate is an
    ISO-8601 duration (e.g. PT1H30M)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "assigneeIds": assignee_ids,
            "estimate": estimate,
            "status": status,
        }
    )
    return await client.post(f"workspaces/{ws}/projects/{project_id}/tasks", json=body)


async def update_task(
    client: ClockifyClient,
    *,
    project_id: str,
    task_id: str,
    name: str,
    workspace_id: str | None = None,
    assignee_ids: list[str] | None = None,
    estimate: str | None = None,
    status: str | None = None,
    billable: bool | None = None,
) -> Any:
    """Update a task. name is required by the API. status is ACTIVE or DONE."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "assigneeIds": assignee_ids,
            "estimate": estimate,
            "status": status,
            "billable": billable,
        }
    )
    return await client.put(
        f"workspaces/{ws}/projects/{project_id}/tasks/{task_id}", json=body
    )


async def delete_task(
    client: ClockifyClient,
    *,
    project_id: str,
    task_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Delete a task. IRREVERSIBLE — the task is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/projects/{project_id}/tasks/{task_id}")
```

In `register()`, add at the end:

```python
    if client.writes_enabled:
        _register_writes(mcp, client)
```

Add `_register_writes` after `register()`:

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_task(
        project_id: str,
        name: str,
        workspace_id: str | None = None,
        assignee_ids: list[str] | None = None,
        estimate: str | None = None,
        status: str | None = None,
    ) -> Any:
        """Create a task on a project. status is ACTIVE or DONE."""
        return await create_task_fn(
            client,
            project_id=project_id,
            name=name,
            workspace_id=workspace_id,
            assignee_ids=assignee_ids,
            estimate=estimate,
            status=status,
        )

    @mcp.tool()
    async def update_task(
        project_id: str,
        task_id: str,
        name: str,
        workspace_id: str | None = None,
        assignee_ids: list[str] | None = None,
        estimate: str | None = None,
        status: str | None = None,
        billable: bool | None = None,
    ) -> Any:
        """Update a task. name is required by the API. status is ACTIVE or DONE."""
        return await update_task_fn(
            client,
            project_id=project_id,
            task_id=task_id,
            name=name,
            workspace_id=workspace_id,
            assignee_ids=assignee_ids,
            estimate=estimate,
            status=status,
            billable=billable,
        )

    @mcp.tool()
    async def delete_task(
        project_id: str, task_id: str, workspace_id: str | None = None
    ) -> Any:
        """Delete a task. IRREVERSIBLE — the task is permanently removed."""
        return await delete_task_fn(
            client, project_id=project_id, task_id=task_id, workspace_id=workspace_id
        )
```

Add aliases at the bottom:

```python
create_task_fn = create_task
update_task_fn = update_task
delete_task_fn = delete_task
```

- [ ] **Step 4: Run the tasks tests**

Run: `uv run pytest tests/test_tasks.py -q`
Expected: PASS — 5 passed.

- [ ] **Step 5: Extend the server enabled-writes assertion**

In `tests/test_server.py`, in `test_writes_registered_when_enabled`, add to the asserted set:

```python
        "create_task", "update_task", "delete_task",
```

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (54 passed) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/tasks.py tests/test_tasks.py tests/test_server.py
git commit -m "feat: tasks write tools (create/update/delete)"
```

---

## Task 4: Tags writes

**Files:**
- Modify: `src/clockify_mcp/domains/tags.py`
- Modify: `tests/test_tags.py`, `tests/test_server.py`

- [ ] **Step 1: Write the failing tags write tests**

Append to `tests/test_tags.py`:

```python
import json


@respx.mock
async def test_create_tag_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/tags").mock(
        return_value=httpx.Response(201, json={"id": "g1", "name": "Billable"})
    )
    client = ClockifyClient(config_writes)
    result = await tags.create_tag(client, name="Billable")
    assert result == {"id": "g1", "name": "Billable"}
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Billable"}
    await client.aclose()


@respx.mock
async def test_update_tag_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/tags/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1"})
    )
    client = ClockifyClient(config_writes)
    await tags.update_tag(client, tag_id="g1", name="New", archived=True)
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "New", "archived": True}
    await client.aclose()


@respx.mock
async def test_delete_tag(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/tags/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1"})
    )
    client = ClockifyClient(config_writes)
    assert await tags.delete_tag(client, tag_id="g1") == {"id": "g1"}
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tags.py -q`
Expected: FAIL — `AttributeError: module 'clockify_mcp.domains.tags' has no attribute 'create_tag'`.

- [ ] **Step 3: Implement tags writes + gate**

In `src/clockify_mcp/domains/tags.py`, add after `from ..pagination import page_params`:

```python
from ..bodies import drop_none
```

Add module-level async functions after `get_tag` (before `def register`):

```python
async def create_tag(
    client: ClockifyClient, *, name: str, workspace_id: str | None = None
) -> Any:
    """Create a tag on the workspace."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"name": name})
    return await client.post(f"workspaces/{ws}/tags", json=body)


async def update_tag(
    client: ClockifyClient,
    *,
    tag_id: str,
    workspace_id: str | None = None,
    name: str | None = None,
    archived: bool | None = None,
) -> Any:
    """Update a tag. Pass archived=True/False to archive or restore it."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"name": name, "archived": archived})
    return await client.put(f"workspaces/{ws}/tags/{tag_id}", json=body)


async def delete_tag(
    client: ClockifyClient, *, tag_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a tag. IRREVERSIBLE — the tag is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/tags/{tag_id}")
```

In `register()`, add at the end:

```python
    if client.writes_enabled:
        _register_writes(mcp, client)
```

Add `_register_writes` after `register()`:

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_tag(name: str, workspace_id: str | None = None) -> Any:
        """Create a tag on the workspace."""
        return await create_tag_fn(client, name=name, workspace_id=workspace_id)

    @mcp.tool()
    async def update_tag(
        tag_id: str,
        workspace_id: str | None = None,
        name: str | None = None,
        archived: bool | None = None,
    ) -> Any:
        """Update a tag. Pass archived=True/False to archive or restore it."""
        return await update_tag_fn(
            client, tag_id=tag_id, workspace_id=workspace_id, name=name, archived=archived
        )

    @mcp.tool()
    async def delete_tag(tag_id: str, workspace_id: str | None = None) -> Any:
        """Delete a tag. IRREVERSIBLE — the tag is permanently removed."""
        return await delete_tag_fn(client, tag_id=tag_id, workspace_id=workspace_id)
```

Add aliases at the bottom:

```python
create_tag_fn = create_tag
update_tag_fn = update_tag
delete_tag_fn = delete_tag
```

- [ ] **Step 4: Run the tags tests**

Run: `uv run pytest tests/test_tags.py -q`
Expected: PASS — 5 passed.

- [ ] **Step 5: Extend the server enabled-writes assertion**

In `tests/test_server.py`, in `test_writes_registered_when_enabled`, add to the asserted set:

```python
        "create_tag", "update_tag", "delete_tag",
```

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (57 passed) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/tags.py tests/test_tags.py tests/test_server.py
git commit -m "feat: tags write tools (create/update/delete)"
```

---

## Task 5: Time entries writes (create/update/delete/duplicate/bulk)

**Files:**
- Modify: `src/clockify_mcp/domains/time_entries.py`
- Modify: `tests/test_time_entries.py`, `tests/test_server.py`

- [ ] **Step 1: Write the failing time-entry write tests**

Append to `tests/test_time_entries.py`:

```python
import json


@respx.mock
async def test_create_time_entry_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "te1"})
    )
    client = ClockifyClient(config_writes)
    await time_entries.create_time_entry(
        client,
        start="2021-01-01T09:00:00Z",
        end="2021-01-01T10:00:00Z",
        description="work",
        project_id="p1",
        tag_ids=["g1"],
        billable=True,
        type="REGULAR",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "start": "2021-01-01T09:00:00Z",
        "end": "2021-01-01T10:00:00Z",
        "description": "work",
        "projectId": "p1",
        "tagIds": ["g1"],
        "billable": True,
        "type": "REGULAR",
    }
    await client.aclose()


@respx.mock
async def test_update_time_entry_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/time-entries/te1").mock(
        return_value=httpx.Response(200, json={"id": "te1"})
    )
    client = ClockifyClient(config_writes)
    await time_entries.update_time_entry(
        client, time_entry_id="te1", start="2021-01-01T09:00:00Z", description="edited"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2021-01-01T09:00:00Z", "description": "edited"}
    await client.aclose()


@respx.mock
async def test_delete_time_entry(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-entries/te1"
    ).mock(return_value=httpx.Response(200, json={"id": "te1"}))
    client = ClockifyClient(config_writes)
    assert await time_entries.delete_time_entry(client, time_entry_id="te1") == {"id": "te1"}
    assert route.called
    await client.aclose()


@respx.mock
async def test_duplicate_time_entry(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries/te1/duplicate"
    ).mock(return_value=httpx.Response(201, json={"id": "te2"}))
    client = ClockifyClient(config_writes)
    result = await time_entries.duplicate_time_entry(
        client, user_id="u1", time_entry_id="te1"
    )
    assert result == {"id": "te2"}
    assert route.called
    await client.aclose()


@respx.mock
async def test_bulk_update_time_entries_sends_array(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(200, json=[{"id": "te1"}]))
    client = ClockifyClient(config_writes)
    entries = [{"id": "te1", "description": "a"}, {"id": "te2", "description": "b"}]
    result = await time_entries.bulk_update_time_entries(
        client, user_id="u1", entries=entries
    )
    assert result == [{"id": "te1"}]
    body = json.loads(route.calls.last.request.content)
    assert body == entries
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: FAIL — `AttributeError: module 'clockify_mcp.domains.time_entries' has no attribute 'create_time_entry'`.

- [ ] **Step 3: Implement time-entry writes + gate**

In `src/clockify_mcp/domains/time_entries.py`, add after `from ..pagination import page_params`:

```python
from ..bodies import drop_none
```

Add module-level async functions after `get_time_entry` (before `def register`):

```python
async def create_time_entry(
    client: ClockifyClient,
    *,
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
    """Create a time entry for the authenticated user.

    start (and optional end) are ISO-8601 datetimes with offset (e.g.
    2021-01-01T09:00:00Z). Omit end to start a running timer. type is REGULAR or BREAK.
    """
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
    return await client.post(f"workspaces/{ws}/time-entries", json=body)


async def update_time_entry(
    client: ClockifyClient,
    *,
    time_entry_id: str,
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
    """Update a time entry. start is required by the API even when only editing
    other fields — pass the entry's existing start if you are not changing it."""
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
    return await client.put(f"workspaces/{ws}/time-entries/{time_entry_id}", json=body)


async def delete_time_entry(
    client: ClockifyClient, *, time_entry_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a time entry. IRREVERSIBLE — the entry is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/time-entries/{time_entry_id}")


async def duplicate_time_entry(
    client: ClockifyClient,
    *,
    user_id: str,
    time_entry_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Duplicate a user's time entry. Resolve user_id with get_current_user."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.post(
        f"workspaces/{ws}/user/{user_id}/time-entries/{time_entry_id}/duplicate"
    )


async def bulk_update_time_entries(
    client: ClockifyClient,
    *,
    user_id: str,
    entries: list[dict[str, Any]],
    workspace_id: str | None = None,
) -> Any:
    """Bulk-edit a user's time entries. Each entry dict MUST include its 'id' plus
    the fields to change (camelCase: start, end, description, projectId, taskId,
    tagIds, billable, type). Resolve user_id with get_current_user."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.put(f"workspaces/{ws}/user/{user_id}/time-entries", json=entries)
```

> Note: `client.put` is type-hinted `json: dict | None`, but httpx accepts a JSON array at runtime; `bulk_update_time_entries` deliberately passes a list. This matches the Clockify "bulk edit" endpoint, which expects a top-level JSON array.

In `register()`, add at the end:

```python
    if client.writes_enabled:
        _register_writes(mcp, client)
```

Add `_register_writes` after `register()`:

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_time_entry(
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
        """Create a time entry for the authenticated user. Omit end for a running timer."""
        return await create_time_entry_fn(
            client,
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
    async def update_time_entry(
        time_entry_id: str,
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
        """Update a time entry. start is required by the API (pass the existing start
        if unchanged)."""
        return await update_time_entry_fn(
            client,
            time_entry_id=time_entry_id,
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
    async def delete_time_entry(
        time_entry_id: str, workspace_id: str | None = None
    ) -> Any:
        """Delete a time entry. IRREVERSIBLE — the entry is permanently removed."""
        return await delete_time_entry_fn(
            client, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def duplicate_time_entry(
        user_id: str, time_entry_id: str, workspace_id: str | None = None
    ) -> Any:
        """Duplicate a user's time entry. Resolve user_id with get_current_user."""
        return await duplicate_time_entry_fn(
            client,
            user_id=user_id,
            time_entry_id=time_entry_id,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def bulk_update_time_entries(
        user_id: str,
        entries: list[dict[str, Any]],
        workspace_id: str | None = None,
    ) -> Any:
        """Bulk-edit a user's time entries. Each entry dict MUST include its 'id'."""
        return await bulk_update_time_entries_fn(
            client, user_id=user_id, entries=entries, workspace_id=workspace_id
        )
```

Add aliases at the bottom:

```python
create_time_entry_fn = create_time_entry
update_time_entry_fn = update_time_entry
delete_time_entry_fn = delete_time_entry
duplicate_time_entry_fn = duplicate_time_entry
bulk_update_time_entries_fn = bulk_update_time_entries
```

- [ ] **Step 4: Run the time-entry tests**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: PASS — 7 passed (2 read + 5 write).

- [ ] **Step 5: Extend the server enabled-writes assertion**

In `tests/test_server.py`, in `test_writes_registered_when_enabled`, add to the asserted set:

```python
        "create_time_entry", "update_time_entry", "delete_time_entry",
        "duplicate_time_entry", "bulk_update_time_entries",
```

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (61 passed) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/time_entries.py tests/test_time_entries.py tests/test_server.py
git commit -m "feat: time_entries write tools (create/update/delete/duplicate/bulk)"
```

---

## Task 6: Docs update

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: Update README.md**

- "What can it do?" intro: keep the 20 read-only count, but update the write sentence. Change `Write tools (create/update/delete) are planned for later phases and opt-in via \`CLOCKIFY_ENABLE_WRITES\`.` to: `17 write tools (create/update/delete across clients, projects, tasks, tags, and time entries) register when you set \`CLOCKIFY_ENABLE_WRITES=true\`.`
- Add a new table after the read-only table titled with a bold line `**Write tools (opt-in, \`CLOCKIFY_ENABLE_WRITES=true\`):**` and rows:

```markdown
| Domain | Tools | Tool names |
|--------|------:|------------|
| **Clients** | 3 | `create_client`, `update_client`, `delete_client` |
| **Projects** | 3 | `create_project`, `update_project`, `delete_project` |
| **Tasks** | 3 | `create_task`, `update_task`, `delete_task` |
| **Tags** | 3 | `create_tag`, `update_tag`, `delete_tag` |
| **Time entries** | 5 | `create_time_entry`, `update_time_entry`, `delete_time_entry`, `duplicate_time_entry`, `bulk_update_time_entries` |
```

- In "Notes", change the `**Read-only by default:**` bullet so it reads: `**Read-only by default:** The 20 read tools are always available. Setting \`CLOCKIFY_ENABLE_WRITES=true\` additionally registers 17 write tools; \`delete_*\` tools are irreversible.`

- [ ] **Step 2: Update CLAUDE.md**

- "Project Overview": change `Current phase: **Phase 0–3** — 20 read-only tools across 9 domains (...).` to `Current phase: **Phase 0–4** — 20 read tools + 17 opt-in write tools across 9 domains. Writes (create/update/delete for clients/projects/tasks/tags/time_entries, plus time-entry duplicate/bulk) register only when CLOCKIFY_ENABLE_WRITES=true.` Keep the rest of the paragraph (trim the now-inaccurate "Write tools ... arrive in later phases" clause to "Remaining domains (time off, holidays, expenses, approvals, etc.) arrive in later phases.").
- Under "Key modules", update the clients/projects/tasks/tags/time_entries lines to mention writes, e.g. append ` (+ create/update/delete when writes enabled)` to each of those five lines. Add a line: `- \`bodies.py\` — \`drop_none()\` for building JSON write bodies.`
- In "Architecture", after the read-only sentence, note: write tools register via `_register_writes(mcp, client)` called from each domain's `register()` only when `client.writes_enabled`.
- In "Development Conventions", change `expect 41 passed` to the actual final count from Step 3.

- [ ] **Step 3: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: 61 passed, ruff clean. Set the CLAUDE.md count to the actual number.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document Phase 4 opt-in write tools"
```

---

## Task 7: Live smoke test (gated) — controller runs it

**Files:**
- Create: `tests/test_live_smoke.py`

This suite is **skipped unless** `CLOCKIFY_LIVE_TEST` is set AND a real `CLOCKIFY_API_KEY` is present. It performs create→update→delete round-trips against a real workspace, cleaning up in `finally`. The controller (not a subagent) runs it after the user provides credentials in-session, and selects the target workspace by name.

- [ ] **Step 1: Create the gated live smoke suite**

Create `tests/test_live_smoke.py`:

```python
"""Live smoke tests against a real Clockify workspace.

Skipped unless CLOCKIFY_LIVE_TEST is set and a real CLOCKIFY_API_KEY is present.
Each test creates real data and deletes it again (try/finally cleanup). Names are
prefixed with 'mcp-smoke-' so any leftover artifacts are easy to spot.

Run:
    CLOCKIFY_LIVE_TEST=1 CLOCKIFY_API_KEY=... CLOCKIFY_ENABLE_WRITES=true \
        CLOCKIFY_LIVE_WORKSPACE_NAME="Alan Fuentes's workspace" \
        uv run pytest tests/test_live_smoke.py -q -s
"""

from __future__ import annotations

import os

import pytest

from clockify_mcp.client import ClockifyClient
from clockify_mcp.config import Config
from clockify_mcp.domains import clients, projects, tags, tasks, time_entries, workspaces

pytestmark = pytest.mark.skipif(
    not os.environ.get("CLOCKIFY_LIVE_TEST"),
    reason="set CLOCKIFY_LIVE_TEST=1 (and CLOCKIFY_API_KEY) to run live smoke tests",
)

PREFIX = "mcp-smoke-"


@pytest.fixture
async def live():
    env = dict(os.environ)
    env.setdefault("CLOCKIFY_ENABLE_WRITES", "true")
    config = Config.load(env=env)
    client = ClockifyClient(config)
    # Resolve the target workspace by name if provided, else the user's default.
    me = await workspaces.get_current_user(client)
    ws_id = config.default_workspace_id or me.get("defaultWorkspace") or me.get("activeWorkspace")
    wanted = os.environ.get("CLOCKIFY_LIVE_WORKSPACE_NAME")
    if wanted:
        all_ws = await workspaces.list_workspaces(client)
        match = [w for w in all_ws if w.get("name") == wanted]
        assert match, f"workspace named {wanted!r} not found; have {[w.get('name') for w in all_ws]}"
        ws_id = match[0]["id"]
    assert ws_id, "could not resolve a workspace id"
    yield client, ws_id, me["id"]
    await client.aclose()


async def test_live_client_roundtrip(live):
    client, ws, _ = live
    created = await clients.create_client(client, workspace_id=ws, name=PREFIX + "client")
    cid = created["id"]
    try:
        updated = await clients.update_client(
            client, workspace_id=ws, client_id=cid, note="updated by smoke test"
        )
        assert updated["id"] == cid
        fetched = await clients.get_client(client, workspace_id=ws, client_id=cid)
        assert fetched["id"] == cid
    finally:
        await clients.delete_client(client, workspace_id=ws, client_id=cid)


async def test_live_tag_roundtrip(live):
    client, ws, _ = live
    created = await tags.create_tag(client, workspace_id=ws, name=PREFIX + "tag")
    gid = created["id"]
    try:
        updated = await tags.update_tag(client, workspace_id=ws, tag_id=gid, name=PREFIX + "tag2")
        assert updated["id"] == gid
    finally:
        await tags.delete_tag(client, workspace_id=ws, tag_id=gid)


async def test_live_project_and_task_roundtrip(live):
    client, ws, _ = live
    project = await projects.create_project(client, workspace_id=ws, name=PREFIX + "project")
    pid = project["id"]
    try:
        task = await tasks.create_task(
            client, workspace_id=ws, project_id=pid, name=PREFIX + "task"
        )
        tid = task["id"]
        try:
            done = await tasks.update_task(
                client, workspace_id=ws, project_id=pid, task_id=tid,
                name=PREFIX + "task", status="DONE",
            )
            assert done["id"] == tid
        finally:
            await tasks.delete_task(client, workspace_id=ws, project_id=pid, task_id=tid)
        await projects.update_project(client, workspace_id=ws, project_id=pid, note="smoke")
    finally:
        await projects.delete_project(client, workspace_id=ws, project_id=pid)


async def test_live_time_entry_roundtrip(live):
    client, ws, _ = live
    entry = await time_entries.create_time_entry(
        client,
        workspace_id=ws,
        start="2020-01-01T09:00:00Z",
        end="2020-01-01T10:00:00Z",
        description=PREFIX + "entry",
    )
    eid = entry["id"]
    try:
        updated = await time_entries.update_time_entry(
            client, workspace_id=ws, time_entry_id=eid,
            start="2020-01-01T09:00:00Z", description=PREFIX + "entry-edited",
        )
        assert updated["id"] == eid
    finally:
        await time_entries.delete_time_entry(client, workspace_id=ws, time_entry_id=eid)
```

- [ ] **Step 2: Verify it is skipped without the gate (default test run)**

Run: `uv run pytest tests/test_live_smoke.py -q`
Expected: all 4 tests SKIPPED (no `CLOCKIFY_LIVE_TEST`), 0 failures.

- [ ] **Step 3: Confirm the full default suite stays green and lint is clean**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: 61 passed, 4 skipped (the live ones), ruff clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_live_smoke.py
git commit -m "test: gated live smoke round-trips for write tools"
```

- [ ] **Step 5: Controller runs the live suite**

After the user exports real credentials in-session (e.g. `! export CLOCKIFY_API_KEY=... CLOCKIFY_LIVE_TEST=1 CLOCKIFY_ENABLE_WRITES=true`), the controller first resolves the two workspaces by name (via `list_workspaces`) to confirm `"Alan Fuentes's workspace"`, sets `CLOCKIFY_LIVE_WORKSPACE_NAME` accordingly, and runs:

```bash
CLOCKIFY_LIVE_WORKSPACE_NAME="Alan Fuentes's workspace" uv run pytest tests/test_live_smoke.py -q -s
```

Expected: 4 passed against the real workspace, with all created artifacts deleted. If any test fails mid-way, check the workspace for leftover `mcp-smoke-*` items and remove them.

---

## Self-Review

**Spec coverage** (design §7 Phase 4 row — core writes opt-in for time entries, projects, tasks, clients, tags + live tests):
- clients create/update/delete → Task 1 ✓
- projects create/update/delete → Task 2 ✓
- tasks create/update/delete → Task 3 ✓
- tags create/update/delete → Task 4 ✓
- time_entries create/update/delete/duplicate/bulk → Task 5 ✓
- All gated behind `CLOCKIFY_ENABLE_WRITES` via `_register_writes` + `client.writes_enabled` (design §5) and proven by server gating tests ✓
- Live create/update/delete round-trips (design §5/§10) → Task 7 ✓
- Docs updated (Task 6) ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output. ✓

**Type consistency:** Module-level write fns and their `@mcp.tool()` wrappers share identical signatures per domain; `*_fn` aliases match the module-level names and sit at the file bottom (matching existing modules); body keys are camelCase (`clientId`, `projectId`, `taskId`, `tagIds`, `isPublic`) while path/query keys stay hyphenated; `client_id`/`project_id`/`task_id`/`tag_id`/`time_entry_id`/`user_id` naming consistent across functions and tests. The shared `drop_none` replaces the per-module copy (reports.py refactored in Task 1). ✓

**Out of scope (this phase):** Phase 5–7 domains (time_off/holidays, expenses/approvals, custom_fields/scheduling/invoices/webhooks). Advanced project create fields (estimate/costRate/hourlyRate/memberships/inline tasks). The "add time entry for another user" and "stop running timer" / "delete all entries for a user" endpoints. Real OTel telemetry port.
