"""The reads behind the tools.

Every value returned here comes out of the database. Nothing is defaulted,
guessed, or filled in from the model's own knowledge: where a row is missing the
caller is told so explicitly. The only computed values are date arithmetic and
sums over rows that were read, and each one is named so it reads as derived
(`days_overdue`, `earliest_ship_date_if_ordered_today`, `short_by`).

"Today" is always `desk.date_today`, never the system clock.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .db import connect, one, rows


def _today(conn) -> str:
    """The shop's date. The desk table holds exactly one row."""
    desk = one(conn, "SELECT date_today FROM desk LIMIT 1")
    if desk is None:
        raise RuntimeError("the desk table is empty — no shop date to work from")
    return desk["date_today"]


def _days_between(start: str, end: str) -> int:
    """Whole days from `start` to `end`, both ISO dates from the database."""
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def list_tickets(status: str | None = "open") -> dict[str, Any]:
    with connect() as conn:
        today = _today(conn)
        if status is None:
            found = rows(conn, "SELECT * FROM tickets ORDER BY id")
        else:
            found = rows(
                conn, "SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,)
            )
        return {
            "today": today,
            "status_filter": status,
            "count": len(found),
            "tickets": found,
        }


def get_ticket(ticket_id: int) -> dict[str, Any]:
    with connect() as conn:
        today = _today(conn)
        ticket = one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            known = [r["id"] for r in rows(conn, "SELECT id FROM tickets ORDER BY id")]
            raise ValueError(f"no ticket with id {ticket_id}; tickets on the board: {known}")

        result: dict[str, Any] = {
            "today": today,
            "ticket": ticket,
            "cash_accounts": rows(conn, "SELECT * FROM cash_accounts ORDER BY name"),
        }

        # A ticket reaches the rest of the shop through sku/size, lease_id, and
        # invoice_id. Only the links this ticket actually has are resolved.
        sku, size = ticket["sku"], ticket["size"]
        if sku:
            result["pricing"] = one(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
            stock = rows(
                conn,
                # Smallest first, rather than alphabetically, so a reader does
                # not have to re-sort L / M / S / XL in their head.
                "SELECT * FROM inventory WHERE sku = ? "
                "ORDER BY CASE size WHEN 'S' THEN 1 WHEN 'M' THEN 2 WHEN 'L' THEN 3 "
                "WHEN 'XL' THEN 4 ELSE 5 END, size",
                (sku,),
            )
            result["stock_all_sizes"] = stock
            if size:
                match = next((r for r in stock if r["size"] == size), None)
                on_hand = match["qty"] if match else 0
                result["stock_requested_size"] = match
                result["on_hand"] = on_hand
                if ticket["qty"] is not None:
                    result["short_by"] = max(0, ticket["qty"] - on_hand)

        if ticket["lease_id"] is not None:
            lease = one(conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
            if lease is not None:
                lease["days_until_due"] = _days_between(today, lease["next_due"])
            result["lease"] = lease

        if ticket["invoice_id"] is not None:
            invoice = one(
                conn, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
            )
            if invoice is not None:
                overdue = _days_between(invoice["due_date"], today)
                invoice["days_overdue"] = max(0, overdue)
                invoice["vendor"] = one(
                    conn, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)
                )
            result["invoice"] = invoice

        return result


def get_vendor_status(vendor_id: int) -> dict[str, Any]:
    with connect() as conn:
        today = _today(conn)
        vendor = one(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            known = rows(conn, "SELECT id, name FROM vendors ORDER BY id")
            raise ValueError(f"no vendor with id {vendor_id}; vendors on file: {known}")

        open_invoices = rows(
            conn,
            "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
            (vendor_id,),
        )
        for inv in open_invoices:
            inv["days_overdue"] = max(0, _days_between(inv["due_date"], today))

        lead_days = vendor["lead_days"]
        ship_date = (date.fromisoformat(today) + timedelta(days=lead_days)).isoformat()

        return {
            "today": today,
            "vendor": vendor,
            "lead_days": lead_days,
            "open_invoices": open_invoices,
            "open_invoice_total": round(sum(i["amount"] for i in open_invoices), 2),
            # House rule: a vendor will not ship new product while they still
            # have an open unpaid invoice.
            "can_ship": not open_invoices,
            "blocked_reason": (
                None
                if not open_invoices
                else "vendor has open unpaid invoice(s): "
                + ", ".join(f"#{i['id']} ({i['amount']:.2f})" for i in open_invoices)
            ),
            "earliest_ship_date_if_ordered_today": ship_date,
        }
