import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import users


@respx.mock
async def test_list_users_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/users").mock(
        return_value=httpx.Response(200, json=[{"id": "u1"}])
    )
    client = ClockifyClient(config)
    result = await users.list_users(client, name="alan", page=2, page_size=10)
    assert result == [{"id": "u1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "alan"
    assert sent["page"] == "2"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_get_user_member_profile(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/member-profile/u1").mock(
        return_value=httpx.Response(200, json={"userId": "u1"})
    )
    client = ClockifyClient(config)
    assert await users.get_user_member_profile(client, user_id="u1") == {"userId": "u1"}
    await client.aclose()


@respx.mock
async def test_find_user_team_manager(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/users/u1/managers").mock(
        return_value=httpx.Response(200, json=[{"id": "m1"}])
    )
    client = ClockifyClient(config)
    assert await users.find_user_team_manager(client, user_id="u1") == [{"id": "m1"}]
    await client.aclose()
