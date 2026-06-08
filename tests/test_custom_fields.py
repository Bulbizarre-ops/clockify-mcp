import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import custom_fields


@respx.mock
async def test_list_workspace_custom_fields_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/custom-fields").mock(
        return_value=httpx.Response(200, json=[{"id": "cf1"}])
    )
    client = ClockifyClient(config)
    result = await custom_fields.list_workspace_custom_fields(
        client, name="loc", status="VISIBLE", entity_type="TIMEENTRY"
    )
    assert result == [{"id": "cf1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "loc"
    assert sent["status"] == "VISIBLE"
    assert sent["entity-type"] == "TIMEENTRY"
    await client.aclose()


@respx.mock
async def test_list_project_custom_fields(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/custom-fields"
    ).mock(return_value=httpx.Response(200, json=[{"id": "cf1"}]))
    client = ClockifyClient(config)
    await custom_fields.list_project_custom_fields(client, project_id="p1", status="VISIBLE")
    assert dict(route.calls.last.request.url.params)["status"] == "VISIBLE"
    await client.aclose()


@respx.mock
async def test_create_workspace_custom_field_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/custom-fields").mock(
        return_value=httpx.Response(201, json={"id": "cf1"})
    )
    client = ClockifyClient(config_writes)
    await custom_fields.create_workspace_custom_field(
        client, name="location", type="DROPDOWN_MULTIPLE", entity_type="TIMEENTRY",
        allowed_values=["NY", "London"], status="VISIBLE",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "location"
    assert body["type"] == "DROPDOWN_MULTIPLE"
    assert body["entityType"] == "TIMEENTRY"
    assert body["allowedValues"] == ["NY", "London"]
    assert body["status"] == "VISIBLE"
    await client.aclose()


@respx.mock
async def test_update_workspace_custom_field_builds_body(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={"id": "cf1"}))
    client = ClockifyClient(config_writes)
    await custom_fields.update_workspace_custom_field(
        client, custom_field_id="cf1", name="loc", type="TXT", required=True
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "loc", "type": "TXT", "required": True}
    await client.aclose()


@respx.mock
async def test_delete_workspace_custom_field(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={"id": "cf1"}))
    client = ClockifyClient(config_writes)
    await custom_fields.delete_workspace_custom_field(client, custom_field_id="cf1")
    assert route.called
    await client.aclose()


@respx.mock
async def test_set_project_custom_field_patches(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={"id": "cf1"}))
    client = ClockifyClient(config_writes)
    await custom_fields.set_project_custom_field(
        client, project_id="p1", custom_field_id="cf1", default_value="NY", status="VISIBLE"
    )
    assert json.loads(route.calls.last.request.content) == {
        "defaultValue": "NY", "status": "VISIBLE"
    }
    await client.aclose()


@respx.mock
async def test_remove_project_custom_field(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config_writes)
    await custom_fields.remove_project_custom_field(
        client, project_id="p1", custom_field_id="cf1"
    )
    assert route.called
    await client.aclose()
