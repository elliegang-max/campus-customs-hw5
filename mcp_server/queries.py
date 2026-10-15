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


# --- Writes ----------------------------------------------------------------
#
# The guardrails live here, not in a prompt:
#
#   * `pay` refuses unless a human-recorded approval exists for that exact
#     payment, and refuses again if the approval has already been spent.
#   * `pay` refuses any payment that would take a cash account below zero.
#   * Only `approve_payment` can set a row to 'approved', and the agents never
#     see that tool — it is filtered out of their toolset (see backend/toolset).
#
# A payment is three writes plus two bookkeeping ones. They all happen in a
# single connection, so a half-finished payment cannot leave the books
# disagreeing with each other.


def _next_month(iso_date: str) -> str:
    """The same day one month on, clamped to the end of a short month."""
    d = date.fromisoformat(iso_date)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    last_day = (date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day)).isoformat()


def propose_payment(
    kind: str,
    ref_id: int,
    amount: float,
    reason: str,
    requested_by: str,
    account: str = "checking",
) -> dict[str, Any]:
    """Record a payment an agent wants made. This does not pay anything."""
    if kind not in ("invoice", "rent"):
        raise ValueError(f"kind must be 'invoice' or 'rent', not {kind!r}")

    with connect(readonly=False) as conn:
        today = _today(conn)

        if kind == "invoice":
            target = one(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if target is None:
                raise ValueError(f"no invoice with id {ref_id}")
            if target["status"] != "open":
                raise ValueError(f"invoice {ref_id} is already {target['status']}")
        else:
            target = one(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if target is None:
                raise ValueError(f"no lease with id {ref_id}")

        balance = one(conn, "SELECT * FROM cash_accounts WHERE name = ?", (account,))
        if balance is None:
            raise ValueError(f"no cash account named {account!r}")

        # One live proposal per obligation. Asking twice returns the first one
        # rather than stacking duplicates: a human looking at several identical
        # approvals for the same invoice cannot tell which is the real decision,
        # and approving two of them is two payments.
        #
        # "Live" means proposed *or already approved but not yet spent* — an
        # earlier version only looked for a pending one, so once a human signed
        # the first proposal a second could still be created behind it, and the
        # board showed a payment that could never go through.
        pending = one(
            conn,
            "SELECT * FROM approvals WHERE kind = ? AND ref_id = ? AND account = ? "
            "AND status IN ('proposed', 'approved') ORDER BY id LIMIT 1",
            (kind, ref_id, account),
        )
        if pending is not None:
            return {
                "approval_id": pending["id"],
                "status": pending["status"],
                "already_proposed": True,
                "kind": kind,
                "ref_id": ref_id,
                "amount": pending["amount"],
                "account": account,
                "proposed_by": pending["requested_by"],
                "cash_before": balance["balance"],
                "cash_after_if_paid": round(balance["balance"] - pending["amount"], 2),
                "awaiting": "this payment is already waiting on a human decision",
            }

        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, amount, account, reason, "
            "requested_by, requested_at, status) VALUES (?,?,?,?,?,?,?, 'proposed')",
            (kind, ref_id, amount, account, reason, requested_by, today),
        )
        return {
            "approval_id": cur.lastrowid,
            "status": "proposed",
            "already_proposed": False,
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "account": account,
            "cash_before": balance["balance"],
            "cash_after_if_paid": round(balance["balance"] - amount, 2),
            "awaiting": "a human must approve this before it can be paid",
        }


def list_approvals(status: str | None = None) -> dict[str, Any]:
    """Every payment proposal and where it stands."""
    with connect() as conn:
        today = _today(conn)
        if status is None:
            found = rows(conn, "SELECT * FROM approvals ORDER BY id")
        else:
            found = rows(
                conn, "SELECT * FROM approvals WHERE status = ? ORDER BY id", (status,)
            )
        return {"today": today, "count": len(found), "approvals": found}


def approve_payment(
    approval_id: int, approved_by: str, decision: str = "approved"
) -> dict[str, Any]:
    """Record a human's decision on a proposal. Not available to the agents."""
    if decision not in ("approved", "declined"):
        raise ValueError("decision must be 'approved' or 'declined'")
    if not approved_by.strip():
        raise ValueError("approved_by must name the person deciding")

    with connect(readonly=False) as conn:
        today = _today(conn)
        approval = one(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if approval is None:
            raise ValueError(f"no approval with id {approval_id}")
        if approval["status"] != "proposed":
            raise ValueError(
                f"approval {approval_id} is already {approval['status']} — "
                "a decision cannot be changed"
            )

        conn.execute(
            "UPDATE approvals SET status = ?, approved_by = ?, decided_at = ? WHERE id = ?",
            (decision, approved_by.strip(), today, approval_id),
        )
        return {
            **approval,
            "status": decision,
            "approved_by": approved_by.strip(),
            "decided_at": today,
        }


def pay(kind: str, ref_id: int, account: str = "checking") -> dict[str, Any]:
    """Pay an approved invoice or rent. Refuses without approval or funds."""
    with connect(readonly=False) as conn:
        today = _today(conn)

        approval = one(
            conn,
            "SELECT * FROM approvals WHERE kind = ? AND ref_id = ? AND account = ? "
            "AND status = 'approved' ORDER BY id LIMIT 1",
            (kind, ref_id, account),
        )
        if approval is None:
            proposed = one(
                conn,
                "SELECT id FROM approvals WHERE kind = ? AND ref_id = ? AND status = 'proposed'",
                (kind, ref_id),
            )
            hint = (
                f" Proposal {proposed['id']} is still awaiting a human decision."
                if proposed
                else " Propose it first, then a human must approve it."
            )
            raise ValueError(
                f"refused: no recorded human approval for {kind} {ref_id} from {account}.{hint}"
            )

        # One approval buys one payment, but two approvals for the same
        # obligation must not buy two. Check the obligation itself, not just
        # the approval.
        if kind == "invoice":
            invoice = one(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if invoice is None:
                raise ValueError(f"no invoice with id {ref_id}")
            if invoice["status"] != "open":
                raise ValueError(
                    f"refused: invoice {ref_id} is already {invoice['status']} — "
                    "it cannot be paid twice"
                )
        else:
            already = one(
                conn,
                "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ? AND paid_at = ?",
                (ref_id, today),
            )
            if already is not None:
                raise ValueError(
                    f"refused: rent for lease {ref_id} was already paid today "
                    f"(payment {already['id']}, {already['amount']:.2f})"
                )

        amount = approval["amount"]
        cash = one(conn, "SELECT * FROM cash_accounts WHERE name = ?", (account,))
        if cash is None:
            raise ValueError(f"no cash account named {account!r}")

        remaining = round(cash["balance"] - amount, 2)
        if remaining < 0:
            raise ValueError(
                f"refused: paying {amount:.2f} from {account} would leave "
                f"{remaining:.2f}. Cash accounts may not go below zero."
            )

        # The five writes of a payment, in one transaction.
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?,?,?,?,?,?)",
            (kind, ref_id, amount, account, today, approval["approved_by"]),
        )
        payment_id = cur.lastrowid

        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (remaining, today, account),
        )
        conn.execute(
            "UPDATE approvals SET status = 'used', payment_id = ? WHERE id = ?",
            (payment_id, approval["id"]),
        )

        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            settled = f"invoice {ref_id} marked paid"
        else:
            lease = one(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            rolled = _next_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (rolled, ref_id))
            settled = f"lease {ref_id} next_due rolled to {rolled}"

        return {
            "paid": True,
            "payment_id": payment_id,
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "account": account,
            "paid_at": today,
            "approved_by": approval["approved_by"],
            "approval_id": approval["id"],
            "cash_before": cash["balance"],
            "cash_after": remaining,
            "settled": settled,
        }


def record_draft_reply(
    ticket_id: int, to_whom: str, subject: str, body: str, written_by: str
) -> dict[str, Any]:
    """Pin a draft reply to the board. Nothing here sends anything."""
    with connect(readonly=False) as conn:
        today = _today(conn)
        if one(conn, "SELECT id FROM tickets WHERE id = ?", (ticket_id,)) is None:
            raise ValueError(f"no ticket with id {ticket_id}")

        # One live draft per ticket. Re-recording replaces the unsent draft
        # rather than adding a second one: two drafts of the same reply on the
        # board is worse than none, because a person has to work out which is
        # the real one.
        existing = one(
            conn,
            "SELECT id FROM drafts WHERE ticket_id = ? AND sent = 0 ORDER BY id LIMIT 1",
            (ticket_id,),
        )
        if existing:
            conn.execute(
                "UPDATE drafts SET to_whom=?, subject=?, body=?, written_by=?, "
                "written_at=? WHERE id=?",
                (to_whom, subject, body, written_by, today, existing["id"]),
            )
            draft_id, replaced = existing["id"], True
        else:
            cur = conn.execute(
                "INSERT INTO drafts (ticket_id, to_whom, subject, body, written_by, "
                "written_at, sent) VALUES (?,?,?,?,?,?, 0)",
                (ticket_id, to_whom, subject, body, written_by, today),
            )
            draft_id, replaced = cur.lastrowid, False

        return {
            "draft_id": draft_id,
            "ticket_id": ticket_id,
            "to": to_whom,
            "written_at": today,
            "sent": False,
            "replaced_existing_draft": replaced,
            "note": "the draft stays on the board; a person sends it or does not",
        }


def resolve_ticket(ticket_id: int, resolution: str, resolved_by: str) -> dict[str, Any]:
    """Close a ticket, recording what was done in its notes."""
    with connect(readonly=False) as conn:
        today = _today(conn)
        ticket = one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            raise ValueError(f"no ticket with id {ticket_id}")
        if ticket["status"] != "open":
            raise ValueError(f"ticket {ticket_id} is already {ticket['status']}")
        if not resolution.strip():
            raise ValueError("resolution must say what was done")

        note = f"{ticket['notes'] or ''}\n[{today}, {resolved_by}] {resolution.strip()}"
        conn.execute(
            "UPDATE tickets SET status = 'resolved', notes = ? WHERE id = ?",
            (note.strip(), ticket_id),
        )
        return {
            "ticket_id": ticket_id,
            "status": "resolved",
            "resolution": resolution.strip(),
            "resolved_by": resolved_by,
            "resolved_at": today,
        }
