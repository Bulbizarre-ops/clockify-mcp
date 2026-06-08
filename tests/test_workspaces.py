import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import workspaces


@respx.mock
async def test_get_current_user(config):
    respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "u1", "name": "Alan"})
    )
    client = ClockifyClient(config)
    assert await workspaces.get_current_user(client) == {"id": "u1", "name": "Alan"}
    await client.aclose()


@respx.mock
async def test_list_workspaces(config):
    respx.get("https://api.clockify.me/api/v1/workspaces").mock(
        return_value=httpx.Response(200, json=[{"id": "ws1"}, {"id": "ws2"}])
    )
    client = ClockifyClient(config)
    assert await workspaces.list_workspaces(client) == [{"id": "ws1"}, {"id": "ws2"}]
    await client.aclose()


@respx.mock
async def test_get_workspace_uses_default(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1").mock(
        return_value=httpx.Response(200, json={"id": "ws1", "name": "Main"})
    )
    client = ClockifyClient(config)
    assert await workspaces.get_workspace(client) == {"id": "ws1", "name": "Main"}
    await client.aclose()
