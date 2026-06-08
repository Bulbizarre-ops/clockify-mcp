"""Custom fields domain (read + write).

Workspace-level custom fields under ``workspaces/{ws}/custom-fields`` and the
per-project apply/override under ``.../projects/{projectId}/custom-fields``.
Custom fields are a paid Clockify feature; the API errors on plans without it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_workspace_custom_fields(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    status: str | None = None,
    entity_type: str | None = None,
) -> Any:
    """List workspace custom fields. status is INACTIVE/VISIBLE/INVISIBLE;
    entity_type filters by the entity the field attaches to (e.g. TIMEENTRY)."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"name": name, "status": status, "entity-type": entity_type}
    return await client.get(f"workspaces/{ws}/custom-fields", params=params)


async def list_project_custom_fields(
    client: ClockifyClient,
    *,
    project_id: str,
    workspace_id: str | None = None,
    status: str | None = None,
    entity_type: str | None = None,
) -> Any:
    """List a project's custom fields (status INACTIVE/VISIBLE/INVISIBLE)."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"status": status, "entity-type": entity_type}
    return await client.get(
        f"workspaces/{ws}/projects/{project_id}/custom-fields", params=params
    )


async def create_workspace_custom_field(
    client: ClockifyClient,
    *,
    name: str,
    type: str,
    workspace_id: str | None = None,
    entity_type: str | None = None,
    allowed_values: list[str] | None = None,
    status: str | None = None,
    description: str | None = None,
    placeholder: str | None = None,
    only_admin_can_edit: bool | None = None,
) -> Any:
    """Create a workspace custom field.

    type is one of TXT, NUMBER, DROPDOWN_SINGLE, DROPDOWN_MULTIPLE, CHECKBOX, LINK.
    entity_type is TIMEENTRY or USER. allowed_values lists the options for DROPDOWN
    types. status is INACTIVE, VISIBLE, or INVISIBLE.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "type": type,
            "entityType": entity_type,
            "allowedValues": allowed_values,
            "status": status,
            "description": description,
            "placeholder": placeholder,
            "onlyAdminCanEdit": only_admin_can_edit,
        }
    )
    return await client.post(f"workspaces/{ws}/custom-fields", json=body)


async def update_workspace_custom_field(
    client: ClockifyClient,
    *,
    custom_field_id: str,
    name: str,
    type: str,
    workspace_id: str | None = None,
    required: bool | None = None,
    status: str | None = None,
    allowed_values: list[str] | None = None,
    description: str | None = None,
    placeholder: str | None = None,
    only_admin_can_edit: bool | None = None,
) -> Any:
    """Update a workspace custom field. name and type are required by the API (pass
    the current values if unchanged). type is one of TXT, NUMBER, DROPDOWN_SINGLE,
    DROPDOWN_MULTIPLE, CHECKBOX, LINK; status is INACTIVE, VISIBLE, or INVISIBLE."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "type": type,
            "required": required,
            "status": status,
            "allowedValues": allowed_values,
            "description": description,
            "placeholder": placeholder,
            "onlyAdminCanEdit": only_admin_can_edit,
        }
    )
    return await client.put(f"workspaces/{ws}/custom-fields/{custom_field_id}", json=body)


async def delete_workspace_custom_field(
    client: ClockifyClient, *, custom_field_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a workspace custom field. IRREVERSIBLE — the field and its values are
    permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/custom-fields/{custom_field_id}")


async def set_project_custom_field(
    client: ClockifyClient,
    *,
    project_id: str,
    custom_field_id: str,
    workspace_id: str | None = None,
    default_value: Any = None,
    status: str | None = None,
) -> Any:
    """Apply or override a workspace custom field on a project. default_value sets
    the project-level default; status is INACTIVE, VISIBLE, or INVISIBLE."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"defaultValue": default_value, "status": status})
    return await client.patch(
        f"workspaces/{ws}/projects/{project_id}/custom-fields/{custom_field_id}", json=body
    )


async def remove_project_custom_field(
    client: ClockifyClient,
    *,
    project_id: str,
    custom_field_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Remove a custom field's project-level override. IRREVERSIBLE for the project's
    custom-field settings (the workspace field itself is unaffected)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(
        f"workspaces/{ws}/projects/{project_id}/custom-fields/{custom_field_id}"
    )


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_workspace_custom_fields(
        workspace_id: str | None = None,
        name: str | None = None,
        status: str | None = None,
        entity_type: str | None = None,
    ) -> Any:
        """List workspace custom fields (status INACTIVE/VISIBLE/INVISIBLE)."""
        return await list_workspace_custom_fields_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            status=status,
            entity_type=entity_type,
        )

    @mcp.tool()
    async def list_project_custom_fields(
        project_id: str,
        workspace_id: str | None = None,
        status: str | None = None,
        entity_type: str | None = None,
    ) -> Any:
        """List a project's custom fields (status INACTIVE/VISIBLE/INVISIBLE)."""
        return await list_project_custom_fields_fn(
            client,
            project_id=project_id,
            workspace_id=workspace_id,
            status=status,
            entity_type=entity_type,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_workspace_custom_field(
        name: str,
        type: str,
        workspace_id: str | None = None,
        entity_type: str | None = None,
        allowed_values: list[str] | None = None,
        status: str | None = None,
        description: str | None = None,
        placeholder: str | None = None,
        only_admin_can_edit: bool | None = None,
    ) -> Any:
        """Create a workspace custom field. type is TXT, NUMBER, DROPDOWN_SINGLE,
        DROPDOWN_MULTIPLE, CHECKBOX, or LINK; entity_type is TIMEENTRY or USER."""
        return await create_workspace_custom_field_fn(
            client,
            name=name,
            type=type,
            workspace_id=workspace_id,
            entity_type=entity_type,
            allowed_values=allowed_values,
            status=status,
            description=description,
            placeholder=placeholder,
            only_admin_can_edit=only_admin_can_edit,
        )

    @mcp.tool()
    async def update_workspace_custom_field(
        custom_field_id: str,
        name: str,
        type: str,
        workspace_id: str | None = None,
        required: bool | None = None,
        status: str | None = None,
        allowed_values: list[str] | None = None,
        description: str | None = None,
        placeholder: str | None = None,
        only_admin_can_edit: bool | None = None,
    ) -> Any:
        """Update a workspace custom field. name and type are required by the API
        (pass current values if unchanged)."""
        return await update_workspace_custom_field_fn(
            client,
            custom_field_id=custom_field_id,
            name=name,
            type=type,
            workspace_id=workspace_id,
            required=required,
            status=status,
            allowed_values=allowed_values,
            description=description,
            placeholder=placeholder,
            only_admin_can_edit=only_admin_can_edit,
        )

    @mcp.tool()
    async def delete_workspace_custom_field(
        custom_field_id: str, workspace_id: str | None = None
    ) -> Any:
        """Delete a workspace custom field. IRREVERSIBLE — the field and its values
        are permanently removed."""
        return await delete_workspace_custom_field_fn(
            client, custom_field_id=custom_field_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def set_project_custom_field(
        project_id: str,
        custom_field_id: str,
        workspace_id: str | None = None,
        default_value: Any = None,
        status: str | None = None,
    ) -> Any:
        """Apply or override a workspace custom field on a project (sets its
        project-level default value and/or status)."""
        return await set_project_custom_field_fn(
            client,
            project_id=project_id,
            custom_field_id=custom_field_id,
            workspace_id=workspace_id,
            default_value=default_value,
            status=status,
        )

    @mcp.tool()
    async def remove_project_custom_field(
        project_id: str, custom_field_id: str, workspace_id: str | None = None
    ) -> Any:
        """Remove a custom field's project-level override (the workspace field itself
        is unaffected)."""
        return await remove_project_custom_field_fn(
            client,
            project_id=project_id,
            custom_field_id=custom_field_id,
            workspace_id=workspace_id,
        )


list_workspace_custom_fields_fn = list_workspace_custom_fields
list_project_custom_fields_fn = list_project_custom_fields
create_workspace_custom_field_fn = create_workspace_custom_field
update_workspace_custom_field_fn = update_workspace_custom_field
delete_workspace_custom_field_fn = delete_workspace_custom_field
set_project_custom_field_fn = set_project_custom_field
remove_project_custom_field_fn = remove_project_custom_field
