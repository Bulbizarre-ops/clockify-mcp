"""Clients domain (read + write)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none
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
_ClientId = Annotated[
    str,
    Field(description="Id of the client (opaque string returned by list_clients)."),
]
_NameFilter = Annotated[
    str | None,
    Field(description="Filter clients by name (substring match)."),
]
_ArchivedFilter = Annotated[
    bool | None,
    Field(description="When true, include archived clients (excluded by default)."),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort by; only NAME is supported."),
]
_SortOrder = Annotated[
    str | None,
    Field(description="Sort direction: ASCENDING or DESCENDING."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number; ignored when fetch_all=True."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of clients per page."),
]
_FetchAll = Annotated[
    bool,
    Field(description="Follow pagination and return all pages concatenated; ignores 'page'."),
]
_NewName = Annotated[
    str,
    Field(description="Display name for the new client."),
]
_UpdateName = Annotated[
    str,
    Field(description="Client name; required by the API (PUT replaces the client) — "
    "pass the current name if unchanged."),
]
_Email = Annotated[
    str | None,
    Field(description="Client contact email address."),
]
_Address = Annotated[
    str | None,
    Field(description="Client postal/billing address."),
]
_Note = Annotated[
    str | None,
    Field(description="Free-form note about the client."),
]
_ArchivedSet = Annotated[
    bool | None,
    Field(description="True archives (hides) the client, false restores it; omit to keep."),
]


async def list_clients(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    archived: bool | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
) -> Any:
    """List clients on the workspace, optionally filtered by name (paginated).

    Set archived=True to include archived clients. sort_column is one of NAME;
    sort_order is ASCENDING or DESCENDING. Set fetch_all=True to follow pagination and
    return every page concatenated (ignores page; may make several API calls).
    """
    ws = resolve_workspace_id(client, workspace_id)
    base = {
        "name": name,
        "archived": archived,
        "sort-column": sort_column,
        "sort-order": sort_order,
    }
    path = f"workspaces/{ws}/clients"
    if fetch_all:
        return await fetch_all_pages(
            lambda p, ps: client.get(path, params={**base, **page_params(p, ps)}),
            page_size=page_size,
        )
    return await client.get(path, params={**base, **page_params(page, page_size)})


async def get_client(
    client: ClockifyClient, *, client_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single client by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/clients/{client_id}")


async def create_client(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    email: str | None = None,
    address: str | None = None,
    note: str | None = None,
) -> Any:
    """Create a client on the workspace."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"name": name, "email": email, "address": address, "note": note})
    return await client.post(f"workspaces/{ws}/clients", json=body)


async def update_client(
    client: ClockifyClient,
    *,
    client_id: str,
    name: str,
    workspace_id: str | None = None,
    email: str | None = None,
    address: str | None = None,
    note: str | None = None,
    archived: bool | None = None,
) -> Any:
    """Update a client. name is required by the Clockify API (its PUT replaces the
    client) — pass the current name if you are not changing it. Pass archived=True/
    False to archive or restore it."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "email": email,
            "address": address,
            "note": note,
            "archived": archived,
        }
    )
    return await client.put(f"workspaces/{ws}/clients/{client_id}", json=body)


async def delete_client(
    client: ClockifyClient, *, client_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a client. IRREVERSIBLE — the client is permanently removed. The client
    must be archived first (call update_client with archived=True); the API rejects
    deleting an active client."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/clients/{client_id}")


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_clients(
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        archived: _ArchivedFilter = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
        fetch_all: _FetchAll = False,
    ) -> Any:
        """List clients defined on a workspace, optionally filtered by name.

        Read-only; results are paginated. Use this to discover client ids and
        names before assigning a client to a project or filtering reports. When
        you already know a client's id, use get_client instead. Set archived=True
        to include archived clients; fetch_all=True follows pagination and returns
        every page concatenated. Returns a list of client objects.
        """
        return await list_clients_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            archived=archived,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )

    @mcp.tool()
    async def get_client(client_id: _ClientId, workspace_id: _WorkspaceId = None) -> Any:
        """Get a single client's full detail by its id.

        Read-only. Use list_clients first to look up the id when you only know the
        client name. Returns one client object (id, name, email, address, note,
        archived).
        """
        return await get_client_fn(client, client_id=client_id, workspace_id=workspace_id)

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_client(
        name: _NewName,
        workspace_id: _WorkspaceId = None,
        email: _Email = None,
        address: _Address = None,
        note: _Note = None,
    ) -> Any:
        """Create a new client on a workspace.

        Write operation. Optionally set email, address, and note. Returns the
        created client including its newly assigned id, which you can then attach
        to projects.
        """
        return await create_client_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            email=email,
            address=address,
            note=note,
        )

    @mcp.tool()
    async def update_client(
        client_id: _ClientId,
        name: _UpdateName,
        workspace_id: _WorkspaceId = None,
        email: _Email = None,
        address: _Address = None,
        note: _Note = None,
        archived: _ArchivedSet = None,
    ) -> Any:
        """Update a client, or archive/restore it.

        Write operation. This is a full replace: name is required by the Clockify
        API, so pass the current name if you are not changing it. Pass
        archived=True to hide the client (prefer this over delete_client when you
        may need it again) or archived=False to restore it. Returns the updated
        client.
        """
        return await update_client_fn(
            client,
            client_id=client_id,
            name=name,
            workspace_id=workspace_id,
            email=email,
            address=address,
            note=note,
            archived=archived,
        )

    @mcp.tool()
    async def delete_client(client_id: _ClientId, workspace_id: _WorkspaceId = None) -> Any:
        """Permanently delete a client from a workspace.

        Write operation and IRREVERSIBLE — the client is removed. It must be
        archived first (call update_client with archived=True); the API rejects
        deleting an active client. If you only want to hide it, use
        update_client(archived=True) instead.
        """
        return await delete_client_fn(client, client_id=client_id, workspace_id=workspace_id)


list_clients_fn = list_clients
get_client_fn = get_client
create_client_fn = create_client
update_client_fn = update_client
delete_client_fn = delete_client
