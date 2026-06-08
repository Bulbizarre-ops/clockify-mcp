import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import clients


@respx.mock
async def test_list_clients_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/clients").mock(
        return_value=httpx.Response(200, json=[{"id": "c1"}])
    )
    client = ClockifyClient(config)
    result = await clients.list_clients(
        client,
        name="acme",
        archived=False,
        sort_column="NAME",
        sort_order="ASCENDING",
        page=2,
        page_size=10,
    )
    assert result == [{"id": "c1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "acme"
    assert sent["archived"] == "false"
    assert sent["sort-column"] == "NAME"
    assert sent["sort-order"] == "ASCENDING"
    assert sent["page"] == "2"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_list_clients_fetch_all_follows_pagination(config):
    # Two full pages then a short page -> fetch_all concatenates all and stops.
    pages = [
        [{"id": "c1"}, {"id": "c2"}],
        [{"id": "c3"}, {"id": "c4"}],
        [{"id": "c5"}],
    ]

    def responder(request):
        page = int(request.url.params["page"])
        return httpx.Response(200, json=pages[page - 1])

    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/clients").mock(
        side_effect=responder
    )
    client = ClockifyClient(config)
    result = await clients.list_clients(client, name="acme", fetch_all=True, page_size=2)
    assert [c["id"] for c in result] == ["c1", "c2", "c3", "c4", "c5"]
    assert route.call_count == 3
    # filters are preserved on every paged request
    assert route.calls.last.request.url.params["name"] == "acme"
    assert route.calls.last.request.url.params["page-size"] == "2"
    await client.aclose()


@respx.mock
async def test_get_client(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(200, json={"id": "c1", "name": "Acme"})
    )
    client = ClockifyClient(config)
    assert await clients.get_client(client, client_id="c1") == {"id": "c1", "name": "Acme"}
    await client.aclose()


@respx.mock
async def test_create_client_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/clients").mock(
        return_value=httpx.Response(201, json={"id": "c1", "name": "Acme"})
    )
    client = ClockifyClient(config_writes)
    result = await clients.create_client(client, name="Acme", email="a@b.com")
    assert result == {"id": "c1", "name": "Acme"}
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Acme", "email": "a@b.com"}
    await client.aclose()


@respx.mock
async def test_update_client_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(200, json={"id": "c1"})
    )
    client = ClockifyClient(config_writes)
    await clients.update_client(client, client_id="c1", name="New", archived=True)
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "New", "archived": True}
    await client.aclose()


@respx.mock
async def test_delete_client(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(200, json={"id": "c1"})
    )
    client = ClockifyClient(config_writes)
    assert await clients.delete_client(client, client_id="c1") == {"id": "c1"}
    assert route.called
    await client.aclose()
