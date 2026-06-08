import json

import httpx
import pytest
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import reports


def _sent_body(route):
    return json.loads(route.calls.last.request.content)


@respx.mock
async def test_detailed_report_builds_body(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/detailed"
    ).mock(return_value=httpx.Response(200, json={"timeentries": []}))
    client = ClockifyClient(config)
    result = await reports.generate_detailed_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
        page=1,
        page_size=50,
        sort_column="DATE",
    )
    assert result == {"timeentries": []}
    body = _sent_body(route)
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert body["dateRangeEnd"] == "2021-01-31T23:59:59Z"
    assert body["detailedFilter"] == {"page": 1, "pageSize": 50, "sortColumn": "DATE"}
    await client.aclose()


@respx.mock
async def test_summary_report_defaults_groups(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/summary"
    ).mock(return_value=httpx.Response(200, json={"groupOne": []}))
    client = ClockifyClient(config)
    result = await reports.generate_summary_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
    )
    assert result == {"groupOne": []}
    body = _sent_body(route)
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert body["summaryFilter"] == {"groups": ["PROJECT"]}
    await client.aclose()


@respx.mock
async def test_summary_report_custom_groups(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/summary"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config)
    await reports.generate_summary_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
        groups=["USER", "DATE"],
        sort_column="DURATION",
    )
    body = _sent_body(route)
    assert body["summaryFilter"] == {"groups": ["USER", "DATE"], "sortColumn": "DURATION"}
    await client.aclose()


@respx.mock
async def test_weekly_report_defaults(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/weekly"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config)
    await reports.generate_weekly_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-07T23:59:59Z",
    )
    body = _sent_body(route)
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert body["weeklyFilter"] == {"group": "USER", "subgroup": "TIME"}
    await client.aclose()


@respx.mock
async def test_export_report_detailed_pdf(config, tmp_path):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/detailed"
    ).mock(return_value=httpx.Response(200, content=b"%PDF-1.4 data"))
    client = ClockifyClient(config)
    dest = tmp_path / "report.pdf"
    result = await reports.export_report(
        client, report_type="detailed", fmt="PDF", save_path=str(dest),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-31T23:59:59Z",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["exportType"] == "PDF"
    assert body["detailedFilter"] == {}
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert dest.read_bytes() == b"%PDF-1.4 data"
    assert result == {"path": str(dest), "bytes": len(b"%PDF-1.4 data"), "format": "PDF"}
    await client.aclose()


@respx.mock
async def test_export_report_summary_and_weekly_filters(config, tmp_path):
    client = ClockifyClient(config)
    s = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/summary"
    ).mock(return_value=httpx.Response(200, content=b"x"))
    await reports.export_report(
        client, report_type="summary", fmt="CSV", save_path=str(tmp_path / "s.csv"),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-07T23:59:59Z",
    )
    assert json.loads(s.calls.last.request.content)["summaryFilter"] == {"groups": ["PROJECT"]}
    w = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/weekly"
    ).mock(return_value=httpx.Response(200, content=b"x"))
    await reports.export_report(
        client, report_type="weekly", fmt="XLSX", save_path=str(tmp_path / "w.xlsx"),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-07T23:59:59Z",
    )
    body = json.loads(w.calls.last.request.content)
    assert body["weeklyFilter"] == {"group": "USER", "subgroup": "TIME"}
    assert body["exportType"] == "XLSX"
    await client.aclose()


@respx.mock
async def test_attendance_report_builds_body(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/attendance"
    ).mock(return_value=httpx.Response(200, json={"rows": []}))
    client = ClockifyClient(config)
    result = await reports.generate_attendance_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
        page=2,
        page_size=10,
        sort_column="DATE",
        has_time_off=True,
    )
    assert result == {"rows": []}
    body = _sent_body(route)
    assert body["dateRangeStart"] == "2021-01-01T00:00:00Z"
    assert body["attendanceFilter"] == {
        "page": 2, "pageSize": 10, "sortColumn": "DATE", "hasTimeOff": True
    }
    await client.aclose()


@respx.mock
async def test_attendance_report_empty_filter(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/attendance"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config)
    await reports.generate_attendance_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
    )
    body = _sent_body(route)
    assert body["attendanceFilter"] == {}  # all optional fields dropped
    await client.aclose()


@respx.mock
async def test_expense_report_builds_body(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/expenses/detailed"
    ).mock(return_value=httpx.Response(200, json={"expenses": [], "totals": {}}))
    client = ClockifyClient(config)
    result = await reports.generate_expense_report(
        client,
        date_range_start="2021-01-01T00:00:00Z",
        date_range_end="2021-01-31T23:59:59Z",
        page=1,
        page_size=25,
        sort_column="AMOUNT",
        billable=True,
    )
    assert result == {"expenses": [], "totals": {}}
    body = _sent_body(route)
    assert body == {
        "dateRangeStart": "2021-01-01T00:00:00Z",
        "dateRangeEnd": "2021-01-31T23:59:59Z",
        "page": 1,
        "pageSize": 25,
        "sortColumn": "AMOUNT",
        "billable": True,
    }
    await client.aclose()


@respx.mock
async def test_export_report_attendance_and_expenses(config, tmp_path):
    client = ClockifyClient(config)
    a = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/attendance"
    ).mock(return_value=httpx.Response(200, content=b"att"))
    await reports.export_report(
        client, report_type="attendance", fmt="PDF", save_path=str(tmp_path / "a.pdf"),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-07T23:59:59Z",
    )
    abody = json.loads(a.calls.last.request.content)
    assert abody["attendanceFilter"] == {}
    assert abody["exportType"] == "PDF"

    e = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/expenses/detailed"
    ).mock(return_value=httpx.Response(200, content=b"exp"))
    result = await reports.export_report(
        client, report_type="expenses", fmt="CSV", save_path=str(tmp_path / "e.csv"),
        date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-07T23:59:59Z",
    )
    ebody = json.loads(e.calls.last.request.content)
    assert "attendanceFilter" not in ebody and "detailedFilter" not in ebody
    assert ebody["exportType"] == "CSV"
    assert (tmp_path / "e.csv").read_bytes() == b"exp"
    assert result["format"] == "CSV"
    await client.aclose()


async def test_export_report_rejects_bad_type(config, tmp_path):
    client = ClockifyClient(config)
    with pytest.raises(ValueError):
        await reports.export_report(
            client, report_type="bogus", fmt="PDF", save_path=str(tmp_path / "x"),
            date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-02T00:00:00Z",
        )
    await client.aclose()


async def test_export_report_rejects_bad_format(config, tmp_path):
    client = ClockifyClient(config)
    with pytest.raises(ValueError):
        await reports.export_report(
            client, report_type="detailed", fmt="DOCX", save_path=str(tmp_path / "x"),
            date_range_start="2021-01-01T00:00:00Z", date_range_end="2021-01-02T00:00:00Z",
        )
    await client.aclose()
