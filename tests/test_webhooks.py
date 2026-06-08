import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import webhooks


@respx.mock
async def test_list_webhooks_passes_type(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/webhooks").mock(
        return_value=httpx.Response(200, json=[{"id": "w1"}])
    )
    client = ClockifyClient(config)
    await webhooks.list_webhooks(client, type="USER_CREATED")
    assert dict(route.calls.last.request.url.params)["type"] == "USER_CREATED"
    await client.aclose()


@respx.mock
async def test_get_webhook(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1").mock(
        return_value=httpx.Response(200, json={"id": "w1"})
    )
    client = ClockifyClient(config)
    assert await webhooks.get_webhook(client, webhook_id="w1") == {"id": "w1"}
    await client.aclose()


@respx.mock
async def test_get_webhook_logs_posts_body_and_query(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1/logs"
    ).mock(return_value=httpx.Response(200, json=[]))
    client = ClockifyClient(config)
    await webhooks.get_webhook_logs(
        client, webhook_id="w1", status="FAILED", sort_by_newest=True, page=1, size=20
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["page"] == "1"
    assert sent["size"] == "20"
    body = json.loads(route.calls.last.request.content)
    assert body["status"] == "FAILED"
    assert body["sortByNewest"] is True
    await client.aclose()


@respx.mock
async def test_create_webhook_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/webhooks").mock(
        return_value=httpx.Response(201, json={"id": "w1"})
    )
    client = ClockifyClient(config_writes)
    await webhooks.create_webhook(
        client, url="https://e.com/h", trigger_source=["p1"],
        trigger_source_type="PROJECT_ID", webhook_event="NEW_TIME_ENTRY", name="My hook",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "url": "https://e.com/h", "triggerSource": ["p1"],
        "triggerSourceType": "PROJECT_ID", "webhookEvent": "NEW_TIME_ENTRY", "name": "My hook",
    }
    await client.aclose()


@respx.mock
async def test_update_webhook_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1").mock(
        return_value=httpx.Response(200, json={"id": "w1"})
    )
    client = ClockifyClient(config_writes)
    await webhooks.update_webhook(
        client, webhook_id="w1", url="https://e.com/h", trigger_source=["p1"],
        trigger_source_type="PROJECT_ID", webhook_event="NEW_TIME_ENTRY",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["url"] == "https://e.com/h"
    assert body["webhookEvent"] == "NEW_TIME_ENTRY"
    await client.aclose()


@respx.mock
async def test_delete_webhook(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1").mock(
        return_value=httpx.Response(200, json={})
    )
    client = ClockifyClient(config_writes)
    await webhooks.delete_webhook(client, webhook_id="w1")
    assert route.called
    await client.aclose()


@respx.mock
async def test_generate_webhook_token_patches(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1/token"
    ).mock(return_value=httpx.Response(200, json={"id": "w1"}))
    client = ClockifyClient(config_writes)
    await webhooks.generate_webhook_token(client, webhook_id="w1")
    assert route.called
    await client.aclose()
