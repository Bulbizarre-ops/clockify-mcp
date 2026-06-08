"""Clients domain (read + write)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


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
) -> Any:
    """List clients on the workspace, optionally filtered by name (paginated).

    Set archived=True to include archived clients. sort_column is one of NAME;
    sort_order is ASCENDING or DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "archived": archived,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/clients", params=params)


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


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_clients(
        workspace_id: str | None = None,
        name: str | None = None,
        archived: bool | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List clients on the workspace, optionally filtered by name (paginated)."""
        return await list_clients_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            archived=archived,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_client(client_id: str, workspace_id: str | None = None) -> Any:
        """Get a single client by id."""
        return await get_client_fn(client, client_id=client_id, workspace_id=workspace_id)

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_client(
        name: str,
        workspace_id: str | None = None,
        email: str | None = None,
        address: str | None = None,
        note: str | None = None,
    ) -> Any:
        """Create a client on the workspace."""
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
        client_id: str,
        name: str,
        workspace_id: str | None = None,
        email: str | None = None,
        address: str | None = None,
        note: str | None = None,
        archived: bool | None = None,
    ) -> Any:
        """Update a client. name is required by the Clockify API (pass the current
        name if unchanged). Pass archived=True/False to archive or restore it."""
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
    async def delete_client(client_id: str, workspace_id: str | None = None) -> Any:
        """Delete a client. IRREVERSIBLE. The client must be archived first
        (update_client archived=True); the API rejects deleting an active client."""
        return await delete_client_fn(client, client_id=client_id, workspace_id=workspace_id)


list_clients_fn = list_clients
get_client_fn = get_client
create_client_fn = create_client
update_client_fn = update_client
delete_client_fn = delete_client
