"""Holidays domain (read + write).

Holidays live on the regular Clockify host under ``workspaces/{workspaceId}/
holidays``. Holidays are a paid Clockify feature; the API errors on plans
without it. ``update_holiday`` is a full replace and requires occurs_annually.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none, ids_filter
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# --- Parameter descriptions (surfaced to MCP clients via the tool input schema) ---
_WorkspaceId = Annotated[
    str | None,
    Field(description="Workspace id; omit to use the configured default_workspace_id."),
]
_HolidayId = Annotated[
    str,
    Field(description="Id of the holiday (opaque string returned by list_holidays)."),
]
_AssignedToFilter = Annotated[
    str | None,
    Field(
        description="User id; when set, return only holidays assigned to that user "
        "(omit for all workspace holidays)."
    ),
]
_AssignedToRequired = Annotated[
    str,
    Field(description="User id whose holidays overlapping the date range are returned."),
]
_PeriodStart = Annotated[
    str,
    Field(description="Range start date (YYYY-MM-DD); required by the in-period query."),
]
_PeriodEnd = Annotated[
    str,
    Field(description="Range end date (YYYY-MM-DD); required by the in-period query."),
]
_Name = Annotated[
    str,
    Field(description="Display name of the holiday."),
]
_StartDate = Annotated[
    str,
    Field(description="Holiday start date (YYYY-MM-DD)."),
]
_EndDate = Annotated[
    str,
    Field(description="Holiday end date (YYYY-MM-DD)."),
]
_OccursAnnuallyOptional = Annotated[
    bool | None,
    Field(description="When true, the holiday repeats every year."),
]
_OccursAnnuallyRequired = Annotated[
    bool,
    Field(description="Whether the holiday repeats every year (required on update)."),
]
_Color = Annotated[
    str | None,
    Field(description="Display color for the holiday."),
]
_EveryoneIncludingNew = Annotated[
    bool | None,
    Field(
        description="When true, assign to all current and future members; satisfies "
        "the required-assignee rule on its own."
    ),
]
_Users = Annotated[
    list[str] | None,
    Field(description="User ids to assign the holiday to (one assignee form)."),
]
_UserGroups = Annotated[
    list[str] | None,
    Field(description="User-group ids to assign the holiday to (one assignee form)."),
]


async def list_holidays(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    assigned_to: str | None = None,
) -> Any:
    """List holidays on the workspace, optionally filtered to a user's assignments.

    assigned_to is a user id; when omitted all workspace holidays are returned.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {"assigned-to": assigned_to}
    return await client.get(f"workspaces/{ws}/holidays", params=params)


async def list_holidays_in_period(
    client: ClockifyClient,
    *,
    assigned_to: str,
    start: str,
    end: str,
    workspace_id: str | None = None,
) -> Any:
    """List holidays overlapping a date range for a user.

    assigned_to (user id), start, and end (YYYY-MM-DD) are all required by the API.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {"assigned-to": assigned_to, "start": start, "end": end}
    return await client.get(f"workspaces/{ws}/holidays/in-period", params=params)


async def create_holiday(
    client: ClockifyClient,
    *,
    name: str,
    start_date: str,
    end_date: str,
    workspace_id: str | None = None,
    color: str | None = None,
    occurs_annually: bool | None = None,
    everyone_including_new: bool | None = None,
    users: list[str] | None = None,
    user_groups: list[str] | None = None,
) -> Any:
    """Create a holiday on the workspace.

    start_date/end_date are YYYY-MM-DD. occurs_annually repeats it every year;
    everyone_including_new assigns it to all current and future members. The holiday
    must be assigned to someone — pass everyone_including_new=True, or supply
    users/user_groups, or the API rejects it with "assign at least one user or user
    group".
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "color": color,
            "occursAnnually": occurs_annually,
            "everyoneIncludingNew": everyone_including_new,
            "users": ids_filter(users) if users else None,
            "userGroups": ids_filter(user_groups) if user_groups else None,
            "datePeriod": {"startDate": start_date, "endDate": end_date},
        }
    )
    return await client.post(f"workspaces/{ws}/holidays", json=body)


async def update_holiday(
    client: ClockifyClient,
    *,
    holiday_id: str,
    name: str,
    start_date: str,
    end_date: str,
    occurs_annually: bool,
    workspace_id: str | None = None,
    color: str | None = None,
    everyone_including_new: bool | None = None,
    users: list[str] | None = None,
    user_groups: list[str] | None = None,
) -> Any:
    """Update a holiday (full replace). name, the date range, and occurs_annually
    are required by the API; start_date/end_date are YYYY-MM-DD. Also pass
    everyone_including_new=True, or supply users/user_groups (the API requires an
    assignee on update too).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "occursAnnually": occurs_annually,
            "color": color,
            "everyoneIncludingNew": everyone_including_new,
            "users": ids_filter(users) if users else None,
            "userGroups": ids_filter(user_groups) if user_groups else None,
            "datePeriod": {"startDate": start_date, "endDate": end_date},
        }
    )
    return await client.put(f"workspaces/{ws}/holidays/{holiday_id}", json=body)


async def delete_holiday(
    client: ClockifyClient, *, holiday_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a holiday. IRREVERSIBLE — the holiday is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/holidays/{holiday_id}")


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_holidays(
        workspace_id: _WorkspaceId = None, assigned_to: _AssignedToFilter = None
    ) -> Any:
        """List holidays defined on a workspace, optionally narrowed to one user.

        Read-only. Pass assigned_to to return only that user's holidays; omit it for
        every workspace holiday. Use list_holidays_in_period instead when you need
        the holidays that overlap a specific date range for a user. Holidays are a
        paid Clockify feature, so the API errors on plans without it. Returns a list
        of holiday objects (id, name, date period, assignees).
        """
        return await list_holidays_fn(
            client, workspace_id=workspace_id, assigned_to=assigned_to
        )

    @mcp.tool()
    async def list_holidays_in_period(
        assigned_to: _AssignedToRequired,
        start: _PeriodStart,
        end: _PeriodEnd,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """List a user's holidays that overlap a given date range.

        Read-only; assigned_to (user id), start, and end (YYYY-MM-DD) are all required
        by the API. Unlike list_holidays, this is date-range scoped — use it to find
        holidays affecting a user within a window, and list_holidays for the full,
        optionally user-filtered set. Returns a list of holiday objects.
        """
        return await list_holidays_in_period_fn(
            client, assigned_to=assigned_to, start=start, end=end, workspace_id=workspace_id
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_holiday(
        name: _Name,
        start_date: _StartDate,
        end_date: _EndDate,
        workspace_id: _WorkspaceId = None,
        color: _Color = None,
        occurs_annually: _OccursAnnuallyOptional = None,
        everyone_including_new: _EveryoneIncludingNew = None,
        users: _Users = None,
        user_groups: _UserGroups = None,
    ) -> Any:
        """Create a holiday on a workspace.

        Write operation. start_date/end_date are YYYY-MM-DD; occurs_annually repeats
        it every year. The holiday must be assigned to someone, so pass
        everyone_including_new=True, or supply users/user_groups, or the API rejects
        it with "assign at least one user or user group". Use update_holiday to change
        an existing one. Returns the created holiday including its new id.
        """
        return await create_holiday_fn(
            client,
            name=name,
            start_date=start_date,
            end_date=end_date,
            workspace_id=workspace_id,
            color=color,
            occurs_annually=occurs_annually,
            everyone_including_new=everyone_including_new,
            users=users,
            user_groups=user_groups,
        )

    @mcp.tool()
    async def update_holiday(
        holiday_id: _HolidayId,
        name: _Name,
        start_date: _StartDate,
        end_date: _EndDate,
        occurs_annually: _OccursAnnuallyRequired,
        workspace_id: _WorkspaceId = None,
        color: _Color = None,
        everyone_including_new: _EveryoneIncludingNew = None,
        users: _Users = None,
        user_groups: _UserGroups = None,
    ) -> Any:
        """Update a holiday by id (full replace, not a partial patch).

        Write operation. Because it fully replaces the holiday, name, the date range,
        and occurs_annually are all required; start_date/end_date are YYYY-MM-DD. As on
        create, you must also supply an assignee — pass everyone_including_new=True or
        users/user_groups. Use create_holiday to add a new one and delete_holiday to
        remove it. Returns the updated holiday.
        """
        return await update_holiday_fn(
            client,
            holiday_id=holiday_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            occurs_annually=occurs_annually,
            workspace_id=workspace_id,
            color=color,
            everyone_including_new=everyone_including_new,
            users=users,
            user_groups=user_groups,
        )

    @mcp.tool()
    async def delete_holiday(
        holiday_id: _HolidayId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Permanently delete a holiday from a workspace by id.

        Write operation and IRREVERSIBLE — the holiday is permanently removed. Use
        update_holiday if you only need to change its dates or assignees rather than
        remove it.
        """
        return await delete_holiday_fn(
            client, holiday_id=holiday_id, workspace_id=workspace_id
        )


list_holidays_fn = list_holidays
list_holidays_in_period_fn = list_holidays_in_period
create_holiday_fn = create_holiday
update_holiday_fn = update_holiday
delete_holiday_fn = delete_holiday
