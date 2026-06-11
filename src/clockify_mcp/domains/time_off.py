"""Time-off domain: policies, balances, and requests (read + write).

All endpoints live on the regular Clockify host under
``workspaces/{workspaceId}/time-off/...``. Listing requests is a POST (the
filter travels in the JSON body). Approve/reject PATCH the request status
(enum APPROVED|REJECTED); withdrawal/cancellation is a DELETE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none, ids_filter
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
_PolicyId = Annotated[
    str,
    Field(description="Id of the time-off policy (from list_time_off_policies)."),
]
_RequestId = Annotated[
    str,
    Field(description="Id of the time-off request (from list_time_off_requests)."),
]
_UserId = Annotated[
    str,
    Field(description="Id of the user/member whose balances to list."),
]
_PolicyNameFilter = Annotated[
    str | None,
    Field(description="Filter policies by name."),
]
_PolicyStatusFilter = Annotated[
    str | None,
    Field(description="Filter policies by status: ACTIVE, ARCHIVED, or ALL."),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort policies by."),
]
_BalanceSort = Annotated[
    str | None,
    Field(description="Balance sort key: USER, POLICY, USED, BALANCE, or TOTAL."),
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
_RequestStart = Annotated[
    str | None,
    Field(description="ISO-8601 start timestamp bounding the request filter."),
]
_RequestEnd = Annotated[
    str | None,
    Field(description="ISO-8601 end timestamp bounding the request filter."),
]
_StatusesFilter = Annotated[
    list[str] | None,
    Field(description="Filter by request status: PENDING, APPROVED, REJECTED, or ALL."),
]
_UsersFilter = Annotated[
    list[str] | None,
    Field(description="Filter requests by member ids."),
]
_UserGroupsFilter = Annotated[
    list[str] | None,
    Field(description="Filter requests by user-group ids."),
]
_PolicyName = Annotated[
    str,
    Field(description="Display name for the new time-off policy."),
]
_RequiresApproval = Annotated[
    bool,
    Field(description="Whether requests under this policy require approval."),
]
_TeamManagers = Annotated[
    bool,
    Field(description="When true, the requester's team managers are approvers."),
]
_SpecificMembers = Annotated[
    bool,
    Field(description="When true, approval is restricted to approver_user_ids."),
]
_ApproverUserIds = Annotated[
    list[str] | None,
    Field(description="Approver member ids (used when specific_members is true)."),
]
_Color = Annotated[
    str | None,
    Field(description="Hex color for the policy."),
]
_Icon = Annotated[
    str | None,
    Field(
        description="Policy icon (e.g. UMBRELLA, PLANE, STETHOSCOPE)."
    ),
]
_TimeUnit = Annotated[
    str,
    Field(description="Unit the policy is measured in: DAYS (default) or HOURS."),
]
_AllowHalfDay = Annotated[
    bool | None,
    Field(description="Allow half-day requests under this policy."),
]
_AllowNegativeBalance = Annotated[
    bool | None,
    Field(description="Allow members to go into a negative balance."),
]
_EveryoneIncludingNew = Annotated[
    bool | None,
    Field(
        description="Assign the policy to everyone, including newly added members. "
        "Supply this, or users/user_groups, or the API rejects the policy."
    ),
]
_AssignUsers = Annotated[
    list[str] | None,
    Field(description="Member ids to assign the policy to."),
]
_AssignUserGroups = Annotated[
    list[str] | None,
    Field(description="User-group ids to assign the policy to."),
]
_RequestStartDate = Annotated[
    str,
    Field(description="Request start date (YYYY-MM-DD)."),
]
_RequestEndDate = Annotated[
    str,
    Field(description="Request end date (YYYY-MM-DD)."),
]
_Days = Annotated[
    int,
    Field(description="Number of days requested."),
]
_Note = Annotated[
    str | None,
    Field(description="Optional note attached to the request or action."),
]
_IsHalfDay = Annotated[
    bool | None,
    Field(description="Whether the request is for a half day."),
]
_HalfDayPeriod = Annotated[
    str | None,
    Field(
        description="Which half (only when is_half_day): "
        "FIRST_HALF, SECOND_HALF, or NOT_DEFINED."
    ),
]


async def list_time_off_policies(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    status: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List time-off policies on the workspace (paginated).

    status is one of ACTIVE, ARCHIVED, ALL. sort_order is ASCENDING or DESCENDING.
    Time off is a paid Clockify feature; on plans without it the API returns an error.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "status": status,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/time-off/policies", params=params)


async def get_time_off_policy(
    client: ClockifyClient, *, policy_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single time-off policy by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/time-off/policies/{policy_id}")


async def list_time_off_balances_by_policy(
    client: ClockifyClient,
    *,
    policy_id: str,
    workspace_id: str | None = None,
    sort: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List per-user time-off balances for a policy (paginated).

    sort is one of USER, POLICY, USED, BALANCE, TOTAL; sort_order ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "sort": sort,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(
        f"workspaces/{ws}/time-off/balance/policy/{policy_id}", params=params
    )


async def list_time_off_balances_by_user(
    client: ClockifyClient,
    *,
    user_id: str,
    workspace_id: str | None = None,
    sort: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List a user's time-off balances across policies (paginated).

    sort is one of USER, POLICY, USED, BALANCE, TOTAL; sort_order ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "sort": sort,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(
        f"workspaces/{ws}/time-off/balance/user/{user_id}", params=params
    )


async def list_time_off_requests(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    statuses: list[str] | None = None,
    users: list[str] | None = None,
    user_groups: list[str] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List/filter time-off requests (the filter travels in a POST body).

    start/end are ISO-8601 timestamps. statuses items are PENDING, APPROVED,
    REJECTED, or ALL. users/user_groups filter by member or group id.
    """
    ws = resolve_workspace_id(client, workspace_id)
    # Pagination travels in the POST body (camelCase) for this filter endpoint,
    # not as query params via page_params() like the GET list tools.
    body = drop_none(
        {
            "start": start,
            "end": end,
            "statuses": statuses,
            "users": users,
            "userGroups": user_groups,
            "page": page,
            "pageSize": page_size,
        }
    )
    return await client.post(f"workspaces/{ws}/time-off/requests", json=body)


async def create_time_off_policy(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    requires_approval: bool = False,
    team_managers: bool = False,
    specific_members: bool = False,
    approver_user_ids: list[str] | None = None,
    color: str | None = None,
    icon: str | None = None,
    time_unit: str = "DAYS",
    allow_half_day: bool | None = None,
    allow_negative_balance: bool | None = None,
    everyone_including_new: bool | None = None,
    users: list[str] | None = None,
    user_groups: list[str] | None = None,
) -> Any:
    """Create a time-off policy on the workspace.

    The approval rule is required by the API and is built from requires_approval,
    team_managers, specific_members, and approver_user_ids. time_unit is DAYS
    (default) or HOURS and is required by the API; icon is one of the Clockify
    policy icons (e.g. UMBRELLA, PLANE,
    STETHOSCOPE). The policy must be assigned to members — pass
    everyone_including_new=True, or supply users/user_groups, or the API rejects it
    with "assign at least one user or user group". Time off is a paid feature; the
    API errors on plans without it.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "color": color,
            "icon": icon,
            "timeUnit": time_unit,
            "allowHalfDay": allow_half_day,
            "allowNegativeBalance": allow_negative_balance,
            "everyoneIncludingNew": everyone_including_new,
            "users": ids_filter(users) if users else None,
            "userGroups": ids_filter(user_groups) if user_groups else None,
            "approve": {
                "requiresApproval": requires_approval,
                "teamManagers": team_managers,
                "specificMembers": specific_members,
                "userIds": approver_user_ids or [],
            },
        }
    )
    return await client.post(f"workspaces/{ws}/time-off/policies", json=body)


async def create_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    start: str,
    end: str,
    days: int,
    workspace_id: str | None = None,
    note: str | None = None,
    is_half_day: bool | None = None,
    half_day_period: str | None = None,
) -> Any:
    """Create a time-off request for the authenticated user under a policy.

    start/end are dates (YYYY-MM-DD); days is the number of days requested.
    half_day_period is FIRST_HALF, SECOND_HALF, or NOT_DEFINED (only meaningful
    when is_half_day is True).
    """
    ws = resolve_workspace_id(client, workspace_id)
    time_off_period = drop_none(
        {
            "period": {"start": start, "end": end, "days": days},
            "isHalfDay": is_half_day,
            "halfDayPeriod": half_day_period,
        }
    )
    body = drop_none({"note": note, "timeOffPeriod": time_off_period})
    return await client.post(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests", json=body
    )


async def approve_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    request_id: str,
    workspace_id: str | None = None,
    note: str | None = None,
) -> Any:
    """Approve a time-off request (sets status APPROVED)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"status": "APPROVED", "note": note})
    return await client.patch(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests/{request_id}", json=body
    )


async def reject_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    request_id: str,
    workspace_id: str | None = None,
    note: str | None = None,
) -> Any:
    """Reject a time-off request (sets status REJECTED)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"status": "REJECTED", "note": note})
    return await client.patch(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests/{request_id}", json=body
    )


async def withdraw_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    request_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Withdraw/cancel a time-off request. IRREVERSIBLE — the request is deleted."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests/{request_id}"
    )


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_time_off_policies(
        workspace_id: _WorkspaceId = None,
        name: _PolicyNameFilter = None,
        status: _PolicyStatusFilter = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List time-off policies defined on a workspace.

        Read-only; results are paginated. Filter by status (ACTIVE, ARCHIVED,
        ALL) and name. Use this to discover policy ids before creating requests
        or listing balances; use get_time_off_policy when you already know the
        id. Time off is a paid Clockify feature — the API errors on plans
        without it. Returns a list of policy objects.
        """
        return await list_time_off_policies_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            status=status,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_time_off_policy(
        policy_id: _PolicyId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Get a single time-off policy's full detail by its id.

        Read-only. Use list_time_off_policies first to look up the id when you
        only know the policy name. Returns one policy object.
        """
        return await get_time_off_policy_fn(
            client, policy_id=policy_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def list_time_off_balances_by_policy(
        policy_id: _PolicyId,
        workspace_id: _WorkspaceId = None,
        sort: _BalanceSort = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List every user's time-off balance for one policy.

        Read-only; results are paginated. This pivots on the policy (one policy,
        all users); use list_time_off_balances_by_user to pivot on a user (one
        user, all policies). sort is one of USER, POLICY, USED, BALANCE, TOTAL.
        Returns a list of per-user balance objects.
        """
        return await list_time_off_balances_by_policy_fn(
            client,
            policy_id=policy_id,
            workspace_id=workspace_id,
            sort=sort,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def list_time_off_balances_by_user(
        user_id: _UserId,
        workspace_id: _WorkspaceId = None,
        sort: _BalanceSort = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List one user's time-off balances across every policy.

        Read-only; results are paginated. This pivots on the user (one user, all
        policies); use list_time_off_balances_by_policy to pivot on a policy (one
        policy, all users). sort is one of USER, POLICY, USED, BALANCE, TOTAL.
        Returns a list of per-policy balance objects.
        """
        return await list_time_off_balances_by_user_fn(
            client,
            user_id=user_id,
            workspace_id=workspace_id,
            sort=sort,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def list_time_off_requests(
        workspace_id: _WorkspaceId = None,
        start: _RequestStart = None,
        end: _RequestEnd = None,
        statuses: _StatusesFilter = None,
        users: _UsersFilter = None,
        user_groups: _UserGroupsFilter = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List and filter time-off requests across the workspace.

        Read-only; the filter (date range, statuses, users, user_groups) travels
        in a POST body and results are paginated via that same body. statuses
        items are PENDING, APPROVED, REJECTED, or ALL. Use this to discover
        request ids before approving, rejecting, or withdrawing them. Returns a
        list of request objects.
        """
        return await list_time_off_requests_fn(
            client,
            workspace_id=workspace_id,
            start=start,
            end=end,
            statuses=statuses,
            users=users,
            user_groups=user_groups,
            page=page,
            page_size=page_size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_time_off_policy(
        name: _PolicyName,
        workspace_id: _WorkspaceId = None,
        requires_approval: _RequiresApproval = False,
        team_managers: _TeamManagers = False,
        specific_members: _SpecificMembers = False,
        approver_user_ids: _ApproverUserIds = None,
        color: _Color = None,
        icon: _Icon = None,
        time_unit: _TimeUnit = "DAYS",
        allow_half_day: _AllowHalfDay = None,
        allow_negative_balance: _AllowNegativeBalance = None,
        everyone_including_new: _EveryoneIncludingNew = None,
        users: _AssignUsers = None,
        user_groups: _AssignUserGroups = None,
    ) -> Any:
        """Create a time-off policy on a workspace.

        Write operation. The approval rule is built from requires_approval,
        team_managers, specific_members, and approver_user_ids. time_unit is DAYS
        (default) or HOURS. The policy MUST be assigned to members — pass
        everyone_including_new=True or supply users/user_groups, or the API
        rejects it. Time off is a paid feature. Returns the created policy
        including its new id.
        """
        return await create_time_off_policy_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            requires_approval=requires_approval,
            team_managers=team_managers,
            specific_members=specific_members,
            approver_user_ids=approver_user_ids,
            color=color,
            icon=icon,
            time_unit=time_unit,
            allow_half_day=allow_half_day,
            allow_negative_balance=allow_negative_balance,
            everyone_including_new=everyone_including_new,
            users=users,
            user_groups=user_groups,
        )

    @mcp.tool()
    async def create_time_off_request(
        policy_id: _PolicyId,
        start: _RequestStartDate,
        end: _RequestEndDate,
        days: _Days,
        workspace_id: _WorkspaceId = None,
        note: _Note = None,
        is_half_day: _IsHalfDay = None,
        half_day_period: _HalfDayPeriod = None,
    ) -> Any:
        """Create a time-off request for the authenticated user under a policy.

        Write operation; the request is always self-scoped to the authenticated
        user. start/end are dates (YYYY-MM-DD) and days is the number of days
        requested. half_day_period (FIRST_HALF, SECOND_HALF, NOT_DEFINED) is only
        meaningful when is_half_day is True. Returns the created request. Approve,
        reject, or withdraw it later with the corresponding tools.
        """
        return await create_time_off_request_fn(
            client,
            policy_id=policy_id,
            start=start,
            end=end,
            days=days,
            workspace_id=workspace_id,
            note=note,
            is_half_day=is_half_day,
            half_day_period=half_day_period,
        )

    @mcp.tool()
    async def approve_time_off_request(
        policy_id: _PolicyId,
        request_id: _RequestId,
        workspace_id: _WorkspaceId = None,
        note: _Note = None,
    ) -> Any:
        """Approve a pending time-off request, setting its status to APPROVED.

        Write operation; PATCHes the request status. Use reject_time_off_request
        to deny it instead, or withdraw_time_off_request to cancel it entirely.
        Discover request ids with list_time_off_requests. Returns the updated
        request.
        """
        return await approve_time_off_request_fn(
            client,
            policy_id=policy_id,
            request_id=request_id,
            workspace_id=workspace_id,
            note=note,
        )

    @mcp.tool()
    async def reject_time_off_request(
        policy_id: _PolicyId,
        request_id: _RequestId,
        workspace_id: _WorkspaceId = None,
        note: _Note = None,
    ) -> Any:
        """Reject a pending time-off request, setting its status to REJECTED.

        Write operation; PATCHes the request status. Use approve_time_off_request
        to grant it instead, or withdraw_time_off_request to cancel it entirely.
        Discover request ids with list_time_off_requests. Returns the updated
        request.
        """
        return await reject_time_off_request_fn(
            client,
            policy_id=policy_id,
            request_id=request_id,
            workspace_id=workspace_id,
            note=note,
        )

    @mcp.tool()
    async def withdraw_time_off_request(
        policy_id: _PolicyId,
        request_id: _RequestId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Withdraw/cancel a time-off request, deleting it.

        Write operation and IRREVERSIBLE — the request is removed (a DELETE),
        unlike approve/reject which only change its status. Discover request ids
        with list_time_off_requests.
        """
        return await withdraw_time_off_request_fn(
            client, policy_id=policy_id, request_id=request_id, workspace_id=workspace_id
        )


list_time_off_policies_fn = list_time_off_policies
get_time_off_policy_fn = get_time_off_policy
list_time_off_balances_by_policy_fn = list_time_off_balances_by_policy
list_time_off_balances_by_user_fn = list_time_off_balances_by_user
list_time_off_requests_fn = list_time_off_requests
create_time_off_policy_fn = create_time_off_policy
create_time_off_request_fn = create_time_off_request
approve_time_off_request_fn = approve_time_off_request
reject_time_off_request_fn = reject_time_off_request
withdraw_time_off_request_fn = withdraw_time_off_request
