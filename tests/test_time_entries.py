import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import time_entries
from clockify_mcp.server import build_server


@respx.mock
async def test_list_time_entries_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(200, json=[{"id": "te1"}]))
    client = ClockifyClient(config)
    result = await time_entries.list_time_entries(
        client,
        user_id="u1",
        description="standup",
        start="2021-01-01T00:00:00Z",
        end="2021-01-31T23:59:59Z",
        project="p1",
        task="t1",
        tags=["g1", "g2"],
        project_required=True,
        task_required=False,
        hydrated=True,
        in_progress=False,
        get_week_before="2021-02-01T00:00:00Z",
        page=2,
        page_size=20,
    )
    assert result == [{"id": "te1"}]
    params = route.calls.last.request.url.params
    assert params["description"] == "standup"
    assert params["start"] == "2021-01-01T00:00:00Z"
    assert params["end"] == "2021-01-31T23:59:59Z"
    assert params["project"] == "p1"
    assert params["task"] == "t1"
    assert params["project-required"] == "true"
    assert params["task-required"] == "false"
    assert params["hydrated"] == "true"
    assert params["in-progress"] == "false"
    assert params["get-week-before"] == "2021-02-01T00:00:00Z"
    assert params["page"] == "2"
    assert params["page-size"] == "20"
    assert params.get_list("tags") == ["g1", "g2"]
    await client.aclose()


@respx.mock
async def test_get_time_entry_passes_hydrated(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-entries/te1"
    ).mock(return_value=httpx.Response(200, json={"id": "te1"}))
    client = ClockifyClient(config)
    assert await time_entries.get_time_entry(
        client, time_entry_id="te1", hydrated=True
    ) == {"id": "te1"}
    assert dict(route.calls.last.request.url.params)["hydrated"] == "true"
    await client.aclose()


@respx.mock
async def test_create_time_entry_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "te1"})
    )
    client = ClockifyClient(config_writes)
    await time_entries.create_time_entry(
        client,
        start="2021-01-01T09:00:00Z",
        end="2021-01-01T10:00:00Z",
        description="work",
        project_id="p1",
        tag_ids=["g1"],
        billable=True,
        type="REGULAR",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "start": "2021-01-01T09:00:00Z",
        "end": "2021-01-01T10:00:00Z",
        "description": "work",
        "projectId": "p1",
        "tagIds": ["g1"],
        "billable": True,
        "type": "REGULAR",
    }
    await client.aclose()


@respx.mock
async def test_update_time_entry_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/time-entries/te1").mock(
        return_value=httpx.Response(200, json={"id": "te1"})
    )
    client = ClockifyClient(config_writes)
    await time_entries.update_time_entry(
        client, time_entry_id="te1", start="2021-01-01T09:00:00Z", description="edited"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2021-01-01T09:00:00Z", "description": "edited"}
    await client.aclose()


@respx.mock
async def test_delete_time_entry(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-entries/te1"
    ).mock(return_value=httpx.Response(200, json={"id": "te1"}))
    client = ClockifyClient(config_writes)
    assert await time_entries.delete_time_entry(client, time_entry_id="te1") == {"id": "te1"}
    assert route.called
    await client.aclose()


@respx.mock
async def test_duplicate_time_entry(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries/te1/duplicate"
    ).mock(return_value=httpx.Response(201, json={"id": "te2"}))
    client = ClockifyClient(config_writes)
    result = await time_entries.duplicate_time_entry(
        client, user_id="u1", time_entry_id="te1"
    )
    assert result == {"id": "te2"}
    assert route.called
    await client.aclose()


@respx.mock
async def test_bulk_update_time_entries_sends_array(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(200, json=[{"id": "te1"}]))
    client = ClockifyClient(config_writes)
    entries = [{"id": "te1", "description": "a"}, {"id": "te2", "description": "b"}]
    result = await time_entries.bulk_update_time_entries(
        client, user_id="u1", entries=entries
    )
    assert result == [{"id": "te1"}]
    body = json.loads(route.calls.last.request.content)
    assert body == entries
    await client.aclose()


async def test_time_tracking_registers_time_entry_writes_only(config_time_tracking):
    client = ClockifyClient(config_time_tracking)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert {
        "create_time_entry", "update_time_entry", "delete_time_entry",
        "duplicate_time_entry", "bulk_update_time_entries",
    } <= names
    assert "create_client" not in names
    assert "create_project" not in names
    await client.aclose()


@respx.mock
async def test_time_tracking_duplicate_is_self_scoped(config_time_tracking):
    user = respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "me1"})
    )
    dup = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/me1/time-entries/te1/duplicate"
    ).mock(return_value=httpx.Response(201, json={"id": "te2"}))
    client = ClockifyClient(config_time_tracking)
    mcp = build_server(client)
    await mcp.call_tool("duplicate_time_entry", {"time_entry_id": "te1"})
    assert user.called and dup.called
    await client.aclose()


@respx.mock
async def test_time_tracking_bulk_is_self_scoped(config_time_tracking):
    user = respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "me1"})
    )
    bulk = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/me1/time-entries"
    ).mock(return_value=httpx.Response(200, json=[{"id": "te1"}]))
    client = ClockifyClient(config_time_tracking)
    mcp = build_server(client)
    await mcp.call_tool(
        "bulk_update_time_entries", {"entries": [{"id": "te1", "description": "a"}]}
    )
    assert user.called and bulk.called
    await client.aclose()


@respx.mock
async def test_create_time_entry_for_user(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(201, json={"id": "te1"}))
    client = ClockifyClient(config_writes)
    await time_entries.create_time_entry_for_user(
        client, user_id="u1", start="2021-01-01T09:00:00Z", description="work",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2021-01-01T09:00:00Z", "description": "work"}
    await client.aclose()


@respx.mock
async def test_stop_running_timer(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/u1/time-entries"
    ).mock(return_value=httpx.Response(200, json={"id": "te1"}))
    client = ClockifyClient(config_writes)
    await time_entries.stop_running_timer(
        client, user_id="u1", end="2021-01-01T10:00:00Z"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"end": "2021-01-01T10:00:00Z"}
    await client.aclose()
