"""Time-off domain: policies, balances, and requests (read + write).

All endpoints live on the regular Clockify host under
``workspaces/{workspaceId}/time-off/...``. Listing requests is a POST (the
filter travels in the JSON body). Approve/reject PATCH the request status
(enum APPROVED|REJECTED); withdrawal/cancellation is a DELETE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none, ids_filter
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


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
        workspace_id: str | None = None,
        name: str | None = None,
        status: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List time-off policies on the workspace (paginated)."""
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
        policy_id: str, workspace_id: str | None = None
    ) -> Any:
        """Get a single time-off policy by id."""
        return await get_time_off_policy_fn(
            client, policy_id=policy_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def list_time_off_balances_by_policy(
        policy_id: str,
        workspace_id: str | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List per-user time-off balances for a policy (paginated)."""
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
        user_id: str,
        workspace_id: str | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List a user's time-off balances across policies (paginated)."""
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
        workspace_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        statuses: list[str] | None = None,
        users: list[str] | None = None,
        user_groups: list[str] | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List/filter time-off requests (filter sent as a POST body)."""
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
        """Create a time-off policy on the workspace."""
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
        policy_id: str,
        start: str,
        end: str,
        days: int,
        workspace_id: str | None = None,
        note: str | None = None,
        is_half_day: bool | None = None,
        half_day_period: str | None = None,
    ) -> Any:
        """Create a time-off request for the authenticated user under a policy."""
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
        policy_id: str,
        request_id: str,
        workspace_id: str | None = None,
        note: str | None = None,
    ) -> Any:
        """Approve a time-off request (sets status APPROVED)."""
        return await approve_time_off_request_fn(
            client,
            policy_id=policy_id,
            request_id=request_id,
            workspace_id=workspace_id,
            note=note,
        )

    @mcp.tool()
    async def reject_time_off_request(
        policy_id: str,
        request_id: str,
        workspace_id: str | None = None,
        note: str | None = None,
    ) -> Any:
        """Reject a time-off request (sets status REJECTED)."""
        return await reject_time_off_request_fn(
            client,
            policy_id=policy_id,
            request_id=request_id,
            workspace_id=workspace_id,
            note=note,
        )

    @mcp.tool()
    async def withdraw_time_off_request(
        policy_id: str, request_id: str, workspace_id: str | None = None
    ) -> Any:
        """Withdraw/cancel a time-off request. IRREVERSIBLE — the request is deleted."""
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
