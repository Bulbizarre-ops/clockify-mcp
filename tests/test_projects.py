import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import projects


@respx.mock
async def test_list_projects_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1"}])
    )
    client = ClockifyClient(config)
    result = await projects.list_projects(
        client,
        name="site",
        strict_name_search=True,
        archived=False,
        billable=True,
        clients=["c1", "c2"],
        users=["u1", "u2"],
        is_template=False,
        hydrated=True,
        sort_column="NAME",
        sort_order="ASCENDING",
        page=1,
        page_size=50,
    )
    assert result == [{"id": "p1"}]
    params = route.calls.last.request.url.params
    assert params["name"] == "site"
    assert params["strict-name-search"] == "true"
    assert params["archived"] == "false"
    assert params["billable"] == "true"
    assert params["is-template"] == "false"
    assert params["hydrated"] == "true"
    assert params["sort-column"] == "NAME"
    assert params["sort-order"] == "ASCENDING"
    assert params["page-size"] == "50"
    assert params.get_list("clients") == ["c1", "c2"]
    assert params.get_list("users") == ["u1", "u2"]
    await client.aclose()


@respx.mock
async def test_get_project_passes_hydrated(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/projects/p1").mock(
        return_value=httpx.Response(200, json={"id": "p1"})
    )
    client = ClockifyClient(config)
    assert await projects.get_project(client, project_id="p1", hydrated=True) == {"id": "p1"}
    assert dict(route.calls.last.request.url.params)["hydrated"] == "true"
    await client.aclose()


@respx.mock
async def test_create_project_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/projects").mock(
        return_value=httpx.Response(201, json={"id": "p1"})
    )
    client = ClockifyClient(config_writes)
    await projects.create_project(
        client, name="Site", client_id="c1", billable=True, is_public=False
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Site", "clientId": "c1", "billable": True, "isPublic": False}
    await client.aclose()


@respx.mock
async def test_update_project_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/projects/p1").mock(
        return_value=httpx.Response(200, json={"id": "p1"})
    )
    client = ClockifyClient(config_writes)
    await projects.update_project(client, project_id="p1", name="New", archived=True)
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "New", "archived": True}
    await client.aclose()


@respx.mock
async def test_delete_project(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/projects/p1").mock(
        return_value=httpx.Response(200, json={"id": "p1"})
    )
    client = ClockifyClient(config_writes)
    assert await projects.delete_project(client, project_id="p1") == {"id": "p1"}
    assert route.called
    await client.aclose()
