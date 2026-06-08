import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import tasks


@respx.mock
async def test_list_tasks_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks"
    ).mock(return_value=httpx.Response(200, json=[{"id": "t1"}]))
    client = ClockifyClient(config)
    result = await tasks.list_tasks(
        client,
        project_id="p1",
        name="design",
        strict_name_search=True,
        is_active=True,
        sort_column="NAME",
        sort_order="ASCENDING",
        page=1,
        page_size=20,
    )
    assert result == [{"id": "t1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "design"
    assert sent["strict-name-search"] == "true"
    assert sent["is-active"] == "true"
    assert sent["sort-column"] == "NAME"
    assert sent["sort-order"] == "ASCENDING"
    assert sent["page-size"] == "20"
    await client.aclose()


@respx.mock
async def test_get_task(config):
    respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks/t1"
    ).mock(return_value=httpx.Response(200, json={"id": "t1", "name": "Design"}))
    client = ClockifyClient(config)
    result = await tasks.get_task(client, project_id="p1", task_id="t1")
    assert result == {"id": "t1", "name": "Design"}
    await client.aclose()


@respx.mock
async def test_create_task_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks"
    ).mock(return_value=httpx.Response(201, json={"id": "t1"}))
    client = ClockifyClient(config_writes)
    await tasks.create_task(
        client, project_id="p1", name="Design", assignee_ids=["u1"], status="ACTIVE"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Design", "assigneeIds": ["u1"], "status": "ACTIVE"}
    await client.aclose()


@respx.mock
async def test_update_task_builds_body(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks/t1"
    ).mock(return_value=httpx.Response(200, json={"id": "t1"}))
    client = ClockifyClient(config_writes)
    await tasks.update_task(
        client, project_id="p1", task_id="t1", name="Done", status="DONE", billable=False
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Done", "status": "DONE", "billable": False}
    await client.aclose()


@respx.mock
async def test_delete_task(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/tasks/t1"
    ).mock(return_value=httpx.Response(200, json={"id": "t1"}))
    client = ClockifyClient(config_writes)
    assert await tasks.delete_task(client, project_id="p1", task_id="t1") == {"id": "t1"}
    assert route.called
    await client.aclose()
