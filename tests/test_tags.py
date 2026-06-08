import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import tags


@respx.mock
async def test_list_tags_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1"}])
    )
    client = ClockifyClient(config)
    result = await tags.list_tags(
        client,
        name="billable",
        strict_name_search=True,
        archived=False,
        excluded_ids="g9",
        sort_column="NAME",
        sort_order="ASCENDING",
        page=1,
        page_size=15,
    )
    assert result == [{"id": "g1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "billable"
    assert sent["strict-name-search"] == "true"
    assert sent["archived"] == "false"
    assert sent["excluded-ids"] == "g9"
    assert sent["sort-column"] == "NAME"
    assert sent["sort-order"] == "ASCENDING"
    assert sent["page-size"] == "15"
    await client.aclose()


@respx.mock
async def test_get_tag(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/tags/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1", "name": "Billable"})
    )
    client = ClockifyClient(config)
    assert await tags.get_tag(client, tag_id="g1") == {"id": "g1", "name": "Billable"}
    await client.aclose()


@respx.mock
async def test_create_tag_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/tags").mock(
        return_value=httpx.Response(201, json={"id": "g1", "name": "Billable"})
    )
    client = ClockifyClient(config_writes)
    result = await tags.create_tag(client, name="Billable")
    assert result == {"id": "g1", "name": "Billable"}
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Billable"}
    await client.aclose()


@respx.mock
async def test_update_tag_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/tags/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1"})
    )
    client = ClockifyClient(config_writes)
    await tags.update_tag(client, tag_id="g1", name="New", archived=True)
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "New", "archived": True}
    await client.aclose()


@respx.mock
async def test_delete_tag(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/tags/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1"})
    )
    client = ClockifyClient(config_writes)
    assert await tags.delete_tag(client, tag_id="g1") == {"id": "g1"}
    assert route.called
    await client.aclose()
