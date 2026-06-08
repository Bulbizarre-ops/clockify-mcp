import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import shared_reports
from clockify_mcp.server import build_server

BASE = "https://reports.api.clockify.me/v1"


@respx.mock
async def test_list_shared_reports_query_params(config):
    route = respx.get(f"{BASE}/workspaces/ws1/shared-reports").mock(
        return_value=httpx.Response(200, json={"sharedReports": []})
    )
    client = ClockifyClient(config)
    result = await shared_reports.list_shared_reports(
        client, page=2, page_size=10, shared_reports_filter="CREATED_BY_ME"
    )
    assert result == {"sharedReports": []}
    params = route.calls.last.request.url.params
    assert params["page"] == "2"
    assert params["pageSize"] == "10"
    assert params["sharedReportsFilter"] == "CREATED_BY_ME"
    await client.aclose()


@respx.mock
async def test_get_shared_report_is_not_workspace_scoped(config):
    # generate-by-id endpoint omits the /workspaces/{ws} prefix
    route = respx.get(f"{BASE}/shared-reports/sr1").mock(
        return_value=httpx.Response(200, json={"id": "sr1"})
    )
    client = ClockifyClient(config)
    result = await shared_reports.get_shared_report(
        client, shared_report_id="sr1", export_type="JSON", page=1, page_size=5
    )
    assert result == {"id": "sr1"}
    params = route.calls.last.request.url.params
    assert params["exportType"] == "JSON"
    assert params["pageSize"] == "5"
    await client.aclose()


@respx.mock
async def test_create_shared_report_builds_body(config_writes):
    route = respx.post(f"{BASE}/workspaces/ws1/shared-reports").mock(
        return_value=httpx.Response(200, json={"id": "sr1"})
    )
    client = ClockifyClient(config_writes)
    result = await shared_reports.create_shared_report(
        client,
        name="Weekly",
        type="SUMMARY",
        date_range_start="2026-06-01T00:00:00Z",
        date_range_end="2026-06-30T23:59:59Z",
        is_public=False,
        visible_to_users=["u1"],
    )
    assert result == {"id": "sr1"}
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "Weekly"
    assert body["type"] == "SUMMARY"
    assert body["isPublic"] is False
    assert body["visibleToUsers"] == ["u1"]
    # SUMMARY type must carry its summaryFilter, or the API rejects the create with
    # 400 "Selecciona un filtro resumido" (caught live).
    assert body["filter"] == {
        "dateRangeStart": "2026-06-01T00:00:00Z",
        "dateRangeEnd": "2026-06-30T23:59:59Z",
        "summaryFilter": {"groups": ["PROJECT"]},
    }
    assert "fixedDate" not in body  # dropped when None
    await client.aclose()


@respx.mock
async def test_create_shared_report_filter_override(config_writes):
    route = respx.post(f"{BASE}/workspaces/ws1/shared-reports").mock(
        return_value=httpx.Response(200, json={"id": "sr1"})
    )
    client = ClockifyClient(config_writes)
    await shared_reports.create_shared_report(
        client,
        name="Custom",
        type="SUMMARY",
        date_range_start="2026-06-01T00:00:00Z",
        date_range_end="2026-06-30T23:59:59Z",
        report_filter={"summaryFilter": {"groups": ["USER", "DATE"]}},
    )
    body = json.loads(route.calls.last.request.content)
    # caller's report_filter overrides the default sub-filter
    assert body["filter"]["summaryFilter"] == {"groups": ["USER", "DATE"]}
    assert body["filter"]["dateRangeStart"] == "2026-06-01T00:00:00Z"
    await client.aclose()


@respx.mock
async def test_update_shared_report_only_metadata(config_writes):
    route = respx.put(f"{BASE}/workspaces/ws1/shared-reports/sr1").mock(
        return_value=httpx.Response(200, json={"id": "sr1"})
    )
    client = ClockifyClient(config_writes)
    await shared_reports.update_shared_report(
        client, shared_report_id="sr1", name="Renamed", is_public=True
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Renamed", "isPublic": True}  # no filter/type accepted
    await client.aclose()


@respx.mock
async def test_delete_shared_report(config_writes):
    route = respx.delete(f"{BASE}/workspaces/ws1/shared-reports/sr1").mock(
        return_value=httpx.Response(204)
    )
    client = ClockifyClient(config_writes)
    await shared_reports.delete_shared_report(client, shared_report_id="sr1")
    assert route.called
    await client.aclose()


async def test_writes_gated_off_by_default(config):
    client = ClockifyClient(config)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert {"list_shared_reports", "get_shared_report"} <= names
    assert "create_shared_report" not in names
    assert "delete_shared_report" not in names
    await client.aclose()


async def test_writes_registered_in_full_mode(config_writes):
    client = ClockifyClient(config_writes)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert {
        "list_shared_reports", "get_shared_report",
        "create_shared_report", "update_shared_report", "delete_shared_report",
    } <= names
    await client.aclose()
