"""Shared reports domain (read + write).

Shared reports are saved, shareable report definitions. They live on the Reports API
host (not the regular host): list/create/update/delete are workspace-scoped under
``workspaces/{ws}/shared-reports``, but generate-by-id is the un-scoped
``shared-reports/{id}`` (still authenticated with the API key).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# A shared report's filter needs the sub-filter matching its type, or the API rejects
# the create (e.g. SUMMARY without summaryFilter -> 400 "Selecciona un filtro resumido").
# These defaults mirror the live-verified ones from the report generators; callers can
# override the whole filter via create_shared_report's report_filter argument.
_SHARED_REPORT_DEFAULT_FILTER: dict[str, dict[str, Any]] = {
    "DETAILED": {"detailedFilter": {}},
    "SUMMARY": {"summaryFilter": {"groups": ["PROJECT"]}},
    "WEEKLY": {"weeklyFilter": {"group": "USER", "subgroup": "TIME"}},
    "ATTENDANCE": {"attendanceFilter": {}},
}


# --- Parameter descriptions (surfaced to MCP clients via the tool input schema) ---
_WorkspaceId = Annotated[
    str | None,
    Field(description="Workspace id; omit to use the configured default_workspace_id."),
]
_SharedReportId = Annotated[
    str,
    Field(description="Id of the shared report (opaque string returned by list_shared_reports)."),
]
_SharedReportsFilter = Annotated[
    str | None,
    Field(description="Scope of reports to list: ALL (default), CREATED_BY_ME, or SHARED_WITH_ME."),
]
_DateRangeStartOpt = Annotated[
    str | None,
    Field(description="ISO-8601 start of the range; overrides the saved report's range when set."),
]
_DateRangeEndOpt = Annotated[
    str | None,
    Field(description="ISO-8601 end of the range; overrides the saved report's range when set."),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort the generated report by; overrides the saved sort."),
]
_SortOrder = Annotated[
    str | None,
    Field(description="Sort direction: ASCENDING or DESCENDING; overrides the saved sort."),
]
_ExportType = Annotated[
    str | None,
    Field(description="Output format: JSON (default), PDF, CSV, XLSX, or ZIP."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number for the paginated results."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of results per page."),
]
_ReportName = Annotated[
    str,
    Field(description="Display name for the shared report."),
]
_ReportType = Annotated[
    str,
    Field(
        description="Report kind: DETAILED, WEEKLY, SUMMARY, EXPENSE_DETAILED, ATTENDANCE, "
        "etc. (see the Clockify docs). Fixed at creation."
    ),
]
_DateRangeStart = Annotated[
    str,
    Field(description="ISO-8601 start of the report's date range (required by the filter)."),
]
_DateRangeEnd = Annotated[
    str,
    Field(description="ISO-8601 end of the report's date range (required by the filter)."),
]
_IsPublic = Annotated[
    bool | None,
    Field(description="When true, the report is accessible without sign-in; otherwise restricted."),
]
_FixedDate = Annotated[
    bool | None,
    Field(
        description="When true, pin the report to its saved date range rather than a relative one."
    ),
]
_VisibleToUsers = Annotated[
    list[str] | None,
    Field(description="User ids allowed to view the report when it is not public."),
]
_VisibleToUserGroups = Annotated[
    list[str] | None,
    Field(description="User-group ids allowed to view the report when it is not public."),
]
_ReportFilter = Annotated[
    dict[str, Any] | None,
    Field(
        description="Filter overrides merged into the report's filter; use for non-default "
        "types or to customize grouping (overrides the type's default sub-filter)."
    ),
]


async def list_shared_reports(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    shared_reports_filter: str | None = None,
) -> Any:
    """List the workspace's shared reports (paginated).

    shared_reports_filter is one of ALL (default), CREATED_BY_ME, SHARED_WITH_ME.
    Pagination uses camelCase page/pageSize query params (Reports API, not the
    hyphenated regular-API style).
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = drop_none(
        {"page": page, "pageSize": page_size, "sharedReportsFilter": shared_reports_filter}
    )
    return await client.report_get(f"workspaces/{ws}/shared-reports", params=params)


async def get_shared_report(
    client: ClockifyClient,
    *,
    shared_report_id: str,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    export_type: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """Generate (fetch the data of) a shared report by its id.

    This endpoint is NOT workspace-scoped. The optional query params override the saved
    report's range/sort/format; export_type is JSON (default), PDF, CSV, XLSX, or ZIP.
    The response shape depends on the report's type and export_type (passthrough JSON).
    """
    params = drop_none(
        {
            "dateRangeStart": date_range_start,
            "dateRangeEnd": date_range_end,
            "sortColumn": sort_column,
            "sortOrder": sort_order,
            "exportType": export_type,
            "page": page,
            "pageSize": page_size,
        }
    )
    return await client.report_get(f"shared-reports/{shared_report_id}", params=params)


async def create_shared_report(
    client: ClockifyClient,
    *,
    name: str,
    type: str,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    is_public: bool | None = None,
    fixed_date: bool | None = None,
    visible_to_users: list[str] | None = None,
    visible_to_user_groups: list[str] | None = None,
    report_filter: dict[str, Any] | None = None,
) -> Any:
    """Create (save) a shared report.

    type is one of DETAILED, WEEKLY, SUMMARY, EXPENSE_DETAILED, ATTENDANCE, and other
    report kinds (see the Clockify docs). The report's filter requires a date range
    (date_range_start/end, ISO-8601) AND the sub-filter for its type (e.g. SUMMARY needs
    a summaryFilter); a sensible default sub-filter is added for DETAILED/SUMMARY/WEEKLY/
    ATTENDANCE. For other types, or to customize grouping, pass report_filter (merged into
    the filter, overriding the defaults). is_public=True makes it accessible without
    sign-in; otherwise restrict it with visible_to_users / visible_to_user_groups.
    """
    ws = resolve_workspace_id(client, workspace_id)
    report_filter_body: dict[str, Any] = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        **_SHARED_REPORT_DEFAULT_FILTER.get(type, {}),
    }
    if report_filter:
        report_filter_body.update(report_filter)
    body = drop_none(
        {
            "name": name,
            "type": type,
            "isPublic": is_public,
            "fixedDate": fixed_date,
            "visibleToUsers": visible_to_users,
            "visibleToUserGroups": visible_to_user_groups,
            "filter": report_filter_body,
        }
    )
    return await client.report(f"workspaces/{ws}/shared-reports", body)


async def update_shared_report(
    client: ClockifyClient,
    *,
    shared_report_id: str,
    name: str,
    workspace_id: str | None = None,
    is_public: bool | None = None,
    fixed_date: bool | None = None,
    visible_to_users: list[str] | None = None,
    visible_to_user_groups: list[str] | None = None,
) -> Any:
    """Update a shared report's metadata and visibility. name is required by the API.

    Only name, is_public, fixed_date, and visibility can be changed — the report's
    type and filter are fixed at creation (delete and recreate to change them).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "isPublic": is_public,
            "fixedDate": fixed_date,
            "visibleToUsers": visible_to_users,
            "visibleToUserGroups": visible_to_user_groups,
        }
    )
    return await client.report_put(f"workspaces/{ws}/shared-reports/{shared_report_id}", json=body)


async def delete_shared_report(
    client: ClockifyClient, *, shared_report_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a shared report. IRREVERSIBLE — the saved report and its share link are
    permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.report_delete(f"workspaces/{ws}/shared-reports/{shared_report_id}")


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_shared_reports(
        workspace_id: _WorkspaceId = None,
        page: _Page = None,
        page_size: _PageSize = None,
        shared_reports_filter: _SharedReportsFilter = None,
    ) -> Any:
        """List the workspace's saved shared-report definitions to discover their ids.

        Read-only. Workspace-scoped (falls back to the configured default workspace) and
        served from the Reports API host. Results are paginated via page/page_size.
        Narrow the listing with shared_reports_filter: ALL (default), CREATED_BY_ME, or
        SHARED_WITH_ME. Returns the saved report metadata, not generated report data —
        use get_shared_report to generate (fetch the data of) a known id."""
        return await list_shared_reports_fn(
            client,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            shared_reports_filter=shared_reports_filter,
        )

    @mcp.tool()
    async def get_shared_report(
        shared_report_id: _SharedReportId,
        date_range_start: _DateRangeStartOpt = None,
        date_range_end: _DateRangeEndOpt = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        export_type: _ExportType = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """Generate (fetch the data of) a single saved shared report by its id.

        Read-only. Unlike list_shared_reports (which returns saved definitions), this runs
        the report and returns its data. This endpoint is NOT workspace-scoped — it takes
        only the report id (still authenticated with the API key) and is served from the
        Reports API host. Optional params override the saved range (date_range_start/end),
        sort (sort_column/sort_order), and format (export_type: JSON default, PDF, CSV,
        XLSX, ZIP); results are paginated via page/page_size. The returned shape depends on
        the report's type and export_type (passthrough JSON). Use list_shared_reports to
        discover ids first."""
        return await get_shared_report_fn(
            client,
            shared_report_id=shared_report_id,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            sort_column=sort_column,
            sort_order=sort_order,
            export_type=export_type,
            page=page,
            page_size=page_size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_shared_report(
        name: _ReportName,
        type: _ReportType,
        date_range_start: _DateRangeStart,
        date_range_end: _DateRangeEnd,
        workspace_id: _WorkspaceId = None,
        is_public: _IsPublic = None,
        fixed_date: _FixedDate = None,
        visible_to_users: _VisibleToUsers = None,
        visible_to_user_groups: _VisibleToUserGroups = None,
        report_filter: _ReportFilter = None,
    ) -> Any:
        """Create (save) a new shared-report definition.

        Write operation. Workspace-scoped (falls back to the configured default workspace)
        and served from the Reports API host. type is DETAILED/WEEKLY/SUMMARY/
        EXPENSE_DETAILED/ATTENDANCE/etc.; the filter needs a date range
        (date_range_start/end, ISO-8601) AND the sub-filter for its type (a sensible
        default is added for DETAILED/SUMMARY/WEEKLY/ATTENDANCE — pass report_filter to
        customize grouping or for other types). is_public=True shares it publicly;
        otherwise scope with visible_to_users / visible_to_user_groups. Returns the created
        report. To change an existing report use update_shared_report (note type and filter
        cannot be changed afterwards)."""
        return await create_shared_report_fn(
            client,
            name=name,
            type=type,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            is_public=is_public,
            fixed_date=fixed_date,
            visible_to_users=visible_to_users,
            visible_to_user_groups=visible_to_user_groups,
            report_filter=report_filter,
        )

    @mcp.tool()
    async def update_shared_report(
        shared_report_id: _SharedReportId,
        name: _ReportName,
        workspace_id: _WorkspaceId = None,
        is_public: _IsPublic = None,
        fixed_date: _FixedDate = None,
        visible_to_users: _VisibleToUsers = None,
        visible_to_user_groups: _VisibleToUserGroups = None,
    ) -> Any:
        """Update an existing shared report's metadata and visibility.

        Write operation. Workspace-scoped (falls back to the configured default workspace)
        and served from the Reports API host. Only name (required by the API), is_public,
        fixed_date, and visibility (visible_to_users / visible_to_user_groups) can be
        changed — the report's type and filter are fixed at creation, so delete and
        recreate with create_shared_report to change them. Returns the updated report."""
        return await update_shared_report_fn(
            client,
            shared_report_id=shared_report_id,
            name=name,
            workspace_id=workspace_id,
            is_public=is_public,
            fixed_date=fixed_date,
            visible_to_users=visible_to_users,
            visible_to_user_groups=visible_to_user_groups,
        )

    @mcp.tool()
    async def delete_shared_report(
        shared_report_id: _SharedReportId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Delete a saved shared report by its id.

        Write operation. IRREVERSIBLE — the saved report and its share link are permanently
        removed. Workspace-scoped (falls back to the configured default workspace) and
        served from the Reports API host. Use list_shared_reports to find the id first."""
        return await delete_shared_report_fn(
            client, shared_report_id=shared_report_id, workspace_id=workspace_id
        )


list_shared_reports_fn = list_shared_reports
get_shared_report_fn = get_shared_report
create_shared_report_fn = create_shared_report
update_shared_report_fn = update_shared_report
delete_shared_report_fn = delete_shared_report
