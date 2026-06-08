"""Webhooks domain (read + write).

Workspace-scoped webhooks under ``workspaces/{ws}/webhooks`` on the regular host.
Logs are fetched via POST (filters in the body, page/size as query params). This
server only manages Clockify webhook definitions — it is not a webhook receiver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_webhooks(
    client: ClockifyClient, *, workspace_id: str | None = None, type: str | None = None
) -> Any:
    """List webhooks. type filters by USER_CREATED, SYSTEM, or ADDON."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/webhooks", params={"type": type})


async def get_webhook(
    client: ClockifyClient, *, webhook_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single webhook by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/webhooks/{webhook_id}")


async def get_webhook_logs(
    client: ClockifyClient,
    *,
    webhook_id: str,
    workspace_id: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    sort_by_newest: bool | None = None,
    status: str | None = None,
    page: int | None = None,
    size: int | None = None,
) -> Any:
    """Get a webhook's delivery logs (POST filter body; page/size are query params).

    from_/to are ISO-8601. status filters by ALL/SUCCEEDED/FAILED.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {"from": from_, "to": to, "sortByNewest": sort_by_newest, "status": status}
    )
    params = drop_none({"page": page, "size": size})
    return await client.post(
        f"workspaces/{ws}/webhooks/{webhook_id}/logs", json=body, params=params or None
    )


async def create_webhook(
    client: ClockifyClient,
    *,
    url: str,
    trigger_source: list[str],
    trigger_source_type: str,
    webhook_event: str,
    workspace_id: str | None = None,
    name: str | None = None,
) -> Any:
    """Create a webhook.

    trigger_source is a list of entity IDs whose type matches trigger_source_type
    (PROJECT_ID/USER_ID/TAG_ID/TASK_ID/WORKSPACE_ID/ASSIGNMENT_ID/EXPENSE_ID).
    webhook_event is a single event name (e.g. NEW_TIME_ENTRY, NEW_INVOICE).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "url": url,
            "triggerSource": trigger_source,
            "triggerSourceType": trigger_source_type,
            "webhookEvent": webhook_event,
            "name": name,
        }
    )
    return await client.post(f"workspaces/{ws}/webhooks", json=body)


async def update_webhook(
    client: ClockifyClient,
    *,
    webhook_id: str,
    url: str,
    trigger_source: list[str],
    trigger_source_type: str,
    webhook_event: str,
    workspace_id: str | None = None,
    name: str | None = None,
) -> Any:
    """Update a webhook (full replace; same fields as create)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "url": url,
            "triggerSource": trigger_source,
            "triggerSourceType": trigger_source_type,
            "webhookEvent": webhook_event,
            "name": name,
        }
    )
    return await client.put(f"workspaces/{ws}/webhooks/{webhook_id}", json=body)


async def delete_webhook(
    client: ClockifyClient, *, webhook_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a webhook. IRREVERSIBLE — permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/webhooks/{webhook_id}")


async def generate_webhook_token(
    client: ClockifyClient, *, webhook_id: str, workspace_id: str | None = None
) -> Any:
    """Regenerate a webhook's signing token. The old token stops working."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.patch(f"workspaces/{ws}/webhooks/{webhook_id}/token")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_webhooks(
        workspace_id: str | None = None,
        type: str | None = None,
    ) -> Any:
        """List webhooks. type filters by USER_CREATED, SYSTEM, or ADDON."""
        return await list_webhooks_fn(client, workspace_id=workspace_id, type=type)

    @mcp.tool()
    async def get_webhook(
        webhook_id: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Get a single webhook by id."""
        return await get_webhook_fn(client, webhook_id=webhook_id, workspace_id=workspace_id)

    @mcp.tool()
    async def get_webhook_logs(
        webhook_id: str,
        workspace_id: str | None = None,
        from_: str | None = None,
        to: str | None = None,
        sort_by_newest: bool | None = None,
        status: str | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> Any:
        """Get a webhook's delivery logs (POST filter body; page/size are query params).

        from_/to are ISO-8601. status filters by ALL/SUCCEEDED/FAILED.
        """
        return await get_webhook_logs_fn(
            client,
            webhook_id=webhook_id,
            workspace_id=workspace_id,
            from_=from_,
            to=to,
            sort_by_newest=sort_by_newest,
            status=status,
            page=page,
            size=size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_webhook(
        url: str,
        trigger_source: list[str],
        trigger_source_type: str,
        webhook_event: str,
        workspace_id: str | None = None,
        name: str | None = None,
    ) -> Any:
        """Create a webhook.

        trigger_source is a list of entity IDs whose type matches trigger_source_type
        (PROJECT_ID/USER_ID/TAG_ID/TASK_ID/WORKSPACE_ID/ASSIGNMENT_ID/EXPENSE_ID).
        webhook_event is a single event name (e.g. NEW_TIME_ENTRY, NEW_INVOICE).
        """
        return await create_webhook_fn(
            client,
            url=url,
            trigger_source=trigger_source,
            trigger_source_type=trigger_source_type,
            webhook_event=webhook_event,
            workspace_id=workspace_id,
            name=name,
        )

    @mcp.tool()
    async def update_webhook(
        webhook_id: str,
        url: str,
        trigger_source: list[str],
        trigger_source_type: str,
        webhook_event: str,
        workspace_id: str | None = None,
        name: str | None = None,
    ) -> Any:
        """Update a webhook (full replace; same fields as create)."""
        return await update_webhook_fn(
            client,
            webhook_id=webhook_id,
            url=url,
            trigger_source=trigger_source,
            trigger_source_type=trigger_source_type,
            webhook_event=webhook_event,
            workspace_id=workspace_id,
            name=name,
        )

    @mcp.tool()
    async def delete_webhook(
        webhook_id: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Delete a webhook. IRREVERSIBLE — permanently removed."""
        return await delete_webhook_fn(client, webhook_id=webhook_id, workspace_id=workspace_id)

    @mcp.tool()
    async def generate_webhook_token(
        webhook_id: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Regenerate a webhook's signing token. The old token stops working."""
        return await generate_webhook_token_fn(
            client, webhook_id=webhook_id, workspace_id=workspace_id
        )


list_webhooks_fn = list_webhooks
get_webhook_fn = get_webhook
get_webhook_logs_fn = get_webhook_logs
create_webhook_fn = create_webhook
update_webhook_fn = update_webhook
delete_webhook_fn = delete_webhook
generate_webhook_token_fn = generate_webhook_token
