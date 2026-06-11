# src/clockify_mcp/domains/approvals.py
"""Approvals domain: timesheet/expense approval requests (read + write).

Endpoints are on the regular Clockify host under
``workspaces/{workspaceId}/approval-requests``. Submitting and resubmitting
reference a period start + period type (WEEKLY/SEMI_MONTHLY/MONTHLY). Status is
changed via PATCH with the state enum
(PENDING/APPROVED/WITHDRAWN_SUBMISSION/WITHDRAWN_APPROVAL/REJECTED). Approvals
are a paid Clockify feature; the API errors on plans without it.
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
_StatusFilter = Annotated[
    str | None,
    Field(
        description="Filter by status: PENDING, APPROVED, or WITHDRAWN_APPROVAL. "
        "REJECTED requests are not returned by this filter (a Clockify limitation)."
    ),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort by: ID, USER_ID, START, or UPDATED_AT."),
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
    Field(description="Number of approval requests per page."),
]
_PeriodStart = Annotated[
    str,
    Field(description="ISO-8601 start of the approval period."),
]
_Period = Annotated[
    str,
    Field(description="Period type: WEEKLY, SEMI_MONTHLY, or MONTHLY."),
]
_UserId = Annotated[
    str,
    Field(description="Id of the user to submit the approval request for."),
]
_ApprovalRequestId = Annotated[
    str,
    Field(
        description="Id of the approval request (opaque string returned by "
        "list_approval_requests)."
    ),
]
_State = Annotated[
    str,
    Field(
        description="New state: APPROVED, REJECTED, PENDING, WITHDRAWN_SUBMISSION, "
        "or WITHDRAWN_APPROVAL."
    ),
]
_Note = Annotated[
    str | None,
    Field(description="Optional reason/note for the state change."),
]


async def list_approval_requests(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    status: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List approval requests (paginated).

    status filters by PENDING, APPROVED, or WITHDRAWN_APPROVAL (REJECTED requests
    are not returned by this filter — a Clockify limitation). sort_column is one
    of ID, USER_ID, START, UPDATED_AT; sort_order is ASCENDING or DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "status": status,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/approval-requests", params=params)


async def submit_approval_request(
    client: ClockifyClient,
    *,
    period_start: str,
    period: str,
    workspace_id: str | None = None,
) -> Any:
    """Submit an approval request for the authenticated user.

    period_start is the ISO-8601 start of the period; period is WEEKLY,
    SEMI_MONTHLY, or MONTHLY.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = {"periodStart": period_start, "period": period}
    return await client.post(f"workspaces/{ws}/approval-requests", json=body)


async def submit_approval_request_for_user(
    client: ClockifyClient,
    *,
    user_id: str,
    period_start: str,
    period: str,
    workspace_id: str | None = None,
) -> Any:
    """Submit an approval request on behalf of another user (manager action)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = {"periodStart": period_start, "period": period}
    return await client.post(
        f"workspaces/{ws}/approval-requests/users/{user_id}", json=body
    )


async def resubmit_approval_entries(
    client: ClockifyClient,
    *,
    period_start: str,
    period: str,
    workspace_id: str | None = None,
) -> Any:
    """Resubmit rejected/withdrawn entries for approval (authenticated user)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = {"periodStart": period_start, "period": period}
    return await client.post(
        f"workspaces/{ws}/approval-requests/resubmit-entries-for-approval", json=body
    )


async def update_approval_request(
    client: ClockifyClient,
    *,
    approval_request_id: str,
    state: str,
    workspace_id: str | None = None,
    note: str | None = None,
) -> Any:
    """Change an approval request's state.

    state is one of APPROVED, REJECTED, PENDING, WITHDRAWN_SUBMISSION,
    WITHDRAWN_APPROVAL. note is an optional reason.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"state": state, "note": note})
    return await client.patch(
        f"workspaces/{ws}/approval-requests/{approval_request_id}", json=body
    )


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_approval_requests(
        workspace_id: _WorkspaceId = None,
        status: _StatusFilter = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List timesheet/expense approval requests on a workspace.

        Read-only; results are paginated. Filter by status (PENDING, APPROVED, or
        WITHDRAWN_APPROVAL — REJECTED requests are not returned, a Clockify
        limitation) and sort by ID/USER_ID/START/UPDATED_AT. Use this to discover
        approval-request ids before changing their state with
        update_approval_request. Approvals are a paid Clockify feature; the API
        errors on plans without it. Returns a list of approval-request objects.
        """
        return await list_approval_requests_fn(
            client,
            workspace_id=workspace_id,
            status=status,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def submit_approval_request(
        period_start: _PeriodStart,
        period: _Period,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Submit an approval request for the authenticated user.

        Write operation; submits the caller's own timesheet/expenses for the
        period starting at period_start (period type WEEKLY/SEMI_MONTHLY/MONTHLY).
        To submit on behalf of someone else, use submit_approval_request_for_user.
        Returns the created approval request.
        """
        return await submit_approval_request_fn(
            client, period_start=period_start, period=period, workspace_id=workspace_id
        )

    @mcp.tool()
    async def submit_approval_request_for_user(
        user_id: _UserId,
        period_start: _PeriodStart,
        period: _Period,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Submit an approval request on behalf of another user (manager action).

        Write operation; like submit_approval_request but targets user_id rather
        than the authenticated caller, for the period starting at period_start
        (period type WEEKLY/SEMI_MONTHLY/MONTHLY). Returns the created approval
        request.
        """
        return await submit_approval_request_for_user_fn(
            client,
            user_id=user_id,
            period_start=period_start,
            period=period,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def resubmit_approval_entries(
        period_start: _PeriodStart,
        period: _Period,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Resubmit the authenticated user's rejected/withdrawn entries for approval.

        Write operation; unlike submit_approval_request (a first submission), this
        re-sends previously rejected or withdrawn entries for the period starting
        at period_start (period type WEEKLY/SEMI_MONTHLY/MONTHLY). Returns the
        resubmitted approval request.
        """
        return await resubmit_approval_entries_fn(
            client, period_start=period_start, period=period, workspace_id=workspace_id
        )

    @mcp.tool()
    async def update_approval_request(
        approval_request_id: _ApprovalRequestId,
        state: _State,
        workspace_id: _WorkspaceId = None,
        note: _Note = None,
    ) -> Any:
        """Change an existing approval request's state (manager/reviewer action).

        Write operation; sets state to one of APPROVED, REJECTED, PENDING,
        WITHDRAWN_SUBMISSION, or WITHDRAWN_APPROVAL, with an optional note. Look up
        approval_request_id via list_approval_requests first. Use this to act on a
        request that already exists, rather than the submit_* tools that create
        one. Returns the updated approval request.
        """
        return await update_approval_request_fn(
            client,
            approval_request_id=approval_request_id,
            state=state,
            workspace_id=workspace_id,
            note=note,
        )


list_approval_requests_fn = list_approval_requests
submit_approval_request_fn = submit_approval_request
submit_approval_request_for_user_fn = submit_approval_request_for_user
resubmit_approval_entries_fn = resubmit_approval_entries
update_approval_request_fn = update_approval_request
