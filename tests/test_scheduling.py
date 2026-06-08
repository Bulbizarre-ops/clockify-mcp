# tests/test_scheduling.py
import json
import httpx
import respx
from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import scheduling


@respx.mock
async def test_list_scheduled_assignments_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/all"
    ).mock(return_value=httpx.Response(200, json=[{"id": "a1"}]))
    client = ClockifyClient(config)
    await scheduling.list_scheduled_assignments(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z",
        name="x", sort_column="USER", sort_order="ASCENDING", page=1, page_size=20,
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["start"] == "2026-06-01T00:00:00Z"
    assert sent["end"] == "2026-06-30T00:00:00Z"
    assert sent["sort-column"] == "USER"
    assert sent["page-size"] == "20"
    await client.aclose()


@respx.mock
async def test_get_project_scheduling_totals_posts_body(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/projects/totals"
    ).mock(return_value=httpx.Response(200, json=[]))
    client = ClockifyClient(config)
    await scheduling.get_project_scheduling_totals(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z",
        search="web", status_filter="ALL", page=1, page_size=50,
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "start": "2026-06-01T00:00:00Z", "end": "2026-06-30T00:00:00Z",
        "search": "web", "statusFilter": "ALL", "page": 1, "pageSize": 50,
    }
    await client.aclose()


@respx.mock
async def test_get_user_scheduling_totals_posts_body(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/user-filter/totals"
    ).mock(return_value=httpx.Response(200, json=[]))
    client = ClockifyClient(config)
    await scheduling.get_user_scheduling_totals(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2026-06-01T00:00:00Z", "end": "2026-06-30T00:00:00Z"}
    await client.aclose()


@respx.mock
async def test_create_assignment_one_off(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await scheduling.create_assignment(
        client, user_id="u1", project_id="p1", start="2026-06-01T00:00:00Z",
        end="2026-06-05T00:00:00Z", hours_per_day=7.5, billable=True,
    )
    body = json.loads(route.calls.last.request.content)
    assert body["userId"] == "u1"
    assert body["projectId"] == "p1"
    assert body["hoursPerDay"] == 7.5
    assert body["billable"] is True
    assert "recurringAssignment" not in body
    await client.aclose()


@respx.mock
async def test_create_assignment_recurring(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await scheduling.create_assignment(
        client, user_id="u1", project_id="p1", start="2026-06-01T00:00:00Z",
        end="2026-06-05T00:00:00Z", hours_per_day=8, repeat=True, weeks=5,
    )
    body = json.loads(route.calls.last.request.content)
    assert body["recurringAssignment"] == {"repeat": True, "weeks": 5}
    await client.aclose()


@respx.mock
async def test_update_assignment(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring/a1"
    ).mock(return_value=httpx.Response(200, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await scheduling.update_assignment(
        client, assignment_id="a1", start="2026-06-01T00:00:00Z",
        end="2026-06-05T00:00:00Z", hours_per_day=6, series_update_option="ALL",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["hoursPerDay"] == 6
    assert body["seriesUpdateOption"] == "ALL"
    await client.aclose()


@respx.mock
async def test_delete_assignment_passes_series_option(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring/a1"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config_writes)
    await scheduling.delete_assignment(
        client, assignment_id="a1", series_update_option="THIS_ONE"
    )
    assert dict(route.calls.last.request.url.params)["seriesUpdateOption"] == "THIS_ONE"
    await client.aclose()


@respx.mock
async def test_publish_assignments(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/publish"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config_writes)
    await scheduling.publish_assignments(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z", notify_users=True,
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2026-06-01T00:00:00Z", "end": "2026-06-30T00:00:00Z", "notifyUsers": True}
    await client.aclose()


@respx.mock
async def test_copy_assignment(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/a1/copy"
    ).mock(return_value=httpx.Response(201, json={"id": "a2"}))
    client = ClockifyClient(config_writes)
    await scheduling.copy_assignment(client, assignment_id="a1", user_id="u2")
    assert json.loads(route.calls.last.request.content) == {"userId": "u2"}
    await client.aclose()
