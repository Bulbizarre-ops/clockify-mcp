"""Reports domain (read). Reports POST a filter body to the Reports API host."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def generate_detailed_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    sort_column: str | None = None,
) -> Any:
    """Generate a detailed report (one row per time entry) for a date range.

    date_range_start/end are ISO-8601 datetimes with offset (e.g.
    2021-01-01T00:00:00Z). sort_column is one of ID, DESCRIPTION, USER, DURATION,
    DATE, ZONED_DATE, NATURAL, USER_DATE. Use page/page_size for large ranges.
    """
    ws = resolve_workspace_id(client, workspace_id)
    detailed_filter = drop_none(
        {"page": page, "pageSize": page_size, "sortColumn": sort_column}
    )
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "detailedFilter": detailed_filter,
    }
    return await client.report(f"workspaces/{ws}/reports/detailed", body)


async def generate_summary_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    groups: list[str] | None = None,
    sort_column: str | None = None,
) -> Any:
    """Generate a summary report (totals grouped by one or more keys) for a date range.

    groups are grouping keys applied in order, e.g. PROJECT, CLIENT, USER, TASK, TAG,
    DATE; defaults to ["PROJECT"]. sort_column is one of GROUP, DURATION, AMOUNT,
    EARNED, COST, PROFIT.
    """
    ws = resolve_workspace_id(client, workspace_id)
    summary_filter = drop_none(
        {"groups": groups if groups is not None else ["PROJECT"], "sortColumn": sort_column}
    )
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "summaryFilter": summary_filter,
    }
    return await client.report(f"workspaces/{ws}/reports/summary", body)


async def generate_weekly_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    group: str | None = None,
    subgroup: str | None = None,
) -> Any:
    """Generate a weekly report for a date range.

    group/subgroup control the breakdown; common values are group="USER" and
    subgroup="TIME" (the defaults when omitted).
    """
    ws = resolve_workspace_id(client, workspace_id)
    weekly_filter = {
        "group": group if group is not None else "USER",
        "subgroup": subgroup if subgroup is not None else "TIME",
    }
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "weeklyFilter": weekly_filter,
    }
    return await client.report(f"workspaces/{ws}/reports/weekly", body)


async def export_report(
    client: ClockifyClient,
    *,
    report_type: str,
    fmt: str,
    save_path: str,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
) -> Any:
    """Export a report as a binary file (PDF/CSV/XLSX) and write it to save_path.

    report_type is detailed, summary, or weekly. fmt is PDF, CSV, or XLSX. The bytes
    are written to save_path; returns {"path", "bytes", "format"} (the file content is
    kept out of the model context). Uses sensible default grouping per report type;
    for fine-grained JSON results use the generate_*_report tools.
    """
    if report_type == "detailed":
        report_filter = {"detailedFilter": {}}
    elif report_type == "summary":
        report_filter = {"summaryFilter": {"groups": ["PROJECT"]}}
    elif report_type == "weekly":
        report_filter = {"weeklyFilter": {"group": "USER", "subgroup": "TIME"}}
    else:
        raise ValueError(
            f"report_type must be 'detailed', 'summary', or 'weekly'; got {report_type!r}"
        )
    if fmt not in ("PDF", "CSV", "XLSX"):
        raise ValueError(f"fmt must be 'PDF', 'CSV', or 'XLSX'; got {fmt!r}")
    ws = resolve_workspace_id(client, workspace_id)
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        **report_filter,
        "exportType": fmt,
    }
    data = await client.report_bytes(f"workspaces/{ws}/reports/{report_type}", body)
    path = Path(save_path)
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data), "format": fmt}


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def generate_detailed_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        sort_column: str | None = None,
    ) -> Any:
        """Generate a detailed report (one row per time entry) for a date range."""
        return await generate_detailed_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
        )

    @mcp.tool()
    async def generate_summary_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        groups: list[str] | None = None,
        sort_column: str | None = None,
    ) -> Any:
        """Generate a summary report (totals grouped by one or more keys) for a date range."""
        return await generate_summary_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            groups=groups,
            sort_column=sort_column,
        )

    @mcp.tool()
    async def generate_weekly_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        group: str | None = None,
        subgroup: str | None = None,
    ) -> Any:
        """Generate a weekly report for a date range."""
        return await generate_weekly_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            group=group,
            subgroup=subgroup,
        )

    @mcp.tool()
    async def export_report(
        report_type: str,
        fmt: str,
        save_path: str,
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Export a report as a file (PDF/CSV/XLSX). report_type is detailed/summary/
        weekly; fmt is PDF/CSV/XLSX; bytes are written to save_path."""
        return await export_report_fn(
            client,
            report_type=report_type,
            fmt=fmt,
            save_path=save_path,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
        )


generate_detailed_report_fn = generate_detailed_report
generate_summary_report_fn = generate_summary_report
generate_weekly_report_fn = generate_weekly_report
export_report_fn = export_report
