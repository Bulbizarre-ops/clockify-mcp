"""Invoices domain (read + write).

Endpoints under ``workspaces/{ws}/invoices`` on the regular host. Creating an
invoice yields an empty invoice (no line items in the create body); items are
added via add_invoice_item / import_invoice_items. Status changes go through a
dedicated PATCH. Invoices are a paid Clockify feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


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
        workspace_id: str | None = None,
        statuses: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List invoices (paginated)."""
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
        invoice_id: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Get a single invoice by id."""
        return await get_invoice_fn(client, invoice_id=invoice_id, workspace_id=workspace_id)

    @mcp.tool()
    async def get_invoice_payments(
        invoice_id: str,
        workspace_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List an invoice's payments (paginated)."""
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
        client_id: str,
        currency: str,
        issued_date: str,
        due_date: str,
        number: str,
        workspace_id: str | None = None,
        time_view_mode: str | None = None,
    ) -> Any:
        """Create an invoice (empty — add items separately)."""
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
        """Update an invoice (full replace)."""
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
        invoice_id: str,
        invoice_status: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Change an invoice's status: UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE."""
        return await change_invoice_status_fn(
            client,
            invoice_id=invoice_id,
            invoice_status=invoice_status,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def duplicate_invoice(
        invoice_id: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Duplicate an invoice (creates a new draft copy)."""
        return await duplicate_invoice_fn(
            client, invoice_id=invoice_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def delete_invoice(
        invoice_id: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Delete an invoice. IRREVERSIBLE — permanently removed."""
        return await delete_invoice_fn(
            client, invoice_id=invoice_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def add_invoice_item(
        invoice_id: str,
        apply_taxes: str,
        description: str,
        item_type: str,
        quantity: int,
        unit_price: int,
        workspace_id: str | None = None,
    ) -> Any:
        """Add a line item to an invoice.

        apply_taxes is TAX1/TAX2/TAX1TAX2/NONE. item_type is a free-text label (e.g.
        "Service"). quantity and unit_price are integers (unit_price in minor units).
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
        project_filter_status is ACTIVE/ARCHIVED/ALL.
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
        invoice_id: str,
        workspace_id: str | None = None,
        amount: int | None = None,
        note: str | None = None,
        payment_date: str | None = None,
    ) -> Any:
        """Record a payment against an invoice (amount in minor units; payment_date ISO-8601)."""
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
        invoice_id: str,
        payment_id: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Delete a recorded invoice payment. IRREVERSIBLE."""
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
