"""Tags domain (read + write)."""

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
_TagId = Annotated[
    str,
    Field(description="Id of the tag (opaque string returned by list_tags)."),
]
_NameFilter = Annotated[
    str | None,
    Field(description="Filter tags by name (substring unless strict_name_search=True)."),
]
_StrictNameSearch = Annotated[
    bool | None,
    Field(description="When true, 'name' must match exactly rather than as a substring."),
]
_ArchivedFilter = Annotated[
    bool | None,
    Field(description="When true, include archived tags (excluded by default)."),
]
_ExcludedIds = Annotated[
    str | None,
    Field(description="Comma-separated tag ids to omit from the results."),
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
    Field(description="Number of tags per page."),
]
_FetchAll = Annotated[
    bool,
    Field(description="Follow pagination and return all pages concatenated; ignores 'page'."),
]
_NewName = Annotated[
    str,
    Field(description="Display name for the new tag."),
]
_UpdateName = Annotated[
    str | None,
    Field(description="New display name; omit to leave it unchanged."),
]
_ArchivedSet = Annotated[
    bool | None,
    Field(description="True archives (hides) the tag, false restores it; omit to keep."),
]


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


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_tags(
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        strict_name_search: _StrictNameSearch = None,
        archived: _ArchivedFilter = None,
        excluded_ids: _ExcludedIds = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
        fetch_all: _FetchAll = False,
    ) -> Any:
        """List tags defined on a workspace, optionally filtered by name.

        Read-only; results are paginated. Use this to discover tag ids and names
        before assigning tags to time entries or filtering reports. When you
        already know a tag's id, use get_tag instead. Returns a list of tag
        objects (id, name, archived).
        """
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
    async def get_tag(tag_id: _TagId, workspace_id: _WorkspaceId = None) -> Any:
        """Get a single tag's full detail by its id.

        Read-only. Use list_tags first to look up the id when you only know the
        tag name. Returns one tag object (id, name, archived).
        """
        return await get_tag_fn(client, tag_id=tag_id, workspace_id=workspace_id)

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_tag(name: _NewName, workspace_id: _WorkspaceId = None) -> Any:
        """Create a new tag on a workspace.

        Write operation. Returns the created tag including its newly assigned id,
        which you can then attach to time entries.
        """
        return await create_tag_fn(client, name=name, workspace_id=workspace_id)

    @mcp.tool()
    async def update_tag(
        tag_id: _TagId,
        workspace_id: _WorkspaceId = None,
        name: _UpdateName = None,
        archived: _ArchivedSet = None,
    ) -> Any:
        """Update a tag's name and/or archived state.

        Write operation; only the fields you pass are changed. Archiving hides a
        tag without deleting it — prefer this over delete_tag when you may need
        the tag again. Returns the updated tag.
        """
        return await update_tag_fn(
            client, tag_id=tag_id, workspace_id=workspace_id, name=name, archived=archived
        )

    @mcp.tool()
    async def delete_tag(tag_id: _TagId, workspace_id: _WorkspaceId = None) -> Any:
        """Permanently delete a tag from a workspace.

        Write operation and IRREVERSIBLE — the tag is removed and unassigned from
        any time entries. If you only want to hide it, use
        update_tag(archived=True) instead.
        """
        return await delete_tag_fn(client, tag_id=tag_id, workspace_id=workspace_id)


list_tags_fn = list_tags
get_tag_fn = get_tag
create_tag_fn = create_tag
update_tag_fn = update_tag
delete_tag_fn = delete_tag
