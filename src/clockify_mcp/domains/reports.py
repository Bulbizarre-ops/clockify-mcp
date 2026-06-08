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


async def generate_attendance_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    sort_column: str | None = None,
    has_time_off: bool | None = None,
) -> Any:
    """Generate an attendance report (per user/day: clock-in/out, work, break, capacity,
    overtime, time off) for a date range. Requires the workspace's attendance/time-tracking
    add-on. sort_column is one of USER, DATE, START, END, BREAK, WORK, CAPACITY, OVERTIME,
    TIME_OFF. Use page/page_size for large ranges. date_range_* are ISO-8601 datetimes.
    """
    ws = resolve_workspace_id(client, workspace_id)
    attendance_filter = drop_none(
        {
            "page": page,
            "pageSize": page_size,
            "sortColumn": sort_column,
            "hasTimeOff": has_time_off,
        }
    )
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "attendanceFilter": attendance_filter,
    }
    return await client.report(f"workspaces/{ws}/reports/attendance", body)


async def generate_expense_report(
    client: ClockifyClient,
    *,
    date_range_start: str,
    date_range_end: str,
    workspace_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    sort_column: str | None = None,
    billable: bool | None = None,
) -> Any:
    """Generate a detailed expense report ({"expenses": [...], "totals": {...}}) for a date
    range. Requires the workspace's Expenses add-on. sort_column is one of ID, PROJECT, USER,
    CATEGORY, DATE, AMOUNT. Pagination is page/page_size. date_range_* are ISO-8601 datetimes.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "dateRangeStart": date_range_start,
            "dateRangeEnd": date_range_end,
            "page": page,
            "pageSize": page_size,
            "sortColumn": sort_column,
            "billable": billable,
        }
    )
    return await client.report(f"workspaces/{ws}/reports/expenses/detailed", body)


# report_type -> (path suffix, default filter object) for export_report.
_EXPORT_REPORTS: dict[str, tuple[str, dict[str, Any]]] = {
    "detailed": ("reports/detailed", {"detailedFilter": {}}),
    "summary": ("reports/summary", {"summaryFilter": {"groups": ["PROJECT"]}}),
    "weekly": ("reports/weekly", {"weeklyFilter": {"group": "USER", "subgroup": "TIME"}}),
    "attendance": ("reports/attendance", {"attendanceFilter": {}}),
    "expenses": ("reports/expenses/detailed", {}),
}


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

    report_type is detailed, summary, weekly, attendance, or expenses. fmt is PDF, CSV,
    or XLSX. The bytes are written to save_path; returns {"path", "bytes", "format"} (the
    file content is kept out of the model context). Uses sensible default grouping per
    report type; for fine-grained JSON results use the generate_*_report tools.
    """
    entry = _EXPORT_REPORTS.get(report_type)
    if entry is None:
        raise ValueError(
            "report_type must be one of "
            f"{sorted(_EXPORT_REPORTS)}; got {report_type!r}"
        )
    path_suffix, report_filter = entry
    if fmt not in ("PDF", "CSV", "XLSX"):
        raise ValueError(f"fmt must be 'PDF', 'CSV', or 'XLSX'; got {fmt!r}")
    ws = resolve_workspace_id(client, workspace_id)
    body = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        **report_filter,
        "exportType": fmt,
    }
    data = await client.report_bytes(f"workspaces/{ws}/{path_suffix}", body)
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
    async def generate_attendance_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        sort_column: str | None = None,
        has_time_off: bool | None = None,
    ) -> Any:
        """Generate an attendance report (per user/day: work, break, capacity, overtime,
        time off) for a date range. Requires the attendance/time-tracking add-on."""
        return await generate_attendance_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            has_time_off=has_time_off,
        )

    @mcp.tool()
    async def generate_expense_report(
        date_range_start: str,
        date_range_end: str,
        workspace_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        sort_column: str | None = None,
        billable: bool | None = None,
    ) -> Any:
        """Generate a detailed expense report ({"expenses": [...], "totals": {...}}) for a
        date range. Requires the Expenses add-on."""
        return await generate_expense_report_fn(
            client,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            billable=billable,
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
        weekly/attendance/expenses; fmt is PDF/CSV/XLSX; bytes are written to save_path."""
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
generate_attendance_report_fn = generate_attendance_report
generate_expense_report_fn = generate_expense_report
export_report_fn = export_report
