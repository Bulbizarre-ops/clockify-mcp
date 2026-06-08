import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import groups


@respx.mock
async def test_list_user_groups(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/user-groups").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Dev"}])
    )
    client = ClockifyClient(config)
    result = await groups.list_user_groups(client, name="Dev", page_size=5)
    assert result == [{"id": "g1", "name": "Dev"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "Dev"
    assert sent["page-size"] == "5"
    await client.aclose()
