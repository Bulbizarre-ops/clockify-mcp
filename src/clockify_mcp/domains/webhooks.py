"""Webhooks domain (read + write).

Workspace-scoped webhooks under ``workspaces/{ws}/webhooks`` on the regular host.
Logs are fetched via POST (filters in the body, page/size as query params). This
server only manages Clockify webhook definitions — it is not a webhook receiver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# --- Parameter descriptions (surfaced to MCP clients via the tool input schema) ---
_WorkspaceId = Annotated[
    str | None,
    Field(description="Workspace id; omit to use the configured default_workspace_id."),
]
_WebhookId = Annotated[
    str,
    Field(description="Id of the webhook (opaque string returned by list_webhooks)."),
]
_TypeFilter = Annotated[
    str | None,
    Field(description="Filter webhooks by origin: USER_CREATED, SYSTEM, or ADDON."),
]
_LogFrom = Annotated[
    str | None,
    Field(description="ISO-8601 start of the delivery-log time range."),
]
_LogTo = Annotated[
    str | None,
    Field(description="ISO-8601 end of the delivery-log time range."),
]
_SortByNewest = Annotated[
    bool | None,
    Field(description="When true, return delivery logs newest-first."),
]
_LogStatus = Annotated[
    str | None,
    Field(description="Filter delivery logs by status: ALL, SUCCEEDED, or FAILED."),
]
_LogPage = Annotated[
    int | None,
    Field(description="1-based page number for delivery logs."),
]
_LogSize = Annotated[
    int | None,
    Field(description="Number of delivery-log entries per page."),
]
_Url = Annotated[
    str,
    Field(description="Destination URL Clockify will POST event payloads to."),
]
_TriggerSource = Annotated[
    list[str],
    Field(
        description="List of entity ids whose type matches trigger_source_type "
        "(e.g. project ids when type is PROJECT_ID)."
    ),
]
_TriggerSourceType = Annotated[
    str,
    Field(
        description="Type of the trigger_source ids: PROJECT_ID, USER_ID, TAG_ID, "
        "TASK_ID, WORKSPACE_ID, ASSIGNMENT_ID, or EXPENSE_ID."
    ),
]
_WebhookEvent = Annotated[
    str,
    Field(
        description="Single event name that fires the webhook "
        "(e.g. NEW_TIME_ENTRY, NEW_INVOICE)."
    ),
]
_Name = Annotated[
    str | None,
    Field(description="Optional human-readable name for the webhook."),
]


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


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_webhooks(
        workspace_id: _WorkspaceId = None,
        type: _TypeFilter = None,
    ) -> Any:
        """List webhook definitions on a workspace, optionally filtered by origin.

        Read-only. type filters by USER_CREATED, SYSTEM, or ADDON. Use this to
        discover webhook ids before calling get_webhook, get_webhook_logs, or any
        write tool. This server only manages Clockify webhook definitions — it is
        not a webhook receiver. Returns a list of webhook objects.
        """
        return await list_webhooks_fn(client, workspace_id=workspace_id, type=type)

    @mcp.tool()
    async def get_webhook(
        webhook_id: _WebhookId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Get a single webhook's full definition by its id.

        Read-only. Use list_webhooks first to look up the id. For this webhook's
        delivery history use get_webhook_logs instead. Returns one webhook object
        (url, trigger source, event, name).
        """
        return await get_webhook_fn(client, webhook_id=webhook_id, workspace_id=workspace_id)

    @mcp.tool()
    async def get_webhook_logs(
        webhook_id: _WebhookId,
        workspace_id: _WorkspaceId = None,
        from_: _LogFrom = None,
        to: _LogTo = None,
        sort_by_newest: _SortByNewest = None,
        status: _LogStatus = None,
        page: _LogPage = None,
        size: _LogSize = None,
    ) -> Any:
        """Get a webhook's delivery (call) logs, optionally filtered by time and status.

        Read-only; results are paginated via page/size (query params) while the
        from_/to/sort_by_newest/status filters are sent in a POST body. from_/to are
        ISO-8601; status filters by ALL, SUCCEEDED, or FAILED. Use get_webhook for the
        definition itself; use this to inspect each delivery attempt and outcome.
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


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_webhook(
        url: _Url,
        trigger_source: _TriggerSource,
        trigger_source_type: _TriggerSourceType,
        webhook_event: _WebhookEvent,
        workspace_id: _WorkspaceId = None,
        name: _Name = None,
    ) -> Any:
        """Create a webhook that POSTs an event payload to a URL.

        Write operation. trigger_source is a list of entity ids whose type matches
        trigger_source_type (PROJECT_ID/USER_ID/TAG_ID/TASK_ID/WORKSPACE_ID/
        ASSIGNMENT_ID/EXPENSE_ID); webhook_event is a single event name (e.g.
        NEW_TIME_ENTRY, NEW_INVOICE). Returns the created webhook including its new id
        and signing token. Use update_webhook to change it later.
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
        webhook_id: _WebhookId,
        url: _Url,
        trigger_source: _TriggerSource,
        trigger_source_type: _TriggerSourceType,
        webhook_event: _WebhookEvent,
        workspace_id: _WorkspaceId = None,
        name: _Name = None,
    ) -> Any:
        """Update an existing webhook by id (full replace; same fields as create_webhook).

        Write operation. All of url/trigger_source/trigger_source_type/webhook_event
        are re-sent, so supply the full intended state rather than a partial change.
        To rotate only the signing token use generate_webhook_token; to remove the
        webhook use delete_webhook. Returns the updated webhook.
        """
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
        webhook_id: _WebhookId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Permanently delete a webhook from a workspace by its id.

        Write operation and IRREVERSIBLE — the webhook is removed and stops
        receiving events. There is no archive/disable equivalent; recreate it with
        create_webhook if you need it again.
        """
        return await delete_webhook_fn(client, webhook_id=webhook_id, workspace_id=workspace_id)

    @mcp.tool()
    async def generate_webhook_token(
        webhook_id: _WebhookId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Regenerate (rotate) a webhook's signing token.

        Write operation. The previous token immediately stops working, so any
        receiver verifying signatures must be updated to the new token. Use this
        instead of update_webhook when only the token needs rotating. Returns the
        webhook with its new token.
        """
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
