"""Custom fields domain (read + write).

Workspace-level custom fields under ``workspaces/{ws}/custom-fields`` and the
per-project apply/override under ``.../projects/{projectId}/custom-fields``.
Custom fields are a paid Clockify feature; the API errors on plans without it.
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
_ProjectId = Annotated[
    str,
    Field(description="Id of the project whose custom fields to act on."),
]
_CustomFieldId = Annotated[
    str,
    Field(
        description="Id of the workspace custom field "
        "(opaque string from list_workspace_custom_fields)."
    ),
]
_NameFilter = Annotated[
    str | None,
    Field(description="Filter custom fields by name."),
]
_StatusFilter = Annotated[
    str | None,
    Field(description="Filter by status: INACTIVE, VISIBLE, or INVISIBLE."),
]
_EntityTypeFilter = Annotated[
    str | None,
    Field(
        description="Filter by the entity the field attaches to (e.g. TIMEENTRY, USER)."
    ),
]
_NewName = Annotated[
    str,
    Field(description="Display name for the custom field."),
]
_FieldType = Annotated[
    str,
    Field(
        description="Field type: TXT, NUMBER, DROPDOWN_SINGLE, DROPDOWN_MULTIPLE, "
        "CHECKBOX, or LINK."
    ),
]
_EntityType = Annotated[
    str | None,
    Field(description="Entity the field attaches to: TIMEENTRY or USER."),
]
_AllowedValues = Annotated[
    list[str] | None,
    Field(description="Options for DROPDOWN_SINGLE/DROPDOWN_MULTIPLE field types."),
]
_Status = Annotated[
    str | None,
    Field(description="Field status: INACTIVE, VISIBLE, or INVISIBLE."),
]
_Description = Annotated[
    str | None,
    Field(description="Optional descriptive text for the field."),
]
_Placeholder = Annotated[
    str | None,
    Field(description="Optional placeholder text shown in the field input."),
]
_OnlyAdminCanEdit = Annotated[
    bool | None,
    Field(description="When true, only admins may edit the field's value."),
]
_Required = Annotated[
    bool | None,
    Field(description="When true, the field must be filled in."),
]
_DefaultValue = Annotated[
    Any,
    Field(description="Project-level default value for the applied custom field."),
]


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


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_workspace_custom_fields(
        workspace_id: _WorkspaceId = None,
        name: _NameFilter = None,
        status: _StatusFilter = None,
        entity_type: _EntityTypeFilter = None,
    ) -> Any:
        """List custom fields defined at the workspace level, optionally filtered.

        Read-only; scoped to the workspace. Filter by name, by status
        (INACTIVE/VISIBLE/INVISIBLE), or by entity_type (the entity the field
        attaches to, e.g. TIMEENTRY or USER). Use this to discover custom-field
        ids before applying a field to a project or updating it; use
        list_project_custom_fields to see what is applied on a specific project.
        Custom fields are a paid Clockify feature; the API errors on plans without
        it. Returns a list of custom-field objects.
        """
        return await list_workspace_custom_fields_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            status=status,
            entity_type=entity_type,
        )

    @mcp.tool()
    async def list_project_custom_fields(
        project_id: _ProjectId,
        workspace_id: _WorkspaceId = None,
        status: _StatusFilter = None,
        entity_type: _EntityTypeFilter = None,
    ) -> Any:
        """List the custom fields applied to one specific project.

        Read-only; scoped to the workspace and the given project. Unlike
        list_workspace_custom_fields (which lists every field defined on the
        workspace), this returns only the fields applied/overridden on this
        project, including their project-level settings. Filter by status
        (INACTIVE/VISIBLE/INVISIBLE) or entity_type. Custom fields are a paid
        Clockify feature. Returns a list of custom-field objects.
        """
        return await list_project_custom_fields_fn(
            client,
            project_id=project_id,
            workspace_id=workspace_id,
            status=status,
            entity_type=entity_type,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_workspace_custom_field(
        name: _NewName,
        type: _FieldType,
        workspace_id: _WorkspaceId = None,
        entity_type: _EntityType = None,
        allowed_values: _AllowedValues = None,
        status: _Status = None,
        description: _Description = None,
        placeholder: _Placeholder = None,
        only_admin_can_edit: _OnlyAdminCanEdit = None,
    ) -> Any:
        """Create a new custom field at the workspace level.

        Write operation; scoped to the workspace. type is TXT, NUMBER,
        DROPDOWN_SINGLE, DROPDOWN_MULTIPLE, CHECKBOX, or LINK; entity_type is
        TIMEENTRY or USER; allowed_values supplies the options for DROPDOWN types;
        status is INACTIVE, VISIBLE, or INVISIBLE. This defines the field on the
        workspace — use set_project_custom_field afterwards to apply or override it
        on a project. Returns the created field including its newly assigned id.
        """
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
        custom_field_id: _CustomFieldId,
        name: _NewName,
        type: _FieldType,
        workspace_id: _WorkspaceId = None,
        required: _Required = None,
        status: _Status = None,
        allowed_values: _AllowedValues = None,
        description: _Description = None,
        placeholder: _Placeholder = None,
        only_admin_can_edit: _OnlyAdminCanEdit = None,
    ) -> Any:
        """Update an existing workspace custom field by its id.

        Write operation; scoped to the workspace. name and type are required by the
        API — pass the current values if you do not want to change them. type is
        TXT, NUMBER, DROPDOWN_SINGLE, DROPDOWN_MULTIPLE, CHECKBOX, or LINK; status
        is INACTIVE, VISIBLE, or INVISIBLE. Use list_workspace_custom_fields to find
        the custom_field_id. Returns the updated field.
        """
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
        custom_field_id: _CustomFieldId, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Permanently delete a workspace custom field by its id.

        Write operation and IRREVERSIBLE — the field and all of its stored values
        are permanently removed across the workspace. To merely hide a field rather
        than remove it, use update_workspace_custom_field with status=INVISIBLE.
        Use remove_project_custom_field to drop only a project-level override
        without deleting the workspace field.
        """
        return await delete_workspace_custom_field_fn(
            client, custom_field_id=custom_field_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def set_project_custom_field(
        project_id: _ProjectId,
        custom_field_id: _CustomFieldId,
        workspace_id: _WorkspaceId = None,
        default_value: _DefaultValue = None,
        status: _Status = None,
    ) -> Any:
        """Apply or override a workspace custom field on a specific project.

        Write operation (PATCH); scoped to the workspace and project. Sets the
        project-level default_value and/or status (INACTIVE, VISIBLE, or INVISIBLE)
        for an existing workspace field — it does not create a new field
        (use create_workspace_custom_field for that). Use
        remove_project_custom_field to undo the project-level override. Returns the
        applied project custom-field settings.
        """
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
        project_id: _ProjectId,
        custom_field_id: _CustomFieldId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Remove a custom field's project-level override from one project.

        Write operation and IRREVERSIBLE for that project's custom-field settings;
        scoped to the workspace and project. The workspace field itself is
        unaffected — only the project-level override applied via
        set_project_custom_field is dropped. To delete the field everywhere, use
        delete_workspace_custom_field instead.
        """
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
