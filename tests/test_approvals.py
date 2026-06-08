# tests/test_approvals.py
import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import approvals


@respx.mock
async def test_list_approval_requests_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests"
    ).mock(return_value=httpx.Response(200, json=[{"id": "a1"}]))
    client = ClockifyClient(config)
    result = await approvals.list_approval_requests(
        client, status="PENDING", sort_column="START", sort_order="DESCENDING",
        page=1, page_size=25,
    )
    assert result == [{"id": "a1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["status"] == "PENDING"
    assert sent["sort-column"] == "START"
    assert sent["sort-order"] == "DESCENDING"
    assert sent["page-size"] == "25"
    await client.aclose()


@respx.mock
async def test_submit_approval_request_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.submit_approval_request(
        client, period_start="2026-06-01T00:00:00Z", period="WEEKLY"
    )
    assert json.loads(route.calls.last.request.content) == {
        "periodStart": "2026-06-01T00:00:00Z",
        "period": "WEEKLY",
    }
    await client.aclose()


@respx.mock
async def test_submit_approval_request_for_user(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests/users/u1"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.submit_approval_request_for_user(
        client, user_id="u1", period_start="2026-06-01T00:00:00Z", period="MONTHLY"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"periodStart": "2026-06-01T00:00:00Z", "period": "MONTHLY"}
    await client.aclose()


@respx.mock
async def test_resubmit_approval_entries(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests/resubmit-entries-for-approval"
    ).mock(return_value=httpx.Response(200, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.resubmit_approval_entries(
        client, period_start="2026-06-01T00:00:00Z", period="WEEKLY"
    )
    assert json.loads(route.calls.last.request.content) == {
        "periodStart": "2026-06-01T00:00:00Z",
        "period": "WEEKLY",
    }
    await client.aclose()


@respx.mock
async def test_update_approval_request_builds_body(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests/a1"
    ).mock(return_value=httpx.Response(200, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.update_approval_request(
        client, approval_request_id="a1", state="APPROVED", note="ok"
    )
    assert json.loads(route.calls.last.request.content) == {"state": "APPROVED", "note": "ok"}
    await client.aclose()
