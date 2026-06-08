"""Projects domain (read + write)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import fetch_all_pages, page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_projects(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    strict_name_search: bool | None = None,
    archived: bool | None = None,
    billable: bool | None = None,
    clients: list[str] | None = None,
    users: list[str] | None = None,
    is_template: bool | None = None,
    hydrated: bool | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
) -> Any:
    """List projects on the workspace with optional filters (paginated).

    Filter by name (substring; set strict_name_search=True for exact), archived,
    billable, is_template, by client ids (clients=[...]) or assigned user ids
    (users=[...]). hydrated=True expands nested tasks/memberships. sort_column is
    one of NAME, CLIENT_NAME, DURATION; sort_order is ASCENDING or DESCENDING.
    Set fetch_all=True to follow pagination and return every page concatenated
    (ignores page; may make several API calls).
    """
    ws = resolve_workspace_id(client, workspace_id)
    base = {
        "name": name,
        "strict-name-search": strict_name_search,
        "archived": archived,
        "billable": billable,
        "clients": clients,
        "users": users,
        "is-template": is_template,
        "hydrated": hydrated,
        "sort-column": sort_column,
        "sort-order": sort_order,
    }
    path = f"workspaces/{ws}/projects"
    if fetch_all:
        return await fetch_all_pages(
            lambda p, ps: client.get(path, params={**base, **page_params(p, ps)}),
            page_size=page_size,
        )
    return await client.get(path, params={**base, **page_params(page, page_size)})


async def get_project(
    client: ClockifyClient,
    *,
    project_id: str,
    workspace_id: str | None = None,
    hydrated: bool | None = None,
) -> Any:
    """Get a single project by id. hydrated=True expands nested tasks/memberships."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"hydrated": hydrated}
    return await client.get(f"workspaces/{ws}/projects/{project_id}", params=params)


async def create_project(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    client_id: str | None = None,
    color: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    is_public: bool | None = None,
) -> Any:
    """Create a project on the workspace. client_id links it to a client."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "clientId": client_id,
            "color": color,
            "note": note,
            "billable": billable,
            "isPublic": is_public,
        }
    )
    return await client.post(f"workspaces/{ws}/projects", json=body)


async def update_project(
    client: ClockifyClient,
    *,
    project_id: str,
    workspace_id: str | None = None,
    name: str | None = None,
    client_id: str | None = None,
    color: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    is_public: bool | None = None,
    archived: bool | None = None,
) -> Any:
    """Update a project. Pass archived=True/False to archive or restore it."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "clientId": client_id,
            "color": color,
            "note": note,
            "billable": billable,
            "isPublic": is_public,
            "archived": archived,
        }
    )
    return await client.put(f"workspaces/{ws}/projects/{project_id}", json=body)


async def delete_project(
    client: ClockifyClient, *, project_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a project. IRREVERSIBLE — the project and its tasks are removed. The
    project must be archived first (call update_project with archived=True); the API
    rejects deleting an active project."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/projects/{project_id}")


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_projects(
        workspace_id: str | None = None,
        name: str | None = None,
        strict_name_search: bool | None = None,
        archived: bool | None = None,
        billable: bool | None = None,
        clients: list[str] | None = None,
        users: list[str] | None = None,
        is_template: bool | None = None,
        hydrated: bool | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        fetch_all: bool = False,
    ) -> Any:
        """List projects on the workspace with optional filters (paginated).
        fetch_all=True follows pagination and returns every page concatenated."""
        return await list_projects_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            strict_name_search=strict_name_search,
            archived=archived,
            billable=billable,
            clients=clients,
            users=users,
            is_template=is_template,
            hydrated=hydrated,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )

    @mcp.tool()
    async def get_project(
        project_id: str,
        workspace_id: str | None = None,
        hydrated: bool | None = None,
    ) -> Any:
        """Get a single project by id."""
        return await get_project_fn(
            client, project_id=project_id, workspace_id=workspace_id, hydrated=hydrated
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_project(
        name: str,
        workspace_id: str | None = None,
        client_id: str | None = None,
        color: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        is_public: bool | None = None,
    ) -> Any:
        """Create a project on the workspace. client_id links it to a client."""
        return await create_project_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            client_id=client_id,
            color=color,
            note=note,
            billable=billable,
            is_public=is_public,
        )

    @mcp.tool()
    async def update_project(
        project_id: str,
        workspace_id: str | None = None,
        name: str | None = None,
        client_id: str | None = None,
        color: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        is_public: bool | None = None,
        archived: bool | None = None,
    ) -> Any:
        """Update a project. Pass archived=True/False to archive or restore it."""
        return await update_project_fn(
            client,
            project_id=project_id,
            workspace_id=workspace_id,
            name=name,
            client_id=client_id,
            color=color,
            note=note,
            billable=billable,
            is_public=is_public,
            archived=archived,
        )

    @mcp.tool()
    async def delete_project(project_id: str, workspace_id: str | None = None) -> Any:
        """Delete a project. IRREVERSIBLE. The project must be archived first
        (update_project archived=True); the API rejects deleting an active project."""
        return await delete_project_fn(
            client, project_id=project_id, workspace_id=workspace_id
        )


list_projects_fn = list_projects
get_project_fn = get_project
create_project_fn = create_project
update_project_fn = update_project
delete_project_fn = delete_project
