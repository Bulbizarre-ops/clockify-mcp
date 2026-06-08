"""Tasks domain (read + write). Tasks live under a project."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import fetch_all_pages, page_params
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
    fetch_all: bool = False,
) -> Any:
    """List tasks on a project, optionally filtered by name/active state (paginated).

    Resolve project_id with list_projects first. Set strict_name_search=True for an
    exact name match; is_active=True returns only active (non-done) tasks. sort_column
    is one of NAME; sort_order is ASCENDING or DESCENDING. Set fetch_all=True to follow
    pagination and return every page concatenated (ignores page; may make several API
    calls).
    """
    ws = resolve_workspace_id(client, workspace_id)
    base = {
        "name": name,
        "strict-name-search": strict_name_search,
        "is-active": is_active,
        "sort-column": sort_column,
        "sort-order": sort_order,
    }
    path = f"workspaces/{ws}/projects/{project_id}/tasks"
    if fetch_all:
        return await fetch_all_pages(
            lambda p, ps: client.get(path, params={**base, **page_params(p, ps)}),
            page_size=page_size,
        )
    return await client.get(path, params={**base, **page_params(page, page_size)})


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


def register(mcp: FastMCP, client: ClockifyClient) -> None:
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
        fetch_all: bool = False,
    ) -> Any:
        """List tasks on a project, optionally filtered by name/active state (paginated).
        fetch_all=True follows pagination and returns every page concatenated."""
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
            fetch_all=fetch_all,
        )

    @mcp.tool()
    async def get_task(
        project_id: str, task_id: str, workspace_id: str | None = None
    ) -> Any:
        """Get a single task by id (within its project)."""
        return await get_task_fn(
            client, project_id=project_id, task_id=task_id, workspace_id=workspace_id
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
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


list_tasks_fn = list_tasks
get_task_fn = get_task
create_task_fn = create_task
update_task_fn = update_task
delete_task_fn = delete_task
