"""Users domain: find/filter workspace users and resolve managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

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
    Field(description="Id of the user (opaque string returned by list_users)."),
]
_NameFilter = Annotated[
    str | None,
    Field(description="Filter users by name."),
]
_EmailFilter = Annotated[
    str | None,
    Field(description="Filter users by email address."),
]
_StatusFilter = Annotated[
    str | None,
    Field(description="Filter by membership status: ACTIVE, INACTIVE, PENDING, DECLINED, etc."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number; ignored when fetch_all=True."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of users per page."),
]
_FetchAll = Annotated[
    bool,
    Field(description="Follow pagination and return all pages concatenated; ignores 'page'."),
]


async def list_users(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    email: str | None = None,
    status: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
) -> Any:
    """List workspace users, optionally filtered by name/email/status (paginated).

    ``status`` is one of ACTIVE, INACTIVE, PENDING, DECLINED, etc. Use page /
    page_size for large workspaces. Set fetch_all=True to follow pagination and
    return every page concatenated (ignores page; may make several API calls).
    """
    ws = resolve_workspace_id(client, workspace_id)
    base = {"name": name, "email": email, "status": status}
    path = f"workspaces/{ws}/users"
    if fetch_all:
        return await fetch_all_pages(
            lambda p, ps: client.get(path, params={**base, **page_params(p, ps)}),
            page_size=page_size,
        )
    return await client.get(path, params={**base, **page_params(page, page_size)})


async def get_user_member_profile(
    client: ClockifyClient, *, user_id: str, workspace_id: str | None = None
) -> Any:
    """Get a member's profile within the workspace."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/member-profile/{user_id}")


async def find_user_team_manager(
    client: ClockifyClient, *, user_id: str, workspace_id: str | None = None
) -> Any:
    """Find a user's team manager(s)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/users/{user_id}/managers")


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_users(
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        email: _EmailFilter = None,
        status: _StatusFilter = None,
        page: _Page = None,
        page_size: _PageSize = None,
        fetch_all: _FetchAll = False,
    ) -> Any:
        """List the members of a workspace, optionally filtered by name, email, or status.

        Read-only; results are paginated. status is one of ACTIVE, INACTIVE,
        PENDING, DECLINED, etc. Use this to discover user ids and emails before
        calling get_user_member_profile or find_user_team_manager, or filtering
        reports and time entries by user. Set fetch_all=True to follow pagination
        and return every page concatenated (may make several API calls). Returns a
        list of user objects.
        """
        return await list_users_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            email=email,
            status=status,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )

    @mcp.tool()
    async def get_user_member_profile(user_id: _UserId, workspace_id: _WorkspaceId = None) -> Any:
        """Get one member's profile within a workspace by user id.

        Read-only. Unlike find_user_team_manager (which returns who manages the
        user), this returns the member's own workspace profile. Use list_users
        first to look up the id when you only know a name or email. Returns one
        member-profile object.
        """
        return await get_user_member_profile_fn(client, user_id=user_id, workspace_id=workspace_id)

    @mcp.tool()
    async def find_user_team_manager(user_id: _UserId, workspace_id: _WorkspaceId = None) -> Any:
        """Find the team manager(s) of a given user within a workspace.

        Read-only. Unlike get_user_member_profile (which returns the user's own
        profile), this returns the user's manager(s). Use list_users first to look
        up the id when you only know a name or email. Returns the manager(s) for
        the user.
        """
        return await find_user_team_manager_fn(client, user_id=user_id, workspace_id=workspace_id)


list_users_fn = list_users
get_user_member_profile_fn = get_user_member_profile
find_user_team_manager_fn = find_user_team_manager
