"""Workspace & current-user discovery domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def resolve_workspace_id(client: ClockifyClient, workspace_id: str | None) -> str:
    """Return the explicit workspace_id, else the configured default, else error."""
    resolved = workspace_id or client.default_workspace_id
    if not resolved:
        raise ValueError(
            "No workspace_id given and no default configured. Call list_workspaces "
            "to find one, or set CLOCKIFY_DEFAULT_WORKSPACE_ID."
        )
    return resolved


async def get_current_user(client: ClockifyClient) -> Any:
    """Get the currently logged-in user's info (resolves your user id)."""
    return await client.get("user")


async def list_workspaces(client: ClockifyClient) -> Any:
    """List all workspaces the authenticated user belongs to."""
    return await client.get("workspaces")


async def get_workspace(client: ClockifyClient, workspace_id: str | None = None) -> Any:
    """Get info for one workspace (defaults to the configured workspace)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def get_current_user() -> Any:
        """Get the currently logged-in user's info (id, email, default workspace)."""
        return await get_current_user_fn(client)

    @mcp.tool()
    async def list_workspaces() -> Any:
        """List all workspaces the authenticated user belongs to."""
        return await list_workspaces_fn(client)

    @mcp.tool()
    async def get_workspace(workspace_id: str | None = None) -> Any:
        """Get info for one workspace (defaults to the configured workspace)."""
        return await get_workspace_fn(client, workspace_id)


get_current_user_fn = get_current_user
list_workspaces_fn = list_workspaces
get_workspace_fn = get_workspace
