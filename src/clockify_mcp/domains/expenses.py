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
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# --- Parameter descriptions (surfaced to MCP clients via the tool input schema) ---
_WorkspaceId = Annotated[
    str | None,
    Field(description="Workspace id; omit to use the configured default_workspace_id."),
]
_UserIdFilter = Annotated[
    str | None,
    Field(description="Limit results to expenses for this user id; omit for all users."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number for paginated results."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of results per page."),
]
_ExpenseId = Annotated[
    str,
    Field(description="Id of the expense (opaque string returned by list_expenses)."),
]
_CategoryNameFilter = Annotated[
    str | None,
    Field(description="Filter expense categories by name."),
]
_ArchivedFilter = Annotated[
    bool | None,
    Field(description="When true, include archived categories (excluded by default)."),
]
_SortColumn = Annotated[
    str | None,
    Field(description="Column to sort categories by; only NAME is supported."),
]
_SortOrder = Annotated[
    str | None,
    Field(description="Sort direction: ASCENDING or DESCENDING."),
]
_FileId = Annotated[
    str,
    Field(description="The expense's receipt fileId (the 'fileId' on the expense object)."),
]
_SavePath = Annotated[
    str,
    Field(
        description="Local filesystem path to write the receipt to; written verbatim "
        "and overwrites any existing file."
    ),
]
_Amount = Annotated[
    float,
    Field(description="Expense amount (required)."),
]
_CategoryIdReq = Annotated[
    str,
    Field(description="Id of the expense category (required); discover ids via "
                      "list_expense_categories."),
]
_DateReq = Annotated[
    str,
    Field(description="Expense date in ISO-8601 format (required)."),
]
_ProjectIdReq = Annotated[
    str,
    Field(description="Id of the project the expense belongs to (required)."),
]
_ProjectIdOpt = Annotated[
    str | None,
    Field(description="Id of the project the expense belongs to."),
]
_ExpenseUserId = Annotated[
    str,
    Field(description="Id of the user the expense is recorded for (required)."),
]
_Billable = Annotated[
    bool | None,
    Field(description="Whether the expense is billable."),
]
_Notes = Annotated[
    str | None,
    Field(description="Free-text notes for the expense."),
]
_TaskId = Annotated[
    str | None,
    Field(description="Id of the task the expense is associated with."),
]
_ReceiptPath = Annotated[
    str | None,
    Field(description="Local file path to attach as the receipt (multipart upload); "
                      "omit to send no receipt."),
]
_CategoryIdPath = Annotated[
    str,
    Field(description="Id of the expense category to act on."),
]
_CategoryName = Annotated[
    str,
    Field(description="Display name for the expense category (required)."),
]
_HasUnitPrice = Annotated[
    bool | None,
    Field(description="True for a unit-priced category (e.g. mileage); pair with "
                      "price_in_cents and unit."),
]
_PriceInCents = Annotated[
    int | None,
    Field(description="Unit price in cents for a unit-priced category."),
]
_Unit = Annotated[
    str | None,
    Field(description="Unit label for a unit-priced category (e.g. km, mile)."),
]
_ArchivedSet = Annotated[
    bool,
    Field(description="True archives (hides) the category; false restores it."),
]


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
        workspace_id: _WorkspaceId = None,
        user_id: _UserIdFilter = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List expenses recorded on a workspace, optionally scoped to one user.

        Read-only; results are paginated. Use this to discover expense ids before
        calling get_expense, update_expense, or delete_expense. Pass user_id to
        narrow to a single user. Expenses are a paid Clockify feature; the API
        errors on plans without it. Returns a list of expense objects.
        """
        return await list_expenses_fn(
            client, workspace_id=workspace_id, user_id=user_id, page=page, page_size=page_size
        )

    @mcp.tool()
    async def get_expense(expense_id: _ExpenseId, workspace_id: _WorkspaceId = None) -> Any:
        """Get a single expense's full detail by its id.

        Read-only. Use list_expenses first to look up the id. Returns one expense
        object, including its receipt fileId (pass that to download_expense_receipt).
        """
        return await get_expense_fn(client, expense_id=expense_id, workspace_id=workspace_id)

    @mcp.tool()
    async def list_expense_categories(
        workspace_id: _WorkspaceId = None,
        name: _CategoryNameFilter = None,
        archived: _ArchivedFilter = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List expense categories on a workspace (e.g. travel, meals, mileage).

        Read-only; results are paginated. Distinct from list_expenses, which lists
        the expenses themselves — categories are the reusable types you assign to
        an expense via its category_id. sort_column is NAME; sort_order is
        ASCENDING or DESCENDING; archived=True includes archived categories.
        Returns a list of category objects.
        """
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
        expense_id: _ExpenseId,
        file_id: _FileId,
        save_path: _SavePath,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Download an expense's receipt file to a local path on the filesystem.

        Read-only on the server. file_id is the expense's fileId (get it from
        get_expense or list_expenses). The raw bytes are written to save_path (the
        file is overwritten) rather than returned inline, so large binaries never
        enter the model context. Returns {path, bytes, file_id}.
        """
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
        amount: _Amount,
        category_id: _CategoryIdReq,
        date: _DateReq,
        project_id: _ProjectIdReq,
        user_id: _ExpenseUserId,
        workspace_id: _WorkspaceId = None,
        billable: _Billable = None,
        notes: _Notes = None,
        task_id: _TaskId = None,
        receipt_path: _ReceiptPath = None,
    ) -> Any:
        """Create an expense, optionally attaching a receipt file.

        Write operation; sent as multipart/form-data. amount, category_id, date
        (ISO-8601), project_id, and user_id are required. receipt_path is a local
        file uploaded as the receipt (omit to send none). Returns the created
        expense including its newly assigned id.
        """
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
        expense_id: _ExpenseId,
        amount: _Amount,
        category_id: _CategoryIdReq,
        date: _DateReq,
        user_id: _ExpenseUserId,
        workspace_id: _WorkspaceId = None,
        project_id: _ProjectIdOpt = None,
        task_id: _TaskId = None,
        billable: _Billable = None,
        notes: _Notes = None,
        receipt_path: _ReceiptPath = None,
    ) -> Any:
        """Update an existing expense, optionally replacing its receipt.

        Write operation; sent as multipart/form-data. amount, category_id, date,
        and user_id are required by the API. The changeFields list is derived
        automatically from the optional fields you pass (project_id, task_id,
        billable, notes, and receipt). receipt_path uploads a new receipt file.
        Returns the updated expense.
        """
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
    async def delete_expense(expense_id: _ExpenseId, workspace_id: _WorkspaceId = None) -> Any:
        """Permanently delete an expense from a workspace.

        Write operation and IRREVERSIBLE — the expense is removed. Use
        list_expenses to confirm the id first.
        """
        return await delete_expense_fn(
            client, expense_id=expense_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def create_expense_category(
        name: _CategoryName,
        workspace_id: _WorkspaceId = None,
        has_unit_price: _HasUnitPrice = None,
        price_in_cents: _PriceInCents = None,
        unit: _Unit = None,
    ) -> Any:
        """Create an expense category (a reusable expense type).

        Write operation. For unit-priced categories (e.g. mileage) set
        has_unit_price=True together with price_in_cents and unit. Returns the
        created category including its newly assigned id, usable as an expense's
        category_id.
        """
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
        category_id: _CategoryIdPath,
        name: _CategoryName,
        workspace_id: _WorkspaceId = None,
        has_unit_price: _HasUnitPrice = None,
        price_in_cents: _PriceInCents = None,
        unit: _Unit = None,
    ) -> Any:
        """Update an expense category's name and unit-pricing settings.

        Write operation; name is required. Set has_unit_price, price_in_cents, and
        unit to configure unit-pricing. To hide a category instead, use
        archive_expense_category. Returns the updated category.
        """
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
        category_id: _CategoryIdPath, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Permanently delete an expense category from a workspace.

        Write operation and IRREVERSIBLE — the category is removed. If you only
        want to hide it, use archive_expense_category(archived=True) instead.
        """
        return await delete_expense_category_fn(
            client, category_id=category_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def archive_expense_category(
        category_id: _CategoryIdPath, archived: _ArchivedSet, workspace_id: _WorkspaceId = None
    ) -> Any:
        """Archive or restore an expense category without deleting it.

        Write operation. Pass archived=True to hide the category or archived=False
        to restore it — prefer this over delete_expense_category when you may need
        the category again. Returns the updated category.
        """
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
