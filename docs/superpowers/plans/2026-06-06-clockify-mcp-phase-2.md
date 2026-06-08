# Phase 2 — Core Entities (read) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only MCP tools for the four core Clockify entity domains — clients, projects, tasks, tags — bringing the server from 7 tools / 3 domains to 15 tools / 7 domains.

**Architecture:** Each domain is a self-contained module under `src/clockify_mcp/domains/` that defines plain async functions (testable directly with a `ClockifyClient`) and a `register(mcp, client)` that wraps each as an `@mcp.tool()`. This mirrors the existing `users.py`/`groups.py` pattern exactly: module-level `*_fn` aliases at the bottom, `resolve_workspace_id` for workspace fallback, `page_params` for pagination. The server layer registers each new domain. No client or pagination changes are needed — Phase 0 already provides everything.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx + pytest-asyncio for tests, `uv` for all commands, ruff for lint.

---

## Background — verified API facts

All endpoints and query-parameter names below were verified against the live Clockify OpenAPI spec (`https://docs.clockify.me/`) on 2026-06-06. **Do not invent or alter parameter names.**

| Tool | Method + path | Query params (exact, verbatim) |
|---|---|---|
| `list_clients` | `GET workspaces/{ws}/clients` | `name`, `archived`, `sort-column`, `sort-order`, `page`, `page-size` |
| `get_client` | `GET workspaces/{ws}/clients/{id}` | — |
| `list_projects` | `GET workspaces/{ws}/projects` | `name`, `strict-name-search`, `archived`, `billable`, `clients` (array), `users` (array), `is-template`, `hydrated`, `sort-column`, `sort-order`, `page`, `page-size` |
| `get_project` | `GET workspaces/{ws}/projects/{projectId}` | `hydrated` |
| `list_tasks` | `GET workspaces/{ws}/projects/{projectId}/tasks` | `name`, `strict-name-search`, `is-active`, `sort-column`, `sort-order`, `page`, `page-size` |
| `get_task` | `GET workspaces/{ws}/projects/{projectId}/tasks/{taskId}` | — |
| `list_tags` | `GET workspaces/{ws}/tags` | `name`, `strict-name-search`, `archived`, `excluded-ids`, `sort-column`, `sort-order`, `page`, `page-size` |
| `get_tag` | `GET workspaces/{ws}/tags/{id}` | — |

Notes confirmed by experiment:
- The list endpoints use **hyphenated `page-size`** — `pagination.page_params()` is already correct.
- `httpx` renders Python `bool` query values as lowercase `true`/`false`; the client's `_clean()` drops `None` values before sending. So `archived: bool | None` etc. work without special handling.
- Array params (`clients`, `users`) are passed as Python `list[str]`; httpx emits repeated keys (`clients=a&clients=b`), which Clockify expects. In tests, read them back with `request.url.params.get_list("clients")`.
- `list_projects` has ~21 query params in the spec; this plan exposes a curated, high-value subset (above). The rarer ones (`contains-client`, `client-status`, `contains-user`, `user-status`, `access`, `expense-*`, `userGroups`, `contains-group`) are intentionally omitted to keep the tool signature usable and can be added later if needed.

**Baseline:** `uv run pytest -q` currently reports **27 passed**. Each task adds tests; the final count is verified in Task 5.

---

## File Structure

- Create: `src/clockify_mcp/domains/clients.py` — clients read tools
- Create: `src/clockify_mcp/domains/projects.py` — projects read tools
- Create: `src/clockify_mcp/domains/tasks.py` — tasks read tools
- Create: `src/clockify_mcp/domains/tags.py` — tags read tools
- Create: `tests/test_clients.py`, `tests/test_projects.py`, `tests/test_tasks.py`, `tests/test_tags.py`
- Modify: `src/clockify_mcp/server.py` — import + register the four new domains
- Modify: `tests/test_server.py` — extend the asserted tool-name set
- Modify: `README.md`, `CLAUDE.md` — update tool tables and counts

Each domain task is self-contained and leaves the server shippable (tools registered, full suite green).

---

## Task 1: Clients domain

**Files:**
- Create: `src/clockify_mcp/domains/clients.py`
- Test: `tests/test_clients.py`
- Modify: `src/clockify_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing unit test**

Create `tests/test_clients.py`:

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import clients


@respx.mock
async def test_list_clients_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/clients").mock(
        return_value=httpx.Response(200, json=[{"id": "c1"}])
    )
    client = ClockifyClient(config)
    result = await clients.list_clients(
        client, name="acme", archived=False, page=2, page_size=10
    )
    assert result == [{"id": "c1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "acme"
    assert sent["archived"] == "false"
    assert sent["page"] == "2"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_get_client(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(200, json={"id": "c1", "name": "Acme"})
    )
    client = ClockifyClient(config)
    assert await clients.get_client(client, client_id="c1") == {"id": "c1", "name": "Acme"}
    await client.aclose()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_clients.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_mcp.domains.clients'` (collection error).

- [ ] **Step 3: Write the domain module**

Create `src/clockify_mcp/domains/clients.py`:

```python
"""Clients domain (read)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_clients(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    archived: bool | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List clients on the workspace, optionally filtered by name (paginated).

    Set archived=True to include archived clients. sort_column is one of NAME;
    sort_order is ASCENDING or DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "archived": archived,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/clients", params=params)


async def get_client(
    client: ClockifyClient, *, client_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single client by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/clients/{client_id}")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_clients(
        workspace_id: str | None = None,
        name: str | None = None,
        archived: bool | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List clients on the workspace, optionally filtered by name (paginated)."""
        return await list_clients_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            archived=archived,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_client(client_id: str, workspace_id: str | None = None) -> Any:
        """Get a single client by id."""
        return await get_client_fn(client, client_id=client_id, workspace_id=workspace_id)


list_clients_fn = list_clients
get_client_fn = get_client
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `uv run pytest tests/test_clients.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 5: Register the domain in the server**

In `src/clockify_mcp/server.py`, change the domains import line:

```python
from .domains import clients, groups, users, workspaces
```

And add a register call after `groups.register(mcp, client)`:

```python
    groups.register(mcp, client)
    clients.register(mcp, client)
    return mcp
```

- [ ] **Step 6: Extend the server registration test**

In `tests/test_server.py`, inside `test_build_server_registers_discovery_tools`, add the two client tool names to the asserted set:

```python
    assert {
        "get_current_user",
        "list_workspaces",
        "get_workspace",
        "list_users",
        "get_user_member_profile",
        "find_user_team_manager",
        "list_user_groups",
        "list_clients",
        "get_client",
    } <= names
```

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all tests pass (29 passed) and ruff reports no errors.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/domains/clients.py tests/test_clients.py src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: clients domain (list/filter, get)"
```

---

## Task 2: Projects domain

**Files:**
- Create: `src/clockify_mcp/domains/projects.py`
- Test: `tests/test_projects.py`
- Modify: `src/clockify_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing unit test**

Create `tests/test_projects.py`:

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import projects


@respx.mock
async def test_list_projects_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1"}])
    )
    client = ClockifyClient(config)
    result = await projects.list_projects(
        client,
        name="site",
        archived=False,
        billable=True,
        clients=["c1", "c2"],
        hydrated=True,
        page=1,
        page_size=50,
    )
    assert result == [{"id": "p1"}]
    params = route.calls.last.request.url.params
    assert params["name"] == "site"
    assert params["archived"] == "false"
    assert params["billable"] == "true"
    assert params["hydrated"] == "true"
    assert params["page-size"] == "50"
    assert params.get_list("clients") == ["c1", "c2"]
    await client.aclose()


@respx.mock
async def test_get_project_passes_hydrated(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/projects/p1").mock(
        return_value=httpx.Response(200, json={"id": "p1"})
    )
    client = ClockifyClient(config)
    assert await projects.get_project(client, project_id="p1", hydrated=True) == {"id": "p1"}
    assert dict(route.calls.last.request.url.params)["hydrated"] == "true"
    await client.aclose()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_projects.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_mcp.domains.projects'`.

- [ ] **Step 3: Write the domain module**

Create `src/clockify_mcp/domains/projects.py`:

```python
"""Projects domain (read)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_projects(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    strict_name_search: bool | None = None,
    archived: bool | None = None,
    billable: bool | None = None,
    clients: list[str] | None = None,
    users: list[str] | None = None,
    is_template: bool | None = None,
    hydrated: bool | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List projects on the workspace with optional filters (paginated).

    Filter by name (substring; set strict_name_search=True for exact), archived,
    billable, is_template, by client ids (clients=[...]) or assigned user ids
    (users=[...]). hydrated=True expands nested tasks/memberships. sort_column is
    one of NAME, CLIENT_NAME, DURATION; sort_order is ASCENDING or DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "strict-name-search": strict_name_search,
        "archived": archived,
        "billable": billable,
        "clients": clients,
        "users": users,
        "is-template": is_template,
        "hydrated": hydrated,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/projects", params=params)


async def get_project(
    client: ClockifyClient,
    *,
    project_id: str,
    workspace_id: str | None = None,
    hydrated: bool | None = None,
) -> Any:
    """Get a single project by id. hydrated=True expands nested tasks/memberships."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"hydrated": hydrated}
    return await client.get(f"workspaces/{ws}/projects/{project_id}", params=params)


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_projects(
        workspace_id: str | None = None,
        name: str | None = None,
        strict_name_search: bool | None = None,
        archived: bool | None = None,
        billable: bool | None = None,
        clients: list[str] | None = None,
        users: list[str] | None = None,
        is_template: bool | None = None,
        hydrated: bool | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List projects on the workspace with optional filters (paginated)."""
        return await list_projects_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            strict_name_search=strict_name_search,
            archived=archived,
            billable=billable,
            clients=clients,
            users=users,
            is_template=is_template,
            hydrated=hydrated,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_project(
        project_id: str,
        workspace_id: str | None = None,
        hydrated: bool | None = None,
    ) -> Any:
        """Get a single project by id."""
        return await get_project_fn(
            client, project_id=project_id, workspace_id=workspace_id, hydrated=hydrated
        )


list_projects_fn = list_projects
get_project_fn = get_project
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `uv run pytest tests/test_projects.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 5: Register the domain in the server**

In `src/clockify_mcp/server.py`, update the import:

```python
from .domains import clients, groups, projects, users, workspaces
```

Add the register call after `clients.register(mcp, client)`:

```python
    clients.register(mcp, client)
    projects.register(mcp, client)
    return mcp
```

- [ ] **Step 6: Extend the server registration test**

In `tests/test_server.py`, add to the asserted set in `test_build_server_registers_discovery_tools`:

```python
        "list_projects",
        "get_project",
```

(place them inside the existing `{ ... } <= names` set literal)

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all tests pass (31 passed) and ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/domains/projects.py tests/test_projects.py src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: projects domain (list/filter, get)"
```

---

## Task 3: Tasks domain

**Files:**
- Create: `src/clockify_mcp/domains/tasks.py`
- Test: `tests/test_tasks.py`
- Modify: `src/clockify_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing unit test**

Create `tests/test_tasks.py`:

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import tasks


@respx.mock
async def test_list_tasks_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks"
    ).mock(return_value=httpx.Response(200, json=[{"id": "t1"}]))
    client = ClockifyClient(config)
    result = await tasks.list_tasks(
        client, project_id="p1", name="design", is_active=True, page=1, page_size=20
    )
    assert result == [{"id": "t1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "design"
    assert sent["is-active"] == "true"
    assert sent["page-size"] == "20"
    await client.aclose()


@respx.mock
async def test_get_task(config):
    respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks/t1"
    ).mock(return_value=httpx.Response(200, json={"id": "t1", "name": "Design"}))
    client = ClockifyClient(config)
    result = await tasks.get_task(client, project_id="p1", task_id="t1")
    assert result == {"id": "t1", "name": "Design"}
    await client.aclose()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_tasks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_mcp.domains.tasks'`.

- [ ] **Step 3: Write the domain module**

Create `src/clockify_mcp/domains/tasks.py`:

```python
"""Tasks domain (read). Tasks live under a project."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_tasks(
    client: ClockifyClient,
    *,
    project_id: str,
    workspace_id: str | None = None,
    name: str | None = None,
    strict_name_search: bool | None = None,
    is_active: bool | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List tasks on a project, optionally filtered by name/active state (paginated).

    Resolve project_id with list_projects first. Set strict_name_search=True for an
    exact name match; is_active=True returns only active (non-done) tasks. sort_column
    is one of NAME; sort_order is ASCENDING or DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "strict-name-search": strict_name_search,
        "is-active": is_active,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/projects/{project_id}/tasks", params=params)


async def get_task(
    client: ClockifyClient,
    *,
    project_id: str,
    task_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Get a single task by id (within its project)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/projects/{project_id}/tasks/{task_id}")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_tasks(
        project_id: str,
        workspace_id: str | None = None,
        name: str | None = None,
        strict_name_search: bool | None = None,
        is_active: bool | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List tasks on a project, optionally filtered by name/active state (paginated)."""
        return await list_tasks_fn(
            client,
            project_id=project_id,
            workspace_id=workspace_id,
            name=name,
            strict_name_search=strict_name_search,
            is_active=is_active,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_task(
        project_id: str, task_id: str, workspace_id: str | None = None
    ) -> Any:
        """Get a single task by id (within its project)."""
        return await get_task_fn(
            client, project_id=project_id, task_id=task_id, workspace_id=workspace_id
        )


list_tasks_fn = list_tasks
get_task_fn = get_task
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `uv run pytest tests/test_tasks.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 5: Register the domain in the server**

In `src/clockify_mcp/server.py`, update the import:

```python
from .domains import clients, groups, projects, tasks, users, workspaces
```

Add the register call after `projects.register(mcp, client)`:

```python
    projects.register(mcp, client)
    tasks.register(mcp, client)
    return mcp
```

- [ ] **Step 6: Extend the server registration test**

In `tests/test_server.py`, add to the asserted set:

```python
        "list_tasks",
        "get_task",
```

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all tests pass (33 passed) and ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/domains/tasks.py tests/test_tasks.py src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: tasks domain (list/filter, get)"
```

---

## Task 4: Tags domain

**Files:**
- Create: `src/clockify_mcp/domains/tags.py`
- Test: `tests/test_tags.py`
- Modify: `src/clockify_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing unit test**

Create `tests/test_tags.py`:

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import tags


@respx.mock
async def test_list_tags_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1"}])
    )
    client = ClockifyClient(config)
    result = await tags.list_tags(
        client, name="billable", archived=False, excluded_ids="g9", page=1, page_size=15
    )
    assert result == [{"id": "g1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "billable"
    assert sent["archived"] == "false"
    assert sent["excluded-ids"] == "g9"
    assert sent["page-size"] == "15"
    await client.aclose()


@respx.mock
async def test_get_tag(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/tags/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1", "name": "Billable"})
    )
    client = ClockifyClient(config)
    assert await tags.get_tag(client, tag_id="g1") == {"id": "g1", "name": "Billable"}
    await client.aclose()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_tags.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_mcp.domains.tags'`.

- [ ] **Step 3: Write the domain module**

Create `src/clockify_mcp/domains/tags.py`:

```python
"""Tags domain (read)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_tags(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    strict_name_search: bool | None = None,
    archived: bool | None = None,
    excluded_ids: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List tags on the workspace, optionally filtered by name (paginated).

    Set strict_name_search=True for an exact name match; archived=True includes
    archived tags; excluded_ids omits specific tag ids. sort_column is one of NAME;
    sort_order is ASCENDING or DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "strict-name-search": strict_name_search,
        "archived": archived,
        "excluded-ids": excluded_ids,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/tags", params=params)


async def get_tag(
    client: ClockifyClient, *, tag_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single tag by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/tags/{tag_id}")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_tags(
        workspace_id: str | None = None,
        name: str | None = None,
        strict_name_search: bool | None = None,
        archived: bool | None = None,
        excluded_ids: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List tags on the workspace, optionally filtered by name (paginated)."""
        return await list_tags_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            strict_name_search=strict_name_search,
            archived=archived,
            excluded_ids=excluded_ids,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_tag(tag_id: str, workspace_id: str | None = None) -> Any:
        """Get a single tag by id."""
        return await get_tag_fn(client, tag_id=tag_id, workspace_id=workspace_id)


list_tags_fn = list_tags
get_tag_fn = get_tag
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `uv run pytest tests/test_tags.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 5: Register the domain in the server**

In `src/clockify_mcp/server.py`, update the import:

```python
from .domains import clients, groups, projects, tags, tasks, users, workspaces
```

Add the register call after `tasks.register(mcp, client)`:

```python
    tasks.register(mcp, client)
    tags.register(mcp, client)
    return mcp
```

- [ ] **Step 6: Extend the server registration test**

In `tests/test_server.py`, add to the asserted set:

```python
        "list_tags",
        "get_tag",
```

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all tests pass (35 passed) and ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/domains/tags.py tests/test_tags.py src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: tags domain (list/filter, get)"
```

---

## Task 5: Docs update + final verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the README tool table**

In `README.md`, replace the "What can it do?" intro line and table. Change `**7 read-only tools**` to `**15 read-only tools**`, update the lead-in sentence to mention clients/projects/tasks/tags, and append four rows to the table:

```markdown
| **Clients** | 2 | `list_clients`, `get_client` |
| **Projects** | 2 | `list_projects`, `get_project` |
| **Tasks** | 2 | `list_tasks`, `get_task` |
| **Tags** | 2 | `list_tags`, `get_tag` |
```

Also update line 5 (the description) and the `Read-only by default` note near the bottom that says "All 7 tools are read-only" → "All 15 tools are read-only", and remove tags/projects/tasks/clients from the "More domains ... land in later phases" note (leave time entries, reports).

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`:
- Change the Project Overview phase line `7 read-only discovery tools across 3 domains (Workspaces, Users, Groups)` → `15 read-only tools across 7 domains (Workspaces, Users, Groups, Clients, Projects, Tasks, Tags)`.
- Under "Key modules", add four lines after the `domains/groups.py` line:

```markdown
- `domains/clients.py` — `list_clients`, `get_client`
- `domains/projects.py` — `list_projects`, `get_project`
- `domains/tasks.py` — `list_tasks`, `get_task`
- `domains/tags.py` — `list_tags`, `get_tag`
```

- In "Development Conventions", change `expect 26 passed` to the actual final count printed in Step 3.

- [ ] **Step 3: Run the full suite and lint one last time**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: 35 passed, ruff clean. Note the exact passed count and ensure CLAUDE.md (Step 2) matches it.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document Phase 2 clients/projects/tasks/tags tools"
```

---

## Self-Review

**Spec coverage** (design §7 Phase 2 row — `projects`, `tasks`, `clients`, `tags` read):
- clients: `list_clients`, `get_client` → Task 1 ✓
- projects: `list_projects`, `get_project` → Task 2 ✓
- tasks: `list_tasks`, `get_task` → Task 3 ✓
- tags: `list_tags`, `get_tag` → Task 4 ✓
- All registered + discoverable (server test) and documented (Task 5) ✓
- Pagination via `page_params`, workspace fallback via `resolve_workspace_id`, no client changes — matches design §3/§4 ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output. ✓

**Type consistency:** Module-level functions and their `@mcp.tool()` wrappers share identical signatures per domain; `*_fn` aliases match the module-level names; `project_id`/`task_id`/`client_id`/`tag_id` naming consistent across list/get and tests. Query-param keys match the verified spec table verbatim. ✓

**Out of scope (this phase):** No write tools (`create/update/delete_*`) — those are Phase 4, gated by `CLOCKIFY_ENABLE_WRITES`. No `fetch_all` auto-pagination. No time_entries/reports (Phase 3).
