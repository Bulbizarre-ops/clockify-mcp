"""User groups domain (read)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_user_groups(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List user groups on the workspace, optionally filtered by name (paginated)."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"name": name, **page_params(page, page_size)}
    return await client.get(f"workspaces/{ws}/user-groups", params=params)


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_user_groups(
        workspace_id: str | None = None,
        name: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List user groups on the workspace, optionally filtered by name (paginated)."""
        return await list_user_groups_fn(
            client, workspace_id=workspace_id, name=name, page=page, page_size=page_size
        )


list_user_groups_fn = list_user_groups
