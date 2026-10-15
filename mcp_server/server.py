"""Campus Customs back-office MCP server.

Every agent in this assignment reaches the shop through these tools — no agent
opens the database itself. The tools below are read-only; tools that spend money
or resolve a ticket are added in later problems and carry their own approval
step.

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


if __name__ == "__main__":
    mcp.run()
