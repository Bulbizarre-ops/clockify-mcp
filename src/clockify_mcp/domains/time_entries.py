"""Time entries domain (read + write)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
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

    if client.writes_enabled:
        _register_writes(mcp, client)
    elif client.time_tracking_enabled:
        _register_time_tracking_writes(mcp, client)


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


def _register_time_tracking_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    """Write tools for the 'time-tracking' access tier: log/manage time entries only.

    create/update/delete are the same as full mode (update/delete act on an entry by
    id; the golden rule lives in their docstrings). duplicate/bulk are self-scoped:
    they take no user_id and always target the authenticated user.
    """

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
        """Update a time entry (by id). start is required by the API (pass the existing
        start if unchanged). GOLDEN RULE: in time-tracking mode you should only edit
        YOUR OWN entries — this acts on an entry by id and the server cannot tell whose
        it is, so confirm with the user before editing an entry that may be someone
        else's."""
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
        """Delete a time entry (by id). IRREVERSIBLE. GOLDEN RULE: in time-tracking
        mode you should only delete YOUR OWN entries — this acts on an entry by id and
        the server cannot tell whose it is, so confirm with the user before deleting an
        entry that may be someone else's."""
        return await delete_time_entry_fn(
            client, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def duplicate_time_entry(
        time_entry_id: str, workspace_id: str | None = None
    ) -> Any:
        """Duplicate one of YOUR OWN time entries (time-tracking mode always targets
        the authenticated user)."""
        user_id = await client.current_user_id()
        return await duplicate_time_entry_fn(
            client, user_id=user_id, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def bulk_update_time_entries(
        entries: list[dict[str, Any]], workspace_id: str | None = None
    ) -> Any:
        """Bulk-edit YOUR OWN time entries (time-tracking mode always targets the
        authenticated user). Each entry dict MUST include its 'id'."""
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
