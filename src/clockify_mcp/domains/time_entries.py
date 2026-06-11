"""Time entries domain (read + write)."""

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
_UserId = Annotated[
    str,
    Field(
        description="Id of the user whose entries are targeted; resolve with "
        "get_current_user (yourself) or list_users (someone else)."
    ),
]
_TimeEntryId = Annotated[
    str,
    Field(description="Id of the time entry (opaque string returned by list_time_entries)."),
]
_DescriptionFilter = Annotated[
    str | None,
    Field(description="Filter entries whose description matches this text."),
]
_StartFilter = Annotated[
    str | None,
    Field(
        description="Only return entries on/after this ISO-8601 datetime with offset "
        "(e.g. 2021-01-01T00:00:00Z)."
    ),
]
_EndFilter = Annotated[
    str | None,
    Field(
        description="Only return entries on/before this ISO-8601 datetime with offset "
        "(e.g. 2021-01-31T23:59:59Z)."
    ),
]
_ProjectFilter = Annotated[
    str | None,
    Field(description="Filter by a single project id."),
]
_TaskFilter = Annotated[
    str | None,
    Field(description="Filter by a single task id."),
]
_TagsFilter = Annotated[
    list[str] | None,
    Field(description="Filter by a list of tag ids."),
]
_ProjectRequired = Annotated[
    bool | None,
    Field(description="When true, only return entries that have a project assigned."),
]
_TaskRequired = Annotated[
    bool | None,
    Field(description="When true, only return entries that have a task assigned."),
]
_HydratedFilter = Annotated[
    bool | None,
    Field(description="When true, expand project/task/tag objects instead of bare ids."),
]
_InProgressFilter = Annotated[
    bool | None,
    Field(description="When true, return only the currently running entry."),
]
_GetWeekBefore = Annotated[
    str | None,
    Field(
        description="ISO-8601 datetime; return the entries of the week before it."
    ),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number; ignored when fetch_all=True."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of entries per page."),
]
_FetchAll = Annotated[
    bool,
    Field(description="Follow pagination and return all pages concatenated; ignores 'page'."),
]
_StartRequired = Annotated[
    str,
    Field(
        description="Start time, ISO-8601 datetime with offset "
        "(e.g. 2021-01-01T09:00:00Z)."
    ),
]
_EndBody = Annotated[
    str | None,
    Field(
        description="End time, ISO-8601 datetime with offset; omit to start a running "
        "timer."
    ),
]
_StopEnd = Annotated[
    str,
    Field(description="End time (ISO-8601 datetime with offset) to set on the running timer."),
]
_DescriptionBody = Annotated[
    str | None,
    Field(description="Description text for the entry."),
]
_ProjectIdBody = Annotated[
    str | None,
    Field(description="Project id to associate with the entry."),
]
_TaskIdBody = Annotated[
    str | None,
    Field(description="Task id to associate with the entry."),
]
_TagIdsBody = Annotated[
    list[str] | None,
    Field(description="Tag ids to attach to the entry."),
]
_BillableBody = Annotated[
    bool | None,
    Field(description="Whether the entry is billable."),
]
_TypeBody = Annotated[
    str | None,
    Field(description="Entry type: REGULAR or BREAK."),
]
_Entries = Annotated[
    list[dict[str, Any]],
    Field(
        description="List of entry dicts to edit; each MUST include its 'id' plus the "
        "camelCase fields to change (start, end, description, projectId, taskId, "
        "tagIds, billable, type)."
    ),
]


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
    fetch_all: bool = False,
) -> Any:
    """List a user's time entries on the workspace (paginated).

    Resolve user_id with get_current_user or list_users first. start/end are
    ISO-8601 datetimes with offset (e.g. 2021-01-01T00:00:00Z). project/task filter
    by a single id; tags is a list of tag ids. hydrated=True expands project/task/tag
    objects; in_progress=True returns only the running entry. get_week_before is an
    ISO-8601 datetime that returns the entries of the week before it. Set fetch_all=True
    to follow pagination and return every page concatenated (ignores page; may make
    several API calls).
    """
    ws = resolve_workspace_id(client, workspace_id)
    base = {
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
    }
    path = f"workspaces/{ws}/user/{user_id}/time-entries"
    if fetch_all:
        return await fetch_all_pages(
            lambda p, ps: client.get(path, params={**base, **page_params(p, ps)}),
            page_size=page_size,
        )
    return await client.get(path, params={**base, **page_params(page, page_size)})


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
    # Same path as bulk_update_time_entries (PUT) — the API distinguishes by verb:
    # PATCH on /user/{id}/time-entries stops the running timer.
    return await client.patch(
        f"workspaces/{ws}/user/{user_id}/time-entries", json={"end": end}
    )


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_time_entries(
        user_id: _UserId,
        workspace_id: _WorkspaceId = None,
        description: _DescriptionFilter = None,
        start: _StartFilter = None,
        end: _EndFilter = None,
        project: _ProjectFilter = None,
        task: _TaskFilter = None,
        tags: _TagsFilter = None,
        project_required: _ProjectRequired = None,
        task_required: _TaskRequired = None,
        hydrated: _HydratedFilter = None,
        in_progress: _InProgressFilter = None,
        get_week_before: _GetWeekBefore = None,
        page: _Page = None,
        page_size: _PageSize = None,
        fetch_all: _FetchAll = False,
    ) -> Any:
        """List one user's time entries on a workspace, with optional filters.

        Read-only; results are paginated. Resolve user_id with get_current_user
        (yourself) or list_users (someone else) first. Filter by description,
        start/end window, project/task id, or tag ids; in_progress=True returns
        only the running entry and get_week_before returns the prior week's
        entries. hydrated=True expands project/task/tag objects. fetch_all=True
        follows pagination and returns every page concatenated (ignores page; may
        make several API calls). Use get_time_entry when you already know an
        entry's id. Returns a list of time-entry objects.
        """
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
            fetch_all=fetch_all,
        )

    @mcp.tool()
    async def get_time_entry(
        time_entry_id: _TimeEntryId,
        workspace_id: _WorkspaceId = None,
        hydrated: _HydratedFilter = None,
    ) -> Any:
        """Get a single time entry's full detail by its id.

        Read-only. Use list_time_entries first to discover the id when you only
        know the user, date, or description. hydrated=True expands project/task/tag
        objects instead of returning bare ids. Returns one time-entry object.
        """
        return await get_time_entry_fn(
            client,
            time_entry_id=time_entry_id,
            workspace_id=workspace_id,
            hydrated=hydrated,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)
    elif client.time_tracking_enabled:
        _register_time_tracking_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_time_entry(
        start: _StartRequired,
        workspace_id: _WorkspaceId = None,
        end: _EndBody = None,
        description: _DescriptionBody = None,
        project_id: _ProjectIdBody = None,
        task_id: _TaskIdBody = None,
        tag_ids: _TagIdsBody = None,
        billable: _BillableBody = None,
        type: _TypeBody = None,
    ) -> Any:
        """Create a time entry for the authenticated user (yourself).

        Write operation. Omit end to start a running timer; provide end to log a
        completed entry. To create an entry for someone else, use
        create_time_entry_for_user. Returns the created time-entry object,
        including its newly assigned id.
        """
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
        time_entry_id: _TimeEntryId,
        start: _StartRequired,
        workspace_id: _WorkspaceId = None,
        end: _EndBody = None,
        description: _DescriptionBody = None,
        project_id: _ProjectIdBody = None,
        task_id: _TaskIdBody = None,
        tag_ids: _TagIdsBody = None,
        billable: _BillableBody = None,
        type: _TypeBody = None,
    ) -> Any:
        """Update an existing time entry, identified by its id.

        Write operation. start is required by the API even when only editing other
        fields — pass the entry's existing start if you are not changing it. Use
        list_time_entries or get_time_entry to find the id. Returns the updated
        time-entry object.
        """
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
        time_entry_id: _TimeEntryId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Permanently delete a time entry, identified by its id.

        Write operation and IRREVERSIBLE — the entry is removed and cannot be
        recovered. Use list_time_entries or get_time_entry to confirm the id first.
        """
        return await delete_time_entry_fn(
            client, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def duplicate_time_entry(
        user_id: _UserId, time_entry_id: _TimeEntryId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Duplicate one of a user's time entries, creating a copy.

        Write operation. Resolve user_id with get_current_user (yourself) or
        list_users (someone else). Returns the newly created copy.
        """
        return await duplicate_time_entry_fn(
            client,
            user_id=user_id,
            time_entry_id=time_entry_id,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def bulk_update_time_entries(
        user_id: _UserId,
        entries: _Entries,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Bulk-edit several of a user's time entries in one call.

        Write operation. Each entry dict MUST include its 'id' plus the camelCase
        fields to change (start, end, description, projectId, taskId, tagIds,
        billable, type). Resolve user_id with get_current_user (yourself) or
        list_users (someone else). Use update_time_entry for a single entry.
        """
        return await bulk_update_time_entries_fn(
            client, user_id=user_id, entries=entries, workspace_id=workspace_id
        )

    @mcp.tool()
    async def create_time_entry_for_user(
        user_id: _UserId,
        start: _StartRequired,
        workspace_id: _WorkspaceId = None,
        end: _EndBody = None,
        description: _DescriptionBody = None,
        project_id: _ProjectIdBody = None,
        task_id: _TaskIdBody = None,
        tag_ids: _TagIdsBody = None,
        billable: _BillableBody = None,
        type: _TypeBody = None,
    ) -> Any:
        """Create a time entry on behalf of ANOTHER user (admin action).

        Write operation. Resolve user_id with list_users. Omit end to start a
        running timer; provide end to log a completed entry. To log time for
        yourself, use create_time_entry instead. Returns the created time-entry
        object, including its newly assigned id.
        """
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
        user_id: _UserId, end: _StopEnd, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Stop a user's currently running timer by setting its end time.

        Write operation. Resolve user_id with get_current_user (yourself) or
        list_users (someone else). Use in_progress=True on list_time_entries to
        find the running entry. Returns the now-stopped time-entry object.
        """
        return await stop_running_timer_fn(
            client, user_id=user_id, end=end, workspace_id=workspace_id
        )


def _register_time_tracking_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    """Write tools for the 'time-tracking' access tier: log/manage time entries only.

    create/update/delete are the same as full mode (update/delete act on an entry by
    id; the golden rule lives in their docstrings). duplicate/bulk are self-scoped:
    they take no user_id and always target the authenticated user.
    """

    @mcp.tool()
    async def create_time_entry(
        start: _StartRequired,
        workspace_id: _WorkspaceId = None,
        end: _EndBody = None,
        description: _DescriptionBody = None,
        project_id: _ProjectIdBody = None,
        task_id: _TaskIdBody = None,
        tag_ids: _TagIdsBody = None,
        billable: _BillableBody = None,
        type: _TypeBody = None,
    ) -> Any:
        """Create a time entry for the authenticated user (yourself).

        Write operation (time-tracking mode). Omit end to start a running timer;
        provide end to log a completed entry. Returns the created time-entry
        object, including its newly assigned id.
        """
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
        time_entry_id: _TimeEntryId,
        start: _StartRequired,
        workspace_id: _WorkspaceId = None,
        end: _EndBody = None,
        description: _DescriptionBody = None,
        project_id: _ProjectIdBody = None,
        task_id: _TaskIdBody = None,
        tag_ids: _TagIdsBody = None,
        billable: _BillableBody = None,
        type: _TypeBody = None,
    ) -> Any:
        """Update an existing time entry, identified by its id (time-tracking mode).

        Write operation. start is required by the API even when editing other
        fields — pass the entry's existing start if unchanged. GOLDEN RULE: in
        time-tracking mode you should only edit YOUR OWN entries — this acts on an
        entry by id and the server cannot tell whose it is, so confirm with the
        user before editing an entry that may be someone else's. Returns the
        updated time-entry object.
        """
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
        time_entry_id: _TimeEntryId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Permanently delete a time entry, identified by its id (time-tracking mode).

        Write operation and IRREVERSIBLE — the entry cannot be recovered. GOLDEN
        RULE: in time-tracking mode you should only delete YOUR OWN entries — this
        acts on an entry by id and the server cannot tell whose it is, so confirm
        with the user before deleting an entry that may be someone else's.
        """
        return await delete_time_entry_fn(
            client, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def duplicate_time_entry(
        time_entry_id: _TimeEntryId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Duplicate one of YOUR OWN time entries, creating a copy.

        Write operation. Self-scoped: time-tracking mode always targets the
        authenticated user (no user_id parameter). Returns the newly created copy.
        """
        user_id = await client.current_user_id()
        return await duplicate_time_entry_fn(
            client, user_id=user_id, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def bulk_update_time_entries(
        entries: _Entries, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Bulk-edit several of YOUR OWN time entries in one call.

        Write operation. Self-scoped: time-tracking mode always targets the
        authenticated user (no user_id parameter). Each entry dict MUST include
        its 'id' plus the camelCase fields to change (start, end, description,
        projectId, taskId, tagIds, billable, type).
        """
        user_id = await client.current_user_id()
        return await bulk_update_time_entries_fn(
            client, user_id=user_id, entries=entries, workspace_id=workspace_id
        )


list_time_entries_fn = list_time_entries
get_time_entry_fn = get_time_entry
create_time_entry_fn = create_time_entry
update_time_entry_fn = update_time_entry
delete_time_entry_fn = delete_time_entry
duplicate_time_entry_fn = duplicate_time_entry
bulk_update_time_entries_fn = bulk_update_time_entries
create_time_entry_for_user_fn = create_time_entry_for_user
stop_running_timer_fn = stop_running_timer
