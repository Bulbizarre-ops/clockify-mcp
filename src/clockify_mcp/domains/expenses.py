# src/clockify_mcp/domains/expenses.py
"""Expenses domain: expenses + expense categories (read + write).

All endpoints are on the regular Clockify host under
``workspaces/{workspaceId}/expenses``. Creating and updating an expense use
multipart/form-data (the receipt file is optional); the receipt download is a
raw binary GET. Categories are plain JSON. Expenses are a paid Clockify feature;
the API errors on plans without it.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_expenses(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List expenses on the workspace (paginated), optionally for one user."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"user-id": user_id, **page_params(page, page_size)}
    return await client.get(f"workspaces/{ws}/expenses", params=params)


async def get_expense(
    client: ClockifyClient, *, expense_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single expense by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/expenses/{expense_id}")


async def list_expense_categories(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    archived: bool | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List expense categories (paginated).

    sort_column is NAME; sort_order is ASCENDING or DESCENDING; archived=True
    includes archived categories.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "archived": archived,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/expenses/categories", params=params)


async def download_expense_receipt(
    client: ClockifyClient,
    *,
    expense_id: str,
    file_id: str,
    save_path: str,
    workspace_id: str | None = None,
) -> Any:
    """Download an expense's receipt file to save_path (local filesystem).

    file_id is the expense's ``fileId``. Returns the path written, the byte
    count, and the file_id. The raw bytes are written to disk rather than
    returned inline so large binaries never enter the model context. save_path
    is written verbatim and overwrites any existing file; the caller is
    responsible for choosing a safe location.
    """
    ws = resolve_workspace_id(client, workspace_id)
    content = await client.get_bytes(
        f"workspaces/{ws}/expenses/{expense_id}/files/{file_id}"
    )
    Path(save_path).write_bytes(content)
    return {"path": save_path, "bytes": len(content), "file_id": file_id}


def _form_value(value: Any) -> str | None:
    """Coerce a scalar form-field value to a string, or None so drop_none strips it.

    The None passthrough is the reason this exists: it lets ``drop_none`` remove
    unset fields and drives the ``changeFields`` derivation in update_expense.
    Bool rendering is duplicated with the client's ``_form_str`` on purpose (both
    layers stay correct independently); don't remove either.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _receipt_files(receipt_path: str | None) -> dict[str, Any] | None:
    if not receipt_path:
        return None
    path = Path(receipt_path)
    if not path.is_file():
        raise FileNotFoundError(f"receipt_path not found: {receipt_path}")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {"file": (path.name, path.read_bytes(), mime)}


async def create_expense(
    client: ClockifyClient,
    *,
    amount: float,
    category_id: str,
    date: str,
    project_id: str,
    user_id: str,
    workspace_id: str | None = None,
    billable: bool | None = None,
    notes: str | None = None,
    task_id: str | None = None,
    receipt_path: str | None = None,
) -> Any:
    """Create an expense (multipart/form-data).

    amount, category_id, date (ISO-8601), project_id, and user_id are required.
    receipt_path is an optional local file to attach as the receipt. Field names
    are sent camelCase per the Clockify OpenAPI spec.
    """
    ws = resolve_workspace_id(client, workspace_id)
    data = drop_none(
        {
            "amount": _form_value(amount),
            "categoryId": category_id,
            "date": date,
            "projectId": project_id,
            "userId": user_id,
            "billable": _form_value(billable),
            "notes": notes,
            "taskId": task_id,
        }
    )
    files = _receipt_files(receipt_path)
    return await client.post_multipart(f"workspaces/{ws}/expenses", data=data, files=files)


async def update_expense(
    client: ClockifyClient,
    *,
    expense_id: str,
    amount: float,
    category_id: str,
    date: str,
    user_id: str,
    workspace_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    billable: bool | None = None,
    notes: str | None = None,
    receipt_path: str | None = None,
) -> Any:
    """Update an expense (multipart/form-data; full update).

    amount, category_id, date, and user_id are required by the API. changeFields
    (the list of fields being changed) is derived automatically from the optional
    fields you pass (project_id, task_id, billable, notes, receipt). receipt_path
    attaches a new receipt file.
    """
    ws = resolve_workspace_id(client, workspace_id)
    optional = {
        "projectId": project_id,
        "taskId": task_id,
        "billable": _form_value(billable),
        "notes": notes,
    }
    change_fields = [key for key, value in optional.items() if value is not None]
    if receipt_path:
        change_fields.append("file")
    data = drop_none(
        {
            "amount": _form_value(amount),
            "categoryId": category_id,
            "date": date,
            "userId": user_id,
            **optional,
        }
    )
    data["changeFields"] = change_fields
    files = _receipt_files(receipt_path)
    return await client.put_multipart(
        f"workspaces/{ws}/expenses/{expense_id}", data=data, files=files
    )


async def delete_expense(
    client: ClockifyClient, *, expense_id: str, workspace_id: str | None = None
) -> Any:
    """Delete an expense. IRREVERSIBLE — the expense is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/expenses/{expense_id}")


async def create_expense_category(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    has_unit_price: bool | None = None,
    price_in_cents: int | None = None,
    unit: str | None = None,
) -> Any:
    """Create an expense category. Set has_unit_price + price_in_cents + unit for
    unit-priced categories (e.g. mileage).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "hasUnitPrice": has_unit_price,
            "priceInCents": price_in_cents,
            "unit": unit,
        }
    )
    return await client.post(f"workspaces/{ws}/expenses/categories", json=body)


async def update_expense_category(
    client: ClockifyClient,
    *,
    category_id: str,
    name: str,
    workspace_id: str | None = None,
    has_unit_price: bool | None = None,
    price_in_cents: int | None = None,
    unit: str | None = None,
) -> Any:
    """Update an expense category (name is required)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "hasUnitPrice": has_unit_price,
            "priceInCents": price_in_cents,
            "unit": unit,
        }
    )
    return await client.put(f"workspaces/{ws}/expenses/categories/{category_id}", json=body)


async def delete_expense_category(
    client: ClockifyClient, *, category_id: str, workspace_id: str | None = None
) -> Any:
    """Delete an expense category. IRREVERSIBLE — the category is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/expenses/categories/{category_id}")


async def archive_expense_category(
    client: ClockifyClient,
    *,
    category_id: str,
    archived: bool,
    workspace_id: str | None = None,
) -> Any:
    """Archive (archived=True) or restore (archived=False) an expense category."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.patch(
        f"workspaces/{ws}/expenses/categories/{category_id}/status",
        json={"archived": archived},
    )


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_expenses(
        workspace_id: str | None = None,
        user_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List expenses on the workspace (paginated), optionally for one user."""
        return await list_expenses_fn(
            client, workspace_id=workspace_id, user_id=user_id, page=page, page_size=page_size
        )

    @mcp.tool()
    async def get_expense(expense_id: str, workspace_id: str | None = None) -> Any:
        """Get a single expense by id."""
        return await get_expense_fn(client, expense_id=expense_id, workspace_id=workspace_id)

    @mcp.tool()
    async def list_expense_categories(
        workspace_id: str | None = None,
        name: str | None = None,
        archived: bool | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List expense categories (paginated)."""
        return await list_expense_categories_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            archived=archived,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def download_expense_receipt(
        expense_id: str,
        file_id: str,
        save_path: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Download an expense's receipt file to a local path."""
        return await download_expense_receipt_fn(
            client,
            expense_id=expense_id,
            file_id=file_id,
            save_path=save_path,
            workspace_id=workspace_id,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_expense(
        amount: float,
        category_id: str,
        date: str,
        project_id: str,
        user_id: str,
        workspace_id: str | None = None,
        billable: bool | None = None,
        notes: str | None = None,
        task_id: str | None = None,
        receipt_path: str | None = None,
    ) -> Any:
        """Create an expense; receipt_path optionally attaches a local receipt file."""
        return await create_expense_fn(
            client,
            amount=amount,
            category_id=category_id,
            date=date,
            project_id=project_id,
            user_id=user_id,
            workspace_id=workspace_id,
            billable=billable,
            notes=notes,
            task_id=task_id,
            receipt_path=receipt_path,
        )

    @mcp.tool()
    async def update_expense(
        expense_id: str,
        amount: float,
        category_id: str,
        date: str,
        user_id: str,
        workspace_id: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        billable: bool | None = None,
        notes: str | None = None,
        receipt_path: str | None = None,
    ) -> Any:
        """Update an expense (multipart; changeFields derived from passed fields)."""
        return await update_expense_fn(
            client,
            expense_id=expense_id,
            amount=amount,
            category_id=category_id,
            date=date,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            task_id=task_id,
            billable=billable,
            notes=notes,
            receipt_path=receipt_path,
        )

    @mcp.tool()
    async def delete_expense(expense_id: str, workspace_id: str | None = None) -> Any:
        """Delete an expense. IRREVERSIBLE — the expense is permanently removed."""
        return await delete_expense_fn(
            client, expense_id=expense_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def create_expense_category(
        name: str,
        workspace_id: str | None = None,
        has_unit_price: bool | None = None,
        price_in_cents: int | None = None,
        unit: str | None = None,
    ) -> Any:
        """Create an expense category."""
        return await create_expense_category_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            has_unit_price=has_unit_price,
            price_in_cents=price_in_cents,
            unit=unit,
        )

    @mcp.tool()
    async def update_expense_category(
        category_id: str,
        name: str,
        workspace_id: str | None = None,
        has_unit_price: bool | None = None,
        price_in_cents: int | None = None,
        unit: str | None = None,
    ) -> Any:
        """Update an expense category (name required)."""
        return await update_expense_category_fn(
            client,
            category_id=category_id,
            name=name,
            workspace_id=workspace_id,
            has_unit_price=has_unit_price,
            price_in_cents=price_in_cents,
            unit=unit,
        )

    @mcp.tool()
    async def delete_expense_category(
        category_id: str, workspace_id: str | None = None
    ) -> Any:
        """Delete an expense category. IRREVERSIBLE — permanently removed."""
        return await delete_expense_category_fn(
            client, category_id=category_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def archive_expense_category(
        category_id: str, archived: bool, workspace_id: str | None = None
    ) -> Any:
        """Archive (archived=True) or restore (archived=False) an expense category."""
        return await archive_expense_category_fn(
            client, category_id=category_id, archived=archived, workspace_id=workspace_id
        )


list_expenses_fn = list_expenses
get_expense_fn = get_expense
list_expense_categories_fn = list_expense_categories
download_expense_receipt_fn = download_expense_receipt
create_expense_fn = create_expense
update_expense_fn = update_expense
delete_expense_fn = delete_expense
create_expense_category_fn = create_expense_category
update_expense_category_fn = update_expense_category
delete_expense_category_fn = delete_expense_category
archive_expense_category_fn = archive_expense_category
