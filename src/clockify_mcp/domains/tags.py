"""Tags domain (read + write)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import fetch_all_pages, page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_tags(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    strict_name_search: bool | None = None,
    archived: bool | None = None,
    excluded_ids: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
) -> Any:
    """List tags on the workspace, optionally filtered by name (paginated).

    Set strict_name_search=True for an exact name match; archived=True includes
    archived tags; excluded_ids omits specific tag ids. sort_column is one of NAME;
    sort_order is ASCENDING or DESCENDING. Set fetch_all=True to follow pagination and
    return every page concatenated (ignores page; may make several API calls).
    """
    ws = resolve_workspace_id(client, workspace_id)
    base = {
        "name": name,
        "strict-name-search": strict_name_search,
        "archived": archived,
        "excluded-ids": excluded_ids,
        "sort-column": sort_column,
        "sort-order": sort_order,
    }
    path = f"workspaces/{ws}/tags"
    if fetch_all:
        return await fetch_all_pages(
            lambda p, ps: client.get(path, params={**base, **page_params(p, ps)}),
            page_size=page_size,
        )
    return await client.get(path, params={**base, **page_params(page, page_size)})


async def get_tag(
    client: ClockifyClient, *, tag_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single tag by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/tags/{tag_id}")


async def create_tag(
    client: ClockifyClient, *, name: str, workspace_id: str | None = None
) -> Any:
    """Create a tag on the workspace."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"name": name})
    return await client.post(f"workspaces/{ws}/tags", json=body)


async def update_tag(
    client: ClockifyClient,
    *,
    tag_id: str,
    workspace_id: str | None = None,
    name: str | None = None,
    archived: bool | None = None,
) -> Any:
    """Update a tag. Pass archived=True/False to archive or restore it."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"name": name, "archived": archived})
    return await client.put(f"workspaces/{ws}/tags/{tag_id}", json=body)


async def delete_tag(
    client: ClockifyClient, *, tag_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a tag. IRREVERSIBLE — the tag is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/tags/{tag_id}")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_tags(
        workspace_id: str | None = None,
        name: str | None = None,
        strict_name_search: bool | None = None,
        archived: bool | None = None,
        excluded_ids: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        fetch_all: bool = False,
    ) -> Any:
        """List tags on the workspace, optionally filtered by name (paginated).
        fetch_all=True follows pagination and returns every page concatenated."""
        return await list_tags_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            strict_name_search=strict_name_search,
            archived=archived,
            excluded_ids=excluded_ids,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )

    @mcp.tool()
    async def get_tag(tag_id: str, workspace_id: str | None = None) -> Any:
        """Get a single tag by id."""
        return await get_tag_fn(client, tag_id=tag_id, workspace_id=workspace_id)

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_tag(name: str, workspace_id: str | None = None) -> Any:
        """Create a tag on the workspace."""
        return await create_tag_fn(client, name=name, workspace_id=workspace_id)

    @mcp.tool()
    async def update_tag(
        tag_id: str,
        workspace_id: str | None = None,
        name: str | None = None,
        archived: bool | None = None,
    ) -> Any:
        """Update a tag. Pass archived=True/False to archive or restore it."""
        return await update_tag_fn(
            client, tag_id=tag_id, workspace_id=workspace_id, name=name, archived=archived
        )

    @mcp.tool()
    async def delete_tag(tag_id: str, workspace_id: str | None = None) -> Any:
        """Delete a tag. IRREVERSIBLE — the tag is permanently removed."""
        return await delete_tag_fn(client, tag_id=tag_id, workspace_id=workspace_id)


list_tags_fn = list_tags
get_tag_fn = get_tag
create_tag_fn = create_tag
update_tag_fn = update_tag
delete_tag_fn = delete_tag
