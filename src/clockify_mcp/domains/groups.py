"""User groups domain (read)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

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
_NameFilter = Annotated[
    str | None,
    Field(description="Filter user groups by name (substring match)."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of user groups per page."),
]


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


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_user_groups(
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List the user groups (teams) defined on a workspace, optionally filtered by name.

        Read-only; results are paginated. Use this to discover user-group ids and
        names — for example to assign groups to projects or to filter reports by
        team. Workspace-scoped: omit workspace_id to use the configured default.
        Returns a list of user-group objects (id, name, and member info).
        """
        return await list_user_groups_fn(
            client, workspace_id=workspace_id, name=name, page=page, page_size=page_size
        )


list_user_groups_fn = list_user_groups
