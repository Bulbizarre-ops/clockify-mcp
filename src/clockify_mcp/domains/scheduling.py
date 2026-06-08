"""Scheduling domain: assignments + capacity totals (read + write).

Endpoints under ``workspaces/{ws}/scheduling/assignments/...`` on the regular
host. The totals reads are POSTs (filters travel in the body). Create lives at
``.../recurring`` and makes one-off or recurring assignments via the optional
recurringAssignment object. Scheduling is a paid Clockify feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_scheduled_assignments(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    name: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List scheduled assignments in a date range (start/end ISO-8601, required).

    sort_column is PROJECT/USER/ID; sort_order is ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "start": start,
        "end": end,
        "name": name,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/scheduling/assignments/all", params=params)


async def get_project_scheduling_totals(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """Get scheduled-assignment totals per project (POST filter body).

    start/end required. status_filter is PUBLISHED/UNPUBLISHED/ALL.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "search": search,
            "statusFilter": status_filter,
            "page": page,
            "pageSize": page_size,
        }
    )
    return await client.post(
        f"workspaces/{ws}/scheduling/assignments/projects/totals", json=body
    )


async def get_user_scheduling_totals(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """Get users' scheduling capacity totals (POST filter body).

    start/end required. status_filter is PUBLISHED/UNPUBLISHED/ALL.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "search": search,
            "statusFilter": status_filter,
            "page": page,
            "pageSize": page_size,
        }
    )
    return await client.post(
        f"workspaces/{ws}/scheduling/assignments/user-filter/totals", json=body
    )


async def create_assignment(
    client: ClockifyClient,
    *,
    user_id: str,
    project_id: str,
    start: str,
    end: str,
    hours_per_day: float,
    workspace_id: str | None = None,
    task_id: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    include_non_working_days: bool | None = None,
    start_time: str | None = None,
    repeat: bool | None = None,
    weeks: int | None = None,
) -> Any:
    """Create a scheduled assignment. Pass weeks (and repeat) to make it recurring.

    start/end are ISO-8601; hours_per_day is the daily hours; start_time is hh:mm:ss.
    """
    ws = resolve_workspace_id(client, workspace_id)
    recurring = drop_none({"repeat": repeat, "weeks": weeks}) if weeks is not None else None
    body = drop_none(
        {
            "userId": user_id,
            "projectId": project_id,
            "start": start,
            "end": end,
            "hoursPerDay": hours_per_day,
            "taskId": task_id,
            "note": note,
            "billable": billable,
            "includeNonWorkingDays": include_non_working_days,
            "startTime": start_time,
            "recurringAssignment": recurring,
        }
    )
    return await client.post(f"workspaces/{ws}/scheduling/assignments/recurring", json=body)


async def update_assignment(
    client: ClockifyClient,
    *,
    assignment_id: str,
    start: str,
    end: str,
    workspace_id: str | None = None,
    hours_per_day: float | None = None,
    task_id: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    include_non_working_days: bool | None = None,
    start_time: str | None = None,
    series_update_option: str | None = None,
) -> Any:
    """Update an assignment (start/end required).

    series_update_option is THIS_ONE/THIS_AND_FOLLOWING/ALL — controls how the
    change propagates across a recurring series.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "hoursPerDay": hours_per_day,
            "taskId": task_id,
            "note": note,
            "billable": billable,
            "includeNonWorkingDays": include_non_working_days,
            "startTime": start_time,
            "seriesUpdateOption": series_update_option,
        }
    )
    return await client.patch(
        f"workspaces/{ws}/scheduling/assignments/recurring/{assignment_id}", json=body
    )


async def delete_assignment(
    client: ClockifyClient,
    *,
    assignment_id: str,
    workspace_id: str | None = None,
    series_update_option: str | None = None,
) -> Any:
    """Delete an assignment. IRREVERSIBLE. series_update_option is
    THIS_ONE/THIS_AND_FOLLOWING/ALL for recurring series."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"seriesUpdateOption": series_update_option}
    return await client.delete(
        f"workspaces/{ws}/scheduling/assignments/recurring/{assignment_id}", params=params
    )


async def publish_assignments(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    notify_users: bool | None = None,
    search: str | None = None,
    view_type: str | None = None,
) -> Any:
    """Publish scheduled assignments in a date range (start/end required).

    view_type is PROJECTS/TEAM/ALL.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "notifyUsers": notify_users,
            "search": search,
            "viewType": view_type,
        }
    )
    return await client.put(f"workspaces/{ws}/scheduling/assignments/publish", json=body)


async def copy_assignment(
    client: ClockifyClient,
    *,
    assignment_id: str,
    user_id: str,
    workspace_id: str | None = None,
    series_update_option: str | None = None,
) -> Any:
    """Copy an assignment to another user (user_id required)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"userId": user_id, "seriesUpdateOption": series_update_option})
    return await client.post(
        f"workspaces/{ws}/scheduling/assignments/{assignment_id}/copy", json=body
    )


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_scheduled_assignments(
        start: str,
        end: str,
        workspace_id: str | None = None,
        name: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List scheduled assignments in a date range (start/end ISO-8601, required).

        sort_column is PROJECT/USER/ID; sort_order is ASCENDING/DESCENDING.
        """
        return await list_scheduled_assignments_fn(
            client,
            start=start,
            end=end,
            workspace_id=workspace_id,
            name=name,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_project_scheduling_totals(
        start: str,
        end: str,
        workspace_id: str | None = None,
        search: str | None = None,
        status_filter: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """Get scheduled-assignment totals per project (POST filter body).

        start/end required. status_filter is PUBLISHED/UNPUBLISHED/ALL.
        """
        return await get_project_scheduling_totals_fn(
            client,
            start=start,
            end=end,
            workspace_id=workspace_id,
            search=search,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_user_scheduling_totals(
        start: str,
        end: str,
        workspace_id: str | None = None,
        search: str | None = None,
        status_filter: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """Get users' scheduling capacity totals (POST filter body).

        start/end required. status_filter is PUBLISHED/UNPUBLISHED/ALL.
        """
        return await get_user_scheduling_totals_fn(
            client,
            start=start,
            end=end,
            workspace_id=workspace_id,
            search=search,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_assignment(
        user_id: str,
        project_id: str,
        start: str,
        end: str,
        hours_per_day: float,
        workspace_id: str | None = None,
        task_id: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        include_non_working_days: bool | None = None,
        start_time: str | None = None,
        repeat: bool | None = None,
        weeks: int | None = None,
    ) -> Any:
        """Create a scheduled assignment. Pass weeks (and repeat) to make it recurring.

        start/end are ISO-8601; hours_per_day is the daily hours; start_time is hh:mm:ss.
        """
        return await create_assignment_fn(
            client,
            user_id=user_id,
            project_id=project_id,
            start=start,
            end=end,
            hours_per_day=hours_per_day,
            workspace_id=workspace_id,
            task_id=task_id,
            note=note,
            billable=billable,
            include_non_working_days=include_non_working_days,
            start_time=start_time,
            repeat=repeat,
            weeks=weeks,
        )

    @mcp.tool()
    async def update_assignment(
        assignment_id: str,
        start: str,
        end: str,
        workspace_id: str | None = None,
        hours_per_day: float | None = None,
        task_id: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        include_non_working_days: bool | None = None,
        start_time: str | None = None,
        series_update_option: str | None = None,
    ) -> Any:
        """Update an assignment (start/end required).

        series_update_option is THIS_ONE/THIS_AND_FOLLOWING/ALL — controls how the
        change propagates across a recurring series.
        """
        return await update_assignment_fn(
            client,
            assignment_id=assignment_id,
            start=start,
            end=end,
            workspace_id=workspace_id,
            hours_per_day=hours_per_day,
            task_id=task_id,
            note=note,
            billable=billable,
            include_non_working_days=include_non_working_days,
            start_time=start_time,
            series_update_option=series_update_option,
        )

    @mcp.tool()
    async def delete_assignment(
        assignment_id: str,
        workspace_id: str | None = None,
        series_update_option: str | None = None,
    ) -> Any:
        """Delete an assignment. IRREVERSIBLE. series_update_option is
        THIS_ONE/THIS_AND_FOLLOWING/ALL for recurring series."""
        return await delete_assignment_fn(
            client,
            assignment_id=assignment_id,
            workspace_id=workspace_id,
            series_update_option=series_update_option,
        )

    @mcp.tool()
    async def publish_assignments(
        start: str,
        end: str,
        workspace_id: str | None = None,
        notify_users: bool | None = None,
        search: str | None = None,
        view_type: str | None = None,
    ) -> Any:
        """Publish scheduled assignments in a date range (start/end required).

        view_type is PROJECTS/TEAM/ALL.
        """
        return await publish_assignments_fn(
            client,
            start=start,
            end=end,
            workspace_id=workspace_id,
            notify_users=notify_users,
            search=search,
            view_type=view_type,
        )

    @mcp.tool()
    async def copy_assignment(
        assignment_id: str,
        user_id: str,
        workspace_id: str | None = None,
        series_update_option: str | None = None,
    ) -> Any:
        """Copy an assignment to another user (user_id required)."""
        return await copy_assignment_fn(
            client,
            assignment_id=assignment_id,
            user_id=user_id,
            workspace_id=workspace_id,
            series_update_option=series_update_option,
        )


list_scheduled_assignments_fn = list_scheduled_assignments
get_project_scheduling_totals_fn = get_project_scheduling_totals
get_user_scheduling_totals_fn = get_user_scheduling_totals
create_assignment_fn = create_assignment
update_assignment_fn = update_assignment
delete_assignment_fn = delete_assignment
publish_assignments_fn = publish_assignments
copy_assignment_fn = copy_assignment
