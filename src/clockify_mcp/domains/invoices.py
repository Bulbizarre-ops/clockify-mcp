"""Invoices domain (read + write).

Endpoints under ``workspaces/{ws}/invoices`` on the regular host. Creating an
invoice yields an empty invoice (no line items in the create body); items are
added via add_invoice_item / import_invoice_items. Status changes go through a
dedicated PATCH. Invoices are a paid Clockify feature.
"""

from __future__ import annotations

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
_InvoiceId = Annotated[
    str,
    Field(description="Id of the invoice (opaque string returned by list_invoices)."),
]
_PaymentId = Annotated[
    str,
    Field(description="Id of a recorded payment (returned by get_invoice_payments)."),
]
_Statuses = Annotated[
    str | None,
    Field(
        description="Filter invoices by status: "
        "UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE."
    ),
]
_SortColumn = Annotated[
    str | None,
    Field(
        description="Column to sort by: "
        "ID/CLIENT/DUE_ON/ISSUE_DATE/AMOUNT/BALANCE."
    ),
]
_SortOrder = Annotated[
    str | None,
    Field(description="Sort direction: ASCENDING or DESCENDING."),
]
_Page = Annotated[
    int | None,
    Field(description="1-based page number."),
]
_PageSize = Annotated[
    int | None,
    Field(description="Number of results per page."),
]
_ClientId = Annotated[
    str,
    Field(description="Id of the client the invoice is billed to."),
]
_Currency = Annotated[
    str,
    Field(description="Invoice currency code (e.g. USD)."),
]
_IssuedDate = Annotated[
    str,
    Field(description="Invoice issue date, ISO-8601."),
]
_DueDate = Annotated[
    str,
    Field(description="Invoice due date, ISO-8601."),
]
_Number = Annotated[
    str,
    Field(description="Human-facing invoice number."),
]
_TimeViewMode = Annotated[
    str | None,
    Field(description="Time view mode: TIME_SENSITIVE_VIEW or AGGREGATED_TIME_VIEW."),
]
_DiscountPercent = Annotated[
    float,
    Field(description="Discount applied to the invoice, as a percentage."),
]
_TaxPercent = Annotated[
    float,
    Field(description="Primary tax rate applied to the invoice, as a percentage."),
]
_Tax2Percent = Annotated[
    float,
    Field(description="Secondary tax rate applied to the invoice, as a percentage."),
]
_UpdateClientId = Annotated[
    str | None,
    Field(description="Id of the client to bill; omit to leave unchanged."),
]
_CompanyId = Annotated[
    str | None,
    Field(description="Id of the issuing company; omit to leave unchanged."),
]
_Note = Annotated[
    str | None,
    Field(description="Free-text note shown on the invoice."),
]
_Subject = Annotated[
    str | None,
    Field(description="Invoice subject line."),
]
_InvoiceStatus = Annotated[
    str,
    Field(
        description="New status: "
        "UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE."
    ),
]
_ApplyTaxes = Annotated[
    str,
    Field(description="Which taxes apply to the item: TAX1/TAX2/TAX1TAX2/NONE."),
]
_ItemDescription = Annotated[
    str,
    Field(description="Description text for the line item."),
]
_ItemType = Annotated[
    str,
    Field(description='Free-text item-type label (e.g. "Service").'),
]
_Quantity = Annotated[
    int,
    Field(description="Quantity for the line item (integer)."),
]
_UnitPrice = Annotated[
    int,
    Field(description="Unit price in minor units (integer)."),
]
_From = Annotated[
    str,
    Field(description="Start of the import period, ISO-8601."),
]
_To = Annotated[
    str,
    Field(description="End of the import period, ISO-8601."),
]
_ImportExpenses = Annotated[
    bool,
    Field(description="When true, also import expenses (not only time entries)."),
]
_TimeEntryGroupType = Annotated[
    str,
    Field(description="Grouping of imported time entries: SINGLE_ITEM/GROUPED/DETAILED."),
]
_ProjectIds = Annotated[
    list[str] | None,
    Field(description="Project ids to filter the imported time entries by."),
]
_ProjectFilterContains = Annotated[
    str | None,
    Field(
        description="Project-filter match mode: "
        "CONTAINS/DOES_NOT_CONTAIN/CONTAINS_ONLY."
    ),
]
_ProjectFilterStatus = Annotated[
    str | None,
    Field(description="Project status filter: ACTIVE/ARCHIVED/ALL."),
]
_PrimaryGroupBy = Annotated[
    str | None,
    Field(description="Primary group-by for GROUPED imports (PROJECT/USER/DATE etc.)."),
]
_SecondaryGroupBy = Annotated[
    str | None,
    Field(description="Secondary group-by for GROUPED imports (PROJECT/USER/DATE etc.)."),
]
_Amount = Annotated[
    int | None,
    Field(description="Payment amount in minor units (integer)."),
]
_PaymentNote = Annotated[
    str | None,
    Field(description="Free-text note for the payment."),
]
_PaymentDate = Annotated[
    str | None,
    Field(description="Date the payment was made, ISO-8601."),
]


async def list_invoices(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    statuses: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List invoices (paginated).

    statuses filters by UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE. sort_column
    is ID/CLIENT/DUE_ON/ISSUE_DATE/AMOUNT/BALANCE; sort_order ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "statuses": statuses,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/invoices", params=params)


async def get_invoice(
    client: ClockifyClient, *, invoice_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single invoice by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/invoices/{invoice_id}")


async def get_invoice_payments(
    client: ClockifyClient,
    *,
    invoice_id: str,
    workspace_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List an invoice's payments (paginated)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(
        f"workspaces/{ws}/invoices/{invoice_id}/payments", params=page_params(page, page_size)
    )


async def create_invoice(
    client: ClockifyClient,
    *,
    client_id: str,
    currency: str,
    issued_date: str,
    due_date: str,
    number: str,
    workspace_id: str | None = None,
    time_view_mode: str | None = None,
) -> Any:
    """Create an invoice (empty — add items separately).

    Required: client_id, currency, issued_date, due_date, number (all ISO-8601
    for the dates). time_view_mode is TIME_SENSITIVE_VIEW or AGGREGATED_TIME_VIEW.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "clientId": client_id,
            "currency": currency,
            "issuedDate": issued_date,
            "dueDate": due_date,
            "number": number,
            "timeViewMode": time_view_mode,
        }
    )
    return await client.post(f"workspaces/{ws}/invoices", json=body)


async def update_invoice(
    client: ClockifyClient,
    *,
    invoice_id: str,
    currency: str,
    number: str,
    issued_date: str,
    due_date: str,
    discount_percent: float,
    tax_percent: float,
    tax2_percent: float,
    workspace_id: str | None = None,
    client_id: str | None = None,
    company_id: str | None = None,
    note: str | None = None,
    subject: str | None = None,
) -> Any:
    """Update an invoice (full replace). Required: currency, number, issued_date,
    due_date, discount_percent, tax_percent, tax2_percent."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "currency": currency,
            "number": number,
            "issuedDate": issued_date,
            "dueDate": due_date,
            "discountPercent": discount_percent,
            "taxPercent": tax_percent,
            "tax2Percent": tax2_percent,
            "clientId": client_id,
            "companyId": company_id,
            "note": note,
            "subject": subject,
        }
    )
    return await client.put(f"workspaces/{ws}/invoices/{invoice_id}", json=body)


async def change_invoice_status(
    client: ClockifyClient,
    *,
    invoice_id: str,
    invoice_status: str,
    workspace_id: str | None = None,
) -> Any:
    """Change an invoice's status: UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.patch(
        f"workspaces/{ws}/invoices/{invoice_id}/status", json={"invoiceStatus": invoice_status}
    )


async def duplicate_invoice(
    client: ClockifyClient, *, invoice_id: str, workspace_id: str | None = None
) -> Any:
    """Duplicate an invoice (creates a new draft copy)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/duplicate")


async def delete_invoice(
    client: ClockifyClient, *, invoice_id: str, workspace_id: str | None = None
) -> Any:
    """Delete an invoice. IRREVERSIBLE — permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/invoices/{invoice_id}")


async def add_invoice_item(
    client: ClockifyClient,
    *,
    invoice_id: str,
    apply_taxes: str,
    description: str,
    item_type: str,
    quantity: int,
    unit_price: int,
    workspace_id: str | None = None,
) -> Any:
    """Add a line item to an invoice.

    All fields are required by the API, so the body is built directly (no drop_none).
    apply_taxes is TAX1/TAX2/TAX1TAX2/NONE. item_type is a free-text label (e.g.
    "Service"). quantity and unit_price are integers (unit_price in minor units).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = {
        "applyTaxes": apply_taxes,
        "description": description,
        "itemType": item_type,
        "quantity": quantity,
        "unitPrice": unit_price,
    }
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/items", json=body)


async def import_invoice_items(
    client: ClockifyClient,
    *,
    invoice_id: str,
    from_: str,
    to: str,
    import_expenses: bool,
    time_entry_group_type: str,
    workspace_id: str | None = None,
    project_ids: list[str] | None = None,
    project_filter_contains: str | None = None,
    project_filter_status: str | None = None,
    time_entry_primary_group_by: str | None = None,
    time_entry_secondary_group_by: str | None = None,
) -> Any:
    """Import time entries (and optionally expenses) into an invoice as items.

    from_/to are ISO-8601. time_entry_group_type is SINGLE_ITEM/GROUPED/DETAILED.
    project_filter_contains is CONTAINS/DOES_NOT_CONTAIN/CONTAINS_ONLY;
    project_filter_status is ACTIVE/ARCHIVED/ALL. The *_group_by options apply to
    GROUPED imports (PROJECT/USER/DATE etc.).
    """
    ws = resolve_workspace_id(client, workspace_id)
    project_filter = drop_none(
        {
            "contains": project_filter_contains,
            "ids": project_ids,
            "status": project_filter_status,
        }
    )
    body = drop_none(
        {
            "from": from_,
            "to": to,
            "importExpenses": import_expenses,
            "timeEntryGroupType": time_entry_group_type,
            "projectFilter": project_filter,
            "timeEntryPrimaryGroupBy": time_entry_primary_group_by,
            "timeEntrySecondaryGroupBy": time_entry_secondary_group_by,
        }
    )
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/items/import", json=body)


async def add_invoice_payment(
    client: ClockifyClient,
    *,
    invoice_id: str,
    workspace_id: str | None = None,
    amount: int | None = None,
    note: str | None = None,
    payment_date: str | None = None,
) -> Any:
    """Record a payment against an invoice (amount in minor units; payment_date ISO-8601)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"amount": amount, "note": note, "paymentDate": payment_date})
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/payments", json=body)


async def delete_invoice_payment(
    client: ClockifyClient,
    *,
    invoice_id: str,
    payment_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Delete a recorded invoice payment. IRREVERSIBLE."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(
        f"workspaces/{ws}/invoices/{invoice_id}/payments/{payment_id}"
    )


def register(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_invoices(
        workspace_id: _WorkspaceId = None,
        statuses: _Statuses = None,
        sort_column: _SortColumn = None,
        sort_order: _SortOrder = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List invoices on a workspace, optionally filtered by status.

        Read-only; results are paginated. Use this to discover invoice ids
        before fetching, updating, or recording payments; pass statuses to
        narrow by UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE and
        sort_column/sort_order to order them. When you already know an
        invoice's id, use get_invoice instead. Invoices are a paid Clockify
        feature. Returns a list of invoice objects.
        """
        return await list_invoices_fn(
            client,
            workspace_id=workspace_id,
            statuses=statuses,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_invoice(
        invoice_id: _InvoiceId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Get a single invoice's full detail by its id.

        Read-only. Use list_invoices first to look up the id when you only
        know its number or client. Unlike get_invoice_payments, this returns
        the invoice header and line items, not its payment records. Returns
        one invoice object.
        """
        return await get_invoice_fn(client, invoice_id=invoice_id, workspace_id=workspace_id)

    @mcp.tool()
    async def get_invoice_payments(
        invoice_id: _InvoiceId,
        workspace_id: _WorkspaceId = None,
        page: _Page = None,
        page_size: _PageSize = None,
    ) -> Any:
        """List the payments recorded against one invoice.

        Read-only; results are paginated. Unlike get_invoice (which returns
        the invoice itself), this returns only its payment records, including
        their payment ids for use with delete_invoice_payment. Returns a list
        of payment objects.
        """
        return await get_invoice_payments_fn(
            client,
            invoice_id=invoice_id,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: FastMCP, client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_invoice(
        client_id: _ClientId,
        currency: _Currency,
        issued_date: _IssuedDate,
        due_date: _DueDate,
        number: _Number,
        workspace_id: _WorkspaceId = None,
        time_view_mode: _TimeViewMode = None,
    ) -> Any:
        """Create a new, empty invoice on a workspace.

        Write operation. The create body has no line items — the invoice
        starts empty, then add items separately with add_invoice_item or
        import_invoice_items. Required: client_id, currency, issued_date,
        due_date, number (dates ISO-8601). time_view_mode is
        TIME_SENSITIVE_VIEW or AGGREGATED_TIME_VIEW. Returns the created
        invoice including its newly assigned id.
        """
        return await create_invoice_fn(
            client,
            client_id=client_id,
            currency=currency,
            issued_date=issued_date,
            due_date=due_date,
            number=number,
            workspace_id=workspace_id,
            time_view_mode=time_view_mode,
        )

    @mcp.tool()
    async def update_invoice(
        invoice_id: _InvoiceId,
        currency: _Currency,
        number: _Number,
        issued_date: _IssuedDate,
        due_date: _DueDate,
        discount_percent: _DiscountPercent,
        tax_percent: _TaxPercent,
        tax2_percent: _Tax2Percent,
        workspace_id: _WorkspaceId = None,
        client_id: _UpdateClientId = None,
        company_id: _CompanyId = None,
        note: _Note = None,
        subject: _Subject = None,
    ) -> Any:
        """Replace an invoice's header fields (full update, not a status change).

        Write operation; this is a full replace, so all required fields must
        be supplied: currency, number, issued_date, due_date, discount_percent,
        tax_percent, tax2_percent. To change only the workflow state, use
        change_invoice_status instead; to add line items, use add_invoice_item
        or import_invoice_items. Returns the updated invoice.
        """
        return await update_invoice_fn(
            client,
            invoice_id=invoice_id,
            currency=currency,
            number=number,
            issued_date=issued_date,
            due_date=due_date,
            discount_percent=discount_percent,
            tax_percent=tax_percent,
            tax2_percent=tax2_percent,
            workspace_id=workspace_id,
            client_id=client_id,
            company_id=company_id,
            note=note,
            subject=subject,
        )

    @mcp.tool()
    async def change_invoice_status(
        invoice_id: _InvoiceId,
        invoice_status: _InvoiceStatus,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Change only an invoice's workflow status.

        Write operation via a dedicated status endpoint. invoice_status is one
        of UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE. Use this rather than
        update_invoice when the only thing you need to change is the state.
        """
        return await change_invoice_status_fn(
            client,
            invoice_id=invoice_id,
            invoice_status=invoice_status,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def duplicate_invoice(
        invoice_id: _InvoiceId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Duplicate an existing invoice into a new draft copy.

        Write operation; the source invoice is left untouched and a new draft
        copy is created. Use this to base a new invoice on an existing one
        rather than building it from scratch with create_invoice. Returns the
        newly created copy.
        """
        return await duplicate_invoice_fn(
            client, invoice_id=invoice_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def delete_invoice(
        invoice_id: _InvoiceId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Permanently delete an invoice from a workspace.

        Write operation and IRREVERSIBLE — the invoice is permanently removed.
        To void rather than delete it, use change_invoice_status(VOID) instead.
        """
        return await delete_invoice_fn(
            client, invoice_id=invoice_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def add_invoice_item(
        invoice_id: _InvoiceId,
        apply_taxes: _ApplyTaxes,
        description: _ItemDescription,
        item_type: _ItemType,
        quantity: _Quantity,
        unit_price: _UnitPrice,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Add one manually-specified line item to an invoice.

        Write operation. All fields are required by the API. apply_taxes is
        TAX1/TAX2/TAX1TAX2/NONE; item_type is a free-text label (e.g.
        "Service"); quantity and unit_price are integers (unit_price in minor
        units). Use this for a single ad-hoc line; to pull items from logged
        time entries and expenses instead, use import_invoice_items.
        """
        return await add_invoice_item_fn(
            client,
            invoice_id=invoice_id,
            apply_taxes=apply_taxes,
            description=description,
            item_type=item_type,
            quantity=quantity,
            unit_price=unit_price,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def import_invoice_items(
        invoice_id: _InvoiceId,
        from_: _From,
        to: _To,
        import_expenses: _ImportExpenses,
        time_entry_group_type: _TimeEntryGroupType,
        workspace_id: _WorkspaceId = None,
        project_ids: _ProjectIds = None,
        project_filter_contains: _ProjectFilterContains = None,
        project_filter_status: _ProjectFilterStatus = None,
        time_entry_primary_group_by: _PrimaryGroupBy = None,
        time_entry_secondary_group_by: _SecondaryGroupBy = None,
    ) -> Any:
        """Import logged time entries (and optionally expenses) into an invoice as items.

        Write operation. Unlike add_invoice_item (a single manual line), this
        pulls billable work from a date range. from_/to are ISO-8601;
        time_entry_group_type is SINGLE_ITEM/GROUPED/DETAILED;
        project_filter_contains is CONTAINS/DOES_NOT_CONTAIN/CONTAINS_ONLY;
        project_filter_status is ACTIVE/ARCHIVED/ALL; the *_group_by options
        (PROJECT/USER/DATE etc.) apply to GROUPED imports. Set import_expenses
        to also include expenses.
        """
        return await import_invoice_items_fn(
            client,
            invoice_id=invoice_id,
            from_=from_,
            to=to,
            import_expenses=import_expenses,
            time_entry_group_type=time_entry_group_type,
            workspace_id=workspace_id,
            project_ids=project_ids,
            project_filter_contains=project_filter_contains,
            project_filter_status=project_filter_status,
            time_entry_primary_group_by=time_entry_primary_group_by,
            time_entry_secondary_group_by=time_entry_secondary_group_by,
        )

    @mcp.tool()
    async def add_invoice_payment(
        invoice_id: _InvoiceId,
        workspace_id: _WorkspaceId = None,
        amount: _Amount = None,
        note: _PaymentNote = None,
        payment_date: _PaymentDate = None,
    ) -> Any:
        """Record a payment received against an invoice.

        Write operation; amount is in minor units and payment_date is
        ISO-8601. The created payment shows up in get_invoice_payments and can
        be removed with delete_invoice_payment. Returns the created payment.
        """
        return await add_invoice_payment_fn(
            client,
            invoice_id=invoice_id,
            workspace_id=workspace_id,
            amount=amount,
            note=note,
            payment_date=payment_date,
        )

    @mcp.tool()
    async def delete_invoice_payment(
        invoice_id: _InvoiceId,
        payment_id: _PaymentId,
        workspace_id: _WorkspaceId = None,
    ) -> Any:
        """Permanently remove one recorded payment from an invoice.

        Write operation and IRREVERSIBLE — the payment record is deleted. Get
        payment_id from get_invoice_payments. This deletes only the payment,
        not the invoice itself (use delete_invoice for that).
        """
        return await delete_invoice_payment_fn(
            client,
            invoice_id=invoice_id,
            payment_id=payment_id,
            workspace_id=workspace_id,
        )


list_invoices_fn = list_invoices
get_invoice_fn = get_invoice
get_invoice_payments_fn = get_invoice_payments
create_invoice_fn = create_invoice
update_invoice_fn = update_invoice
change_invoice_status_fn = change_invoice_status
duplicate_invoice_fn = duplicate_invoice
delete_invoice_fn = delete_invoice
add_invoice_item_fn = add_invoice_item
import_invoice_items_fn = import_invoice_items
add_invoice_payment_fn = add_invoice_payment
delete_invoice_payment_fn = delete_invoice_payment
