"""Tasks domain (read + write). Tasks live under a project."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import fetch_all_pages, page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# --- Parameter descriptions (surfaced to MCP clients via the tool input schema) ---
_WorkspaceId = Annotated[
    str | None,
    Field(description="Workspace id; omit to use the configured default_workspace_id."),
]
_ProjectId = Annotated[
    str,
    Field(
        description="Id of the project the task lives under "
        "(resolve via list_projects)."
    ),
]
_TaskId = Annotated[
    str,
    Field(description="Id of the task (opaque string returned by list_tasks)."),
]
_NameFilter = Annotated[
    str | None,
    Field(description="Filter tasks by name (substring unless strict_name_search=True)."),
]
_StrictNameSearch = Annotated[
    bool | None,
    Field(description="When true, 'name' must match exactly rather than as a substring."),
]
_IsActiveFilter = Annotated[
    bool | None,
    Field(description="When true, return only active (non-done) tasks."),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort by; only NAME is supported."),
]
_SortOrder = Annotated[
    str | None,
    Field(description="Sort direction: ASCENDING or DESCENDING."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number; ignored when fetch_all=True."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of tasks per page."),
]
_FetchAll = Annotated[
    bool,
    Field(description="Follow pagination and return all pages concatenated; ignores 'page'."),
]
_NewName = Annotated[
    str,
    Field(description="Display name for the new task."),
]
_UpdateName = Annotated[
    str,
    Field(description="Task name; required by the API on update."),
]
_AssigneeIds = Annotated[
    list[str] | None,
    Field(description="User ids to assign to the task; omit to leave unchanged."),
]
_Estimate = Annotated[
    str | None,
    Field(description="Time estimate as an ISO-8601 duration (e.g. PT1H30M)."),
]
_Status = Annotated[
    str | None,
    Field(description="Task status: ACTIVE or DONE."),
]
_Billable = Annotated[
    bool | None,
    Field(description="Whether the task is billable; omit to leave unchanged."),
]


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
        project_id: _ProjectId,
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        strict_name_search: _StrictNameSearch = None,
        is_active: _IsActiveFilter = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
        fetch_all: _FetchAll = False,
    ) -> Any:
        """List tasks under a project, optionally filtered by name/active state.

        Read-only; tasks nest under a project, so project_id is required (resolve
        it with list_projects first). Set strict_name_search=True for an exact name
        match; is_active=True returns only active (non-done) tasks. sort_column is
        one of NAME; sort_order is ASCENDING or DESCENDING. Results are paginated;
        fetch_all=True follows pagination and returns every page concatenated
        (ignores page). Use this to discover task ids before logging time entries;
        when you already know a task's id, use get_task instead.
        """
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
        project_id: _ProjectId, task_id: _TaskId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Get a single task's full detail by its id, within its project.

        Read-only; tasks nest under a project, so both project_id and task_id are
        required. Use list_tasks first to look up the id when you only know the
        task name. Returns one task object.
        """
        return await get_task_fn(
            client, project_id=project_id, task_id=task_id, workspace_id=workspace_id
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_task(
        project_id: _ProjectId,
        name: _NewName,
        workspace_id: _WorkspaceId = None,
        assignee_ids: _AssigneeIds = None,
        estimate: _Estimate = None,
        status: _Status = None,
    ) -> Any:
        """Create a task under a project.

        Write operation; tasks nest under a project, so project_id is required.
        status is ACTIVE or DONE; estimate is an ISO-8601 duration (e.g. PT1H30M).
        Returns the created task including its newly assigned id.
        """
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
        project_id: _ProjectId,
        task_id: _TaskId,
        name: _UpdateName,
        workspace_id: _WorkspaceId = None,
        assignee_ids: _AssigneeIds = None,
        estimate: _Estimate = None,
        status: _Status = None,
        billable: _Billable = None,
    ) -> Any:
        """Update an existing task within its project.

        Write operation; tasks nest under a project, so project_id and task_id are
        required, and name is required by the API even when unchanged. status is
        ACTIVE or DONE; estimate is an ISO-8601 duration (e.g. PT1H30M). Set
        status=DONE to mark a task complete rather than deleting it. Returns the
        updated task.
        """
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
        project_id: _ProjectId, task_id: _TaskId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Permanently delete a task from its project.

        Write operation and IRREVERSIBLE — the task is permanently removed. Tasks
        nest under a project, so project_id and task_id are required. If you only
        want to mark it complete, use update_task(status="DONE") instead.
        """
        return await delete_task_fn(
            client, project_id=project_id, task_id=task_id, workspace_id=workspace_id
        )


list_tasks_fn = list_tasks
get_task_fn = get_task
create_task_fn = create_task
update_task_fn = update_task
delete_task_fn = delete_task
