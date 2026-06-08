"""Users domain: find/filter workspace users and resolve managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_users(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    email: str | None = None,
    status: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List workspace users, optionally filtered by name/email/status (paginated).

    ``status`` is one of ACTIVE, INACTIVE, PENDING, DECLINED, etc. Use page /
    page_size for large workspaces.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {"name": name, "email": email, "status": status, **page_params(page, page_size)}
    return await client.get(f"workspaces/{ws}/users", params=params)


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


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_users(
        workspace_id: str | None = None,
        name: str | None = None,
        email: str | None = None,
        status: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List workspace users, optionally filtered by name/email/status (paginated)."""
        return await list_users_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            email=email,
            status=status,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_user_member_profile(user_id: str, workspace_id: str | None = None) -> Any:
        """Get a member's profile within the workspace."""
        return await get_user_member_profile_fn(client, user_id=user_id, workspace_id=workspace_id)

    @mcp.tool()
    async def find_user_team_manager(user_id: str, workspace_id: str | None = None) -> Any:
        """Find a user's team manager(s)."""
        return await find_user_team_manager_fn(client, user_id=user_id, workspace_id=workspace_id)


list_users_fn = list_users
get_user_member_profile_fn = get_user_member_profile
find_user_team_manager_fn = find_user_team_manager
