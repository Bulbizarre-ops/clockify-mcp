"""Scheduling domain: assignments + capacity totals (read + write).

Endpoints under ``workspaces/{ws}/scheduling/assignments/...`` on the regular
host. The totals reads are POSTs (filters travel in the body). Create lives at
``.../recurring`` and makes one-off or recurring assignments via the optional
recurringAssignment object. Scheduling is a paid Clockify feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# --- Parameter descriptions (surfaced to MCP clients via the tool input schema) ---
_WorkspaceId = Annotated[
    str | None,
    Field(description="Workspace id; omit to use the configured default_workspace_id."),
]
_Start = Annotated[
    str,
    Field(description="Range start, ISO-8601 datetime (required)."),
]
_End = Annotated[
    str,
    Field(description="Range end, ISO-8601 datetime (required)."),
]
_NameFilter = Annotated[
    str | None,
    Field(description="Filter assignments by name."),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort by: PROJECT, USER, or ID."),
]
_SortOrder = Annotated[
    str | None,
    Field(description="Sort direction: ASCENDING or DESCENDING."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of results per page."),
]
_Search = Annotated[
    str | None,
    Field(description="Free-text search term applied to the totals filter."),
]
_StatusFilter = Annotated[
    str | None,
    Field(description="Filter by publish status: PUBLISHED, UNPUBLISHED, or ALL."),
]
_AssignmentId = Annotated[
    str,
    Field(description="Id of the scheduled assignment (opaque string)."),
]
_UserId = Annotated[
    str,
    Field(description="Id of the user the assignment is for (opaque string)."),
]
_ProjectId = Annotated[
    str,
    Field(description="Id of the project the assignment is on (opaque string)."),
]
_HoursPerDay = Annotated[
    float,
    Field(description="Daily scheduled hours for the assignment."),
]
_HoursPerDayOpt = Annotated[
    float | None,
    Field(description="Daily scheduled hours; omit to leave unchanged."),
]
_TaskId = Annotated[
    str | None,
    Field(description="Optional task id to scope the assignment within the project."),
]
_Note = Annotated[
    str | None,
    Field(description="Optional free-text note on the assignment."),
]
_Billable = Annotated[
    bool | None,
    Field(description="Whether the assigned time is billable."),
]
_IncludeNonWorkingDays = Annotated[
    bool | None,
    Field(description="When true, spread hours across non-working days too."),
]
_StartTime = Annotated[
    str | None,
    Field(description="Daily start time in hh:mm:ss format."),
]
_Repeat = Annotated[
    bool | None,
    Field(description="When true (with 'weeks'), make the assignment recurring."),
]
_Weeks = Annotated[
    int | None,
    Field(description="Number of weeks to recur; pass to create a recurring assignment."),
]
_SeriesUpdateOption = Annotated[
    str | None,
    Field(
        description="For a recurring series, scope of the change: "
        "THIS_ONE, THIS_AND_FOLLOWING, or ALL."
    ),
]
_NotifyUsers = Annotated[
    bool | None,
    Field(description="When true, notify users about the published assignments."),
]
_ViewType = Annotated[
    str | None,
    Field(description="Publish view scope: PROJECTS, TEAM, or ALL."),
]
_CopyUserId = Annotated[
    str,
    Field(description="Id of the user to copy the assignment to (opaque string)."),
]


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


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_scheduled_assignments(
        start: _Start,
        end: _End,
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List individual scheduled assignments in a date range; unlike the *_totals
        tools, this returns the raw assignment records rather than aggregated capacity.

        Read-only. Scoped to one workspace (defaults to the configured workspace).
        Requires start/end (ISO-8601). sort_column is PROJECT/USER/ID; sort_order is
        ASCENDING/DESCENDING. Results are paginated (page/page_size). Returns a list of
        assignment objects. Scheduling is a paid Clockify feature.
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
        start: _Start,
        end: _End,
        workspace_id: _WorkspaceId = None,
        search: _Search = None,
        status_filter: _StatusFilter = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """Get scheduled-assignment totals aggregated per project; use
        get_user_scheduling_totals for the same aggregation grouped by user, or
        list_scheduled_assignments for the un-aggregated records.

        Read-only. Scoped to one workspace (defaults to the configured workspace).
        Filters travel in a POST body. Requires start/end. status_filter is
        PUBLISHED/UNPUBLISHED/ALL. Results are paginated (page/page_size). Returns
        per-project total objects. Scheduling is a paid Clockify feature.
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
        start: _Start,
        end: _End,
        workspace_id: _WorkspaceId = None,
        search: _Search = None,
        status_filter: _StatusFilter = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """Get users' scheduling capacity totals aggregated per user; use
        get_project_scheduling_totals for the same aggregation grouped by project, or
        list_scheduled_assignments for the un-aggregated records.

        Read-only. Scoped to one workspace (defaults to the configured workspace).
        Filters travel in a POST body. Requires start/end. status_filter is
        PUBLISHED/UNPUBLISHED/ALL. Results are paginated (page/page_size). Returns
        per-user total objects. Scheduling is a paid Clockify feature.
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


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_assignment(
        user_id: _UserId,
        project_id: _ProjectId,
        start: _Start,
        end: _End,
        hours_per_day: _HoursPerDay,
        workspace_id: _WorkspaceId = None,
        task_id: _TaskId = None,
        note: _Note = None,
        billable: _Billable = None,
        include_non_working_days: _IncludeNonWorkingDays = None,
        start_time: _StartTime = None,
        repeat: _Repeat = None,
        weeks: _Weeks = None,
    ) -> Any:
        """Create a scheduled assignment for a user on a project; pass 'weeks' (and
        'repeat') to make it a recurring series instead of a one-off.

        Write operation. Scoped to one workspace (defaults to the configured workspace).
        start/end are ISO-8601; hours_per_day is the daily hours; start_time is hh:mm:ss.
        Returns the created assignment object. Scheduling is a paid Clockify feature.
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
        assignment_id: _AssignmentId,
        start: _Start,
        end: _End,
        workspace_id: _WorkspaceId = None,
        hours_per_day: _HoursPerDayOpt = None,
        task_id: _TaskId = None,
        note: _Note = None,
        billable: _Billable = None,
        include_non_working_days: _IncludeNonWorkingDays = None,
        start_time: _StartTime = None,
        series_update_option: _SeriesUpdateOption = None,
    ) -> Any:
        """Update an existing assignment identified by assignment_id; use create_assignment
        to make a new one and copy_assignment to clone one to another user.

        Write operation. Scoped to one workspace (defaults to the configured workspace).
        start/end are required. series_update_option is THIS_ONE/THIS_AND_FOLLOWING/ALL —
        it controls how the change propagates across a recurring series. Returns the
        updated assignment object. Scheduling is a paid Clockify feature.
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
        assignment_id: _AssignmentId,
        workspace_id: _WorkspaceId = None,
        series_update_option: _SeriesUpdateOption = None,
    ) -> Any:
        """Permanently delete a scheduled assignment by id.

        Write operation. IRREVERSIBLE — the assignment is permanently removed. Scoped to
        one workspace (defaults to the configured workspace). series_update_option is
        THIS_ONE/THIS_AND_FOLLOWING/ALL and controls which occurrences of a recurring
        series are removed. Scheduling is a paid Clockify feature.
        """
        return await delete_assignment_fn(
            client,
            assignment_id=assignment_id,
            workspace_id=workspace_id,
            series_update_option=series_update_option,
        )

    @mcp.tool()
    async def publish_assignments(
        start: _Start,
        end: _End,
        workspace_id: _WorkspaceId = None,
        notify_users: _NotifyUsers = None,
        search: _Search = None,
        view_type: _ViewType = None,
    ) -> Any:
        """Publish (release to users) all scheduled assignments in a date range; this is a
        bulk range operation rather than a single-assignment edit like update_assignment.

        Write operation. Scoped to one workspace (defaults to the configured workspace).
        start/end are required. Set notify_users to alert affected users. view_type is
        PROJECTS/TEAM/ALL. Scheduling is a paid Clockify feature.
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
        assignment_id: _AssignmentId,
        user_id: _CopyUserId,
        workspace_id: _WorkspaceId = None,
        series_update_option: _SeriesUpdateOption = None,
    ) -> Any:
        """Clone an existing assignment onto another user; unlike update_assignment this
        leaves the original intact and creates a copy for the target user_id.

        Write operation. Scoped to one workspace (defaults to the configured workspace).
        user_id is the destination user. series_update_option is
        THIS_ONE/THIS_AND_FOLLOWING/ALL for recurring series. Returns the copied
        assignment object. Scheduling is a paid Clockify feature.
        """
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
