# tests/test_holidays.py
import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import holidays


@respx.mock
async def test_list_holidays_passes_assigned_to(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays"
    ).mock(return_value=httpx.Response(200, json=[{"id": "h1"}]))
    client = ClockifyClient(config)
    result = await holidays.list_holidays(client, assigned_to="u1")
    assert result == [{"id": "h1"}]
    assert dict(route.calls.last.request.url.params)["assigned-to"] == "u1"
    await client.aclose()


@respx.mock
async def test_list_holidays_in_period_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays/in-period"
    ).mock(return_value=httpx.Response(200, json=[{"id": "h1"}]))
    client = ClockifyClient(config)
    await holidays.list_holidays_in_period(
        client, assigned_to="u1", start="2023-01-01", end="2023-12-31"
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["assigned-to"] == "u1"
    assert sent["start"] == "2023-01-01"
    assert sent["end"] == "2023-12-31"
    await client.aclose()


@respx.mock
async def test_create_holiday_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays"
    ).mock(return_value=httpx.Response(201, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    result = await holidays.create_holiday(
        client,
        name="Labour Day",
        start_date="2023-05-01",
        end_date="2023-05-01",
        color="#8BC34A",
        occurs_annually=True,
        everyone_including_new=True,
    )
    assert result == {"id": "h1"}
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "Labour Day"
    assert body["color"] == "#8BC34A"
    assert body["occursAnnually"] is True
    assert body["everyoneIncludingNew"] is True
    assert body["datePeriod"] == {"startDate": "2023-05-01", "endDate": "2023-05-01"}
    await client.aclose()


@respx.mock
async def test_create_holiday_minimal(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays"
    ).mock(return_value=httpx.Response(201, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    await holidays.create_holiday(
        client, name="One Off", start_date="2023-06-06", end_date="2023-06-06"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "name": "One Off",
        "datePeriod": {"startDate": "2023-06-06", "endDate": "2023-06-06"},
    }
    await client.aclose()


@respx.mock
async def test_update_holiday_builds_body(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays/h1"
    ).mock(return_value=httpx.Response(200, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    await holidays.update_holiday(
        client,
        holiday_id="h1",
        name="Labour Day",
        start_date="2023-05-01",
        end_date="2023-05-02",
        occurs_annually=False,
    )
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "Labour Day"
    assert body["occursAnnually"] is False
    assert body["datePeriod"] == {"startDate": "2023-05-01", "endDate": "2023-05-02"}
    await client.aclose()


@respx.mock
async def test_delete_holiday(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays/h1"
    ).mock(return_value=httpx.Response(200, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    assert await holidays.delete_holiday(client, holiday_id="h1") == {"id": "h1"}
    assert route.called
    await client.aclose()


@respx.mock
async def test_create_holiday_with_specific_users(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/holidays").mock(
        return_value=httpx.Response(201, json={"id": "h1"})
    )
    client = ClockifyClient(config_writes)
    await holidays.create_holiday(
        client, name="Xmas", start_date="2026-12-25", end_date="2026-12-25",
        users=["u1"],
    )
    body = json.loads(route.calls.last.request.content)
    assert body["users"] == {"ids": ["u1"], "contains": "CONTAINS", "status": "ALL"}
    await client.aclose()


@respx.mock
async def test_update_holiday_with_user_groups(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/holidays/h1").mock(
        return_value=httpx.Response(200, json={"id": "h1"})
    )
    client = ClockifyClient(config_writes)
    await holidays.update_holiday(
        client, holiday_id="h1", name="Xmas", start_date="2026-12-25",
        end_date="2026-12-25", occurs_annually=True, user_groups=["g1"],
    )
    body = json.loads(route.calls.last.request.content)
    assert body["userGroups"] == {"ids": ["g1"], "contains": "CONTAINS", "status": "ALL"}
    await client.aclose()
