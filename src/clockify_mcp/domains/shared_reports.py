"""Shared reports domain (read + write).

Shared reports are saved, shareable report definitions. They live on the Reports API
host (not the regular host): list/create/update/delete are workspace-scoped under
``workspaces/{ws}/shared-reports``, but generate-by-id is the un-scoped
``shared-reports/{id}`` (still authenticated with the API key).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
        workspace_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        shared_reports_filter: str | None = None,
    ) -> Any:
        """List the workspace's shared reports. shared_reports_filter is ALL (default),
        CREATED_BY_ME, or SHARED_WITH_ME."""
        return await list_shared_reports_fn(
            client,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            shared_reports_filter=shared_reports_filter,
        )

    @mcp.tool()
    async def get_shared_report(
        shared_report_id: str,
        date_range_start: str | None = None,
        date_range_end: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        export_type: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """Generate (fetch the data of) a shared report by id. Optional params override
        the saved range/sort/format; export_type is JSON/PDF/CSV/XLSX/ZIP."""
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
        """Create a shared report. type is DETAILED/WEEKLY/SUMMARY/EXPENSE_DETAILED/
        ATTENDANCE/etc.; the filter needs a date range and the type's sub-filter (a
        default is added for DETAILED/SUMMARY/WEEKLY/ATTENDANCE; pass report_filter to
        customize or for other types). is_public=True shares it publicly; otherwise
        scope with visible_to_users / visible_to_user_groups."""
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
        shared_report_id: str,
        name: str,
        workspace_id: str | None = None,
        is_public: bool | None = None,
        fixed_date: bool | None = None,
        visible_to_users: list[str] | None = None,
        visible_to_user_groups: list[str] | None = None,
    ) -> Any:
        """Update a shared report's metadata/visibility (name required). type and filter
        are fixed at creation — delete and recreate to change them."""
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
        shared_report_id: str, workspace_id: str | None = None
    ) -> Any:
        """Delete a shared report. IRREVERSIBLE — the saved report and share link are
        permanently removed."""
        return await delete_shared_report_fn(
            client, shared_report_id=shared_report_id, workspace_id=workspace_id
        )


list_shared_reports_fn = list_shared_reports
get_shared_report_fn = get_shared_report
create_shared_report_fn = create_shared_report
update_shared_report_fn = update_shared_report
delete_shared_report_fn = delete_shared_report
