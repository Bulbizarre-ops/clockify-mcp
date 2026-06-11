"""Projects domain (read + write)."""

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
_ProjectId = Annotated[
    str,
    Field(description="Id of the project (opaque string returned by list_projects)."),
]
_NameFilter = Annotated[
    str | None,
    Field(description="Filter projects by name (substring unless strict_name_search=True)."),
]
_StrictNameSearch = Annotated[
    bool | None,
    Field(description="When true, 'name' must match exactly rather than as a substring."),
]
_ArchivedFilter = Annotated[
    bool | None,
    Field(description="When true, include archived projects (excluded by default)."),
]
_BillableFilter = Annotated[
    bool | None,
    Field(description="Filter by billable flag: true for billable projects, false otherwise."),
]
_ClientsFilter = Annotated[
    list[str] | None,
    Field(description="Restrict to projects belonging to these client ids."),
]
_UsersFilter = Annotated[
    list[str] | None,
    Field(description="Restrict to projects that have these user ids assigned."),
]
_IsTemplateFilter = Annotated[
    bool | None,
    Field(description="Filter by template flag: true for template projects only."),
]
_Hydrated = Annotated[
    bool | None,
    Field(description="When true, expand nested tasks and memberships in the response."),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort by: NAME, CLIENT_NAME, or DURATION."),
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
    Field(description="Number of projects per page."),
]
_FetchAll = Annotated[
    bool,
    Field(description="Follow pagination and return all pages concatenated; ignores 'page'."),
]
_NewName = Annotated[
    str,
    Field(description="Display name for the new project."),
]
_UpdateName = Annotated[
    str | None,
    Field(description="New display name; omit to leave it unchanged."),
]
_ClientId = Annotated[
    str | None,
    Field(description="Id of the client to link the project to (from list_clients)."),
]
_Color = Annotated[
    str | None,
    Field(description="Project color as a hex string (e.g. '#FF5733')."),
]
_Note = Annotated[
    str | None,
    Field(description="Free-text note describing the project."),
]
_BillableSet = Annotated[
    bool | None,
    Field(description="Whether time logged on the project is billable by default."),
]
_IsPublic = Annotated[
    bool | None,
    Field(description="When true, the project is public to all workspace members."),
]
_ArchivedSet = Annotated[
    bool | None,
    Field(description="True archives (hides) the project, false restores it; omit to keep."),
]


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
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        strict_name_search: _StrictNameSearch = None,
        archived: _ArchivedFilter = None,
        billable: _BillableFilter = None,
        clients: _ClientsFilter = None,
        users: _UsersFilter = None,
        is_template: _IsTemplateFilter = None,
        hydrated: _Hydrated = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
        fetch_all: _FetchAll = False,
    ) -> Any:
        """List projects defined on a workspace, optionally filtered.

        Read-only; results are paginated. Filter by name, archived/billable/
        is_template flags, client ids (clients=[...]), or assigned user ids
        (users=[...]); hydrated=True expands nested tasks and memberships.
        sort_column is NAME, CLIENT_NAME, or DURATION. Use this to discover
        project ids before logging time or scoping tasks; when you already know
        a project's id, use get_project instead. fetch_all=True follows
        pagination and returns every page concatenated (ignores page). Returns a
        list of project objects.
        """
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
        project_id: _ProjectId,
        workspace_id: _WorkspaceId = None,
        hydrated: _Hydrated = None,
    ) -> Any:
        """Get a single project's full detail by its id.

        Read-only. Use list_projects first to look up the id when you only know
        the project name. hydrated=True expands nested tasks and memberships.
        Returns one project object.
        """
        return await get_project_fn(
            client, project_id=project_id, workspace_id=workspace_id, hydrated=hydrated
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_project(
        name: _NewName,
        workspace_id: _WorkspaceId = None,
        client_id: _ClientId = None,
        color: _Color = None,
        note: _Note = None,
        billable: _BillableSet = None,
        is_public: _IsPublic = None,
    ) -> Any:
        """Create a new project on a workspace.

        Write operation. Pass client_id to link the project to a client. Returns
        the created project including its newly assigned id, which you can then
        use to add tasks or log time entries.
        """
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
        project_id: _ProjectId,
        workspace_id: _WorkspaceId = None,
        name: _UpdateName = None,
        client_id: _ClientId = None,
        color: _Color = None,
        note: _Note = None,
        billable: _BillableSet = None,
        is_public: _IsPublic = None,
        archived: _ArchivedSet = None,
    ) -> Any:
        """Update a project's name, client, color, note, billable, or visibility.

        Write operation; only the fields you pass are changed. Pass
        archived=True/False to archive or restore it — archiving hides a project
        without deleting it, and is a prerequisite for delete_project. Returns the
        updated project.
        """
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
    async def delete_project(
        project_id: _ProjectId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Permanently delete a project from a workspace.

        Write operation and IRREVERSIBLE — the project and its tasks are removed.
        The project must be archived first (call update_project with
        archived=True); the API rejects deleting an active project. If you only
        want to hide it, use update_project(archived=True) instead.
        """
        return await delete_project_fn(
            client, project_id=project_id, workspace_id=workspace_id
        )


list_projects_fn = list_projects
get_project_fn = get_project
create_project_fn = create_project
update_project_fn = update_project
delete_project_fn = delete_project
