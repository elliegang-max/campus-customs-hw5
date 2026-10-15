"""Campus Customs back-office MCP server.

Every agent in this assignment reaches the shop through these tools — no agent
opens the database itself, and there is no second shop-tools layer that goes
round them.

The tools fall into three groups:

* **Reads** — `list_tickets`, `get_ticket`, `get_vendor_status`,
  `list_approvals`.
* **Writes an agent may do** — `propose_payment`, `record_draft_reply`,
  `resolve_ticket`. None of them moves money.
* **`pay`** — the only tool that moves money, and it refuses unless a human
  approval is already recorded for that exact payment and the balance can take
  it.

`approve_payment` is the human's tool. It is served here so that approving goes
through the same audited path as everything else, but it is filtered out of the
agents' toolset in `backend/toolset.py`: an agent cannot approve its own
proposal because it cannot see the tool.

Run it with:

    python -m mcp_server.server          # stdio transport
"""

from __future__ import annotations

from typing import Any

try:  # the standalone FastMCP package
    from fastmcp import FastMCP
except ModuleNotFoundError:  # the copy bundled with the official MCP SDK
    from mcp.server.fastmcp import FastMCP

from . import queries

mcp = FastMCP("campus-customs")


@mcp.tool()
def list_tickets(status: str | None = "open") -> dict[str, Any]:
    """List tickets on the board, newest last.

    Args:
        status: Only tickets with this status. Pass null for every ticket.

    Returns the shop's own date (`today`, from the desk) alongside the tickets,
    because every overdue judgement must be made against that date and not
    against the real-world clock.
    """
    return queries.list_tickets(status)


@mcp.tool()
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Read one ticket with everything it links to, resolved in one call.

    Args:
        ticket_id: The id of the ticket, as listed by `list_tickets`.

    A ticket reaches the rest of the shop through three nullable columns, and
    only the links it actually has are resolved:

    * `sku` + `size` -> the `pricing` row and the `inventory` rows for that SKU,
      plus `on_hand` and `short_by` for the size requested.
    * `lease_id` -> the lease, with `days_until_due` against the shop's date.
    * `invoice_id` -> the invoice, with `days_overdue` and the vendor behind it.

    Cash balances come back too, since no decision can exceed them. Raises if
    the ticket id is not on the board rather than guessing at one.
    """
    return queries.get_ticket(ticket_id)


@mcp.tool()
def get_vendor_status(vendor_id: int) -> dict[str, Any]:
    """Check whether a vendor will ship, and how long they take.

    Args:
        vendor_id: The id of the vendor, as named on an invoice.

    `lead_days` is read from the vendors table — never assumed. `can_ship` is
    false while the vendor has any open unpaid invoice, which is the house rule
    that blocks restocks, and `blocked_reason` names the invoices responsible.
    `earliest_ship_date_if_ordered_today` is the shop's date plus the vendor's
    lead days; it only applies once `can_ship` is true.
    """
    return queries.get_vendor_status(vendor_id)


@mcp.tool()
def propose_payment(
    kind: str,
    ref_id: int,
    amount: float,
    reason: str,
    requested_by: str,
    account: str = "checking",
) -> dict[str, Any]:
    """Propose a payment for a human to approve. This pays nothing.

    Args:
        kind: "invoice" or "rent".
        ref_id: The invoice id, or the lease id for rent.
        amount: What should be paid.
        reason: Why it should be paid, in one line. A human reads this.
        requested_by: Which agent is proposing it.
        account: The cash account to pay from. Defaults to checking.

    Returns the proposal with `cash_before` and `cash_after_if_paid` so the
    human can see what approving it would cost. The proposal sits at status
    "proposed" until a person decides; nothing is spent in the meantime.
    """
    return queries.propose_payment(kind, ref_id, amount, reason, requested_by, account)


@mcp.tool()
def list_approvals(status: str | None = None) -> dict[str, Any]:
    """Every payment proposal and where it stands.

    Args:
        status: Filter to "proposed", "approved", "declined", or "used".
            Pass null for all of them.

    Use this to check whether a payment has actually been approved before
    assuming it can go ahead.
    """
    return queries.list_approvals(status)


@mcp.tool()
def approve_payment(
    approval_id: int, approved_by: str, decision: str = "approved"
) -> dict[str, Any]:
    """**Human only.** Record a person's decision on a payment proposal.

    Args:
        approval_id: The proposal being decided.
        approved_by: The name of the person deciding. Not an agent.
        decision: "approved" or "declined".

    This tool is not in the agents' toolset — it exists for a person working
    the board through `scripts/approve.py`. A decision cannot be changed once
    recorded.
    """
    return queries.approve_payment(approval_id, approved_by, decision)


@mcp.tool()
def pay(kind: str, ref_id: int, account: str = "checking") -> dict[str, Any]:
    """Pay an invoice or rent. The only tool that moves money.

    Args:
        kind: "invoice" or "rent".
        ref_id: The invoice id, or the lease id for rent.
        account: The cash account to pay from. Defaults to checking.

    **It refuses** unless a human approval is already recorded for exactly this
    payment, and refuses again if that approval has already been spent — one
    approval buys one payment. **It also refuses** any payment that would take
    the account below zero.

    When it does pay, it writes all of it at once: the payment row, the new
    balance, the invoice marked paid (or the lease's next due date rolled on),
    and the approval marked used.
    """
    return queries.pay(kind, ref_id, account)


@mcp.tool()
def record_draft_reply(
    ticket_id: int, to_whom: str, subject: str, body: str, written_by: str
) -> dict[str, Any]:
    """Pin a draft reply to the board. Nothing is sent.

    Args:
        ticket_id: The ticket being answered.
        to_whom: The requester named on the ticket.
        subject: The subject line.
        body: The message.
        written_by: Which agent wrote it.

    No mail leaves this system. The draft is stored with `sent` false for a
    person to send, edit, or discard.
    """
    return queries.record_draft_reply(ticket_id, to_whom, subject, body, written_by)


@mcp.tool()
def resolve_ticket(ticket_id: int, resolution: str, resolved_by: str) -> dict[str, Any]:
    """Close a ticket, recording what was done.

    Args:
        ticket_id: The ticket to close.
        resolution: What was done, in one or two lines. Appended to the
            ticket's notes with the shop's date.
        resolved_by: Which agent is closing it.

    Only close a ticket when nothing further is needed from a human or a
    vendor. A ticket waiting on an approval is not resolved.
    """
    return queries.resolve_ticket(ticket_id, resolution, resolved_by)


if __name__ == "__main__":
    mcp.run()
