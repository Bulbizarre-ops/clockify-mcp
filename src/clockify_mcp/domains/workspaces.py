"""Workspace & current-user discovery domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..client import ClockifyClient

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# --- Parameter descriptions (surfaced to MCP clients via the tool input schema) ---
_WorkspaceId = Annotated[
    str | None,
    Field(description="Workspace id; omit to use the configured default_workspace_id."),
]


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


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def get_current_user() -> Any:
        """Get the authenticated user's own profile (resolves who the API key belongs to).

        Read-only and takes no workspace; it identifies the caller. Use this to
        discover your own user id, email, and default workspace id before calling
        workspace-scoped tools — unlike list_users, which lists members of a
        workspace. Returns one user object (id, email, name, defaultWorkspace,
        activeWorkspace, settings).
        """
        return await get_current_user_fn(client)

    @mcp.tool()
    async def list_workspaces() -> Any:
        """List every workspace the authenticated user belongs to.

        Read-only and not workspace-scoped (it spans all of the caller's
        workspaces). Use this to discover workspace ids when no default is
        configured; pass one to get_workspace for full detail on a single
        workspace. Returns a list of workspace objects (id, name, settings).
        """
        return await list_workspaces_fn(client)

    @mcp.tool()
    async def get_workspace(workspace_id: _WorkspaceId = None) -> Any:
        """Get full detail for one workspace by id.

        Read-only. Defaults to the configured default_workspace_id when
        workspace_id is omitted. Use list_workspaces first to discover available
        ids. Returns one workspace object (id, name, settings, memberships).
        """
        return await get_workspace_fn(client, workspace_id)


get_current_user_fn = get_current_user
list_workspaces_fn = list_workspaces
get_workspace_fn = get_workspace
