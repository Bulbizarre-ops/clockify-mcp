import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import time_off


@respx.mock
async def test_list_time_off_policies_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(200, json=[{"id": "p1"}]))
    client = ClockifyClient(config)
    result = await time_off.list_time_off_policies(
        client,
        name="Vacation",
        status="ACTIVE",
        sort_column="NAME",
        sort_order="ASCENDING",
        page=1,
        page_size=15,
    )
    assert result == [{"id": "p1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "Vacation"
    assert sent["status"] == "ACTIVE"
    assert sent["sort-column"] == "NAME"
    assert sent["sort-order"] == "ASCENDING"
    assert sent["page-size"] == "15"
    await client.aclose()


@respx.mock
async def test_get_time_off_policy(config):
    respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1"
    ).mock(return_value=httpx.Response(200, json={"id": "p1", "name": "Vacation"}))
    client = ClockifyClient(config)
    assert await time_off.get_time_off_policy(client, policy_id="p1") == {
        "id": "p1",
        "name": "Vacation",
    }
    await client.aclose()


@respx.mock
async def test_list_balances_by_policy_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/balance/policy/p1"
    ).mock(return_value=httpx.Response(200, json={"balances": []}))
    client = ClockifyClient(config)
    result = await time_off.list_time_off_balances_by_policy(
        client, policy_id="p1", sort="BALANCE", sort_order="DESCENDING", page=2, page_size=10
    )
    assert result == {"balances": []}
    sent = dict(route.calls.last.request.url.params)
    assert sent["sort"] == "BALANCE"
    assert sent["sort-order"] == "DESCENDING"
    assert sent["page"] == "2"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_list_balances_by_user_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/balance/user/u1"
    ).mock(return_value=httpx.Response(200, json={"balances": []}))
    client = ClockifyClient(config)
    await time_off.list_time_off_balances_by_user(
        client, user_id="u1", sort="USER", sort_order="ASCENDING"
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["sort"] == "USER"
    assert sent["sort-order"] == "ASCENDING"
    await client.aclose()


@respx.mock
async def test_list_time_off_requests_builds_body(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/requests"
    ).mock(return_value=httpx.Response(200, json={"requests": []}))
    client = ClockifyClient(config)
    result = await time_off.list_time_off_requests(
        client,
        start="2022-08-01T00:00:00Z",
        end="2022-08-31T23:59:59Z",
        statuses=["PENDING"],
        users=["u1"],
        user_groups=["g1"],
        page=1,
        page_size=50,
    )
    assert result == {"requests": []}
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "start": "2022-08-01T00:00:00Z",
        "end": "2022-08-31T23:59:59Z",
        "statuses": ["PENDING"],
        "users": ["u1"],
        "userGroups": ["g1"],
        "page": 1,
        "pageSize": 50,
    }
    await client.aclose()


@respx.mock
async def test_list_time_off_requests_omits_unset(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/requests"
    ).mock(return_value=httpx.Response(200, json={"requests": []}))
    client = ClockifyClient(config)
    await time_off.list_time_off_requests(client)
    assert json.loads(route.calls.last.request.content) == {}
    await client.aclose()


@respx.mock
async def test_create_time_off_policy_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(201, json={"id": "p1"}))
    client = ClockifyClient(config_writes)
    result = await time_off.create_time_off_policy(
        client,
        name="Mental health days",
        requires_approval=True,
        team_managers=True,
        approver_user_ids=["u1"],
        color="#8BC34A",
        icon="STETHOSCOPE",
        time_unit="DAYS",
        everyone_including_new=True,
    )
    assert result == {"id": "p1"}
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "Mental health days"
    assert body["color"] == "#8BC34A"
    assert body["icon"] == "STETHOSCOPE"
    assert body["timeUnit"] == "DAYS"
    assert body["everyoneIncludingNew"] is True
    assert body["approve"] == {
        "requiresApproval": True,
        "teamManagers": True,
        "specificMembers": False,
        "userIds": ["u1"],
    }
    await client.aclose()


@respx.mock
async def test_create_time_off_policy_minimal(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(201, json={"id": "p1"}))
    client = ClockifyClient(config_writes)
    await time_off.create_time_off_policy(client, name="PTO")
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "name": "PTO",
        "timeUnit": "DAYS",
        "approve": {
            "requiresApproval": False,
            "teamManagers": False,
            "specificMembers": False,
            "userIds": [],
        },
    }
    await client.aclose()


@respx.mock
async def test_create_time_off_request_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests"
    ).mock(return_value=httpx.Response(201, json={"id": "r1"}))
    client = ClockifyClient(config_writes)
    result = await time_off.create_time_off_request(
        client,
        policy_id="p1",
        start="2021-12-23",
        end="2021-12-25",
        days=3,
        note="Family vacation",
    )
    assert result == {"id": "r1"}
    body = json.loads(route.calls.last.request.content)
    assert body["note"] == "Family vacation"
    assert body["timeOffPeriod"] == {
        "period": {"start": "2021-12-23", "end": "2021-12-25", "days": 3}
    }
    await client.aclose()


@respx.mock
async def test_create_time_off_request_half_day(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests"
    ).mock(return_value=httpx.Response(201, json={"id": "r1"}))
    client = ClockifyClient(config_writes)
    await time_off.create_time_off_request(
        client, policy_id="p1", start="2021-12-23", end="2021-12-23", days=1,
        is_half_day=True, half_day_period="FIRST_HALF",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["timeOffPeriod"]["isHalfDay"] is True
    assert body["timeOffPeriod"]["halfDayPeriod"] == "FIRST_HALF"
    await client.aclose()


@respx.mock
async def test_approve_time_off_request(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests/r1"
    ).mock(return_value=httpx.Response(200, json={"id": "r1", "status": "APPROVED"}))
    client = ClockifyClient(config_writes)
    result = await time_off.approve_time_off_request(client, policy_id="p1", request_id="r1")
    assert result["status"] == "APPROVED"
    assert json.loads(route.calls.last.request.content) == {"status": "APPROVED"}
    await client.aclose()


@respx.mock
async def test_reject_time_off_request_with_note(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests/r1"
    ).mock(return_value=httpx.Response(200, json={"id": "r1", "status": "REJECTED"}))
    client = ClockifyClient(config_writes)
    await time_off.reject_time_off_request(
        client, policy_id="p1", request_id="r1", note="Insufficient balance"
    )
    assert json.loads(route.calls.last.request.content) == {
        "status": "REJECTED",
        "note": "Insufficient balance",
    }
    await client.aclose()


@respx.mock
async def test_withdraw_time_off_request(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests/r1"
    ).mock(return_value=httpx.Response(200, json={"id": "r1"}))
    client = ClockifyClient(config_writes)
    assert await time_off.withdraw_time_off_request(
        client, policy_id="p1", request_id="r1"
    ) == {"id": "r1"}
    assert route.called
    await client.aclose()


@respx.mock
async def test_create_policy_with_specific_users(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(201, json={"id": "p1"}))
    client = ClockifyClient(config_writes)
    await time_off.create_time_off_policy(
        client, name="PTO", users=["u1"], user_groups=["g1"]
    )
    body = json.loads(route.calls.last.request.content)
    assert body["users"] == {"ids": ["u1"], "contains": "CONTAINS", "status": "ALL"}
    assert body["userGroups"] == {"ids": ["g1"], "contains": "CONTAINS", "status": "ALL"}
    await client.aclose()
