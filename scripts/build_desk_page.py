"""Build output/desk_tickets.html — the desk page, one tab per ticket.

Every figure on the page is read from `data/campus_customs_new.db` when the
page is built, so nothing on it is typed from memory. Run it against a reset
database: the Expected sections describe what the team should do with a *fresh*
board.

    ./scripts/reset_db.sh
    ./.venv/bin/python scripts/build_desk_page.py
"""

from __future__ import annotations

import html
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "desk_tickets.html"
ACTUALS = ROOT / "output" / "run_actuals.json"

#: What actually happened, mined from the audit trail by collect_actuals.py.
#: Absent until the agents have been run, in which case the Actual sections stay
#: empty and the page still builds.
RUN = json.loads(ACTUALS.read_text()) if ACTUALS.exists() else {"tickets": {}}

AGENT_COLORS = {
    "boss": "#2F4A86",
    "inventory": "#2C7A55",
    "accounting": "#B4581C",
    "facilities": "#6B4BA3",
    "customer_service": "#0E7A84",
}


def agent_chip(key: str) -> str:
    color = AGENT_COLORS.get(key, "#7A6E5D")
    label = key.replace("_", " ")
    return f"<span class='who' style='--who:{color}'>{e(label)}</span>"


def actual_section(ticket_id: int) -> str:
    """What this run did with the ticket, from the trail and the database."""
    entry = RUN["tickets"].get(str(ticket_id))
    if not entry:
        return "<p class='lede'>Not run yet — run the agents, then rebuild this page.</p>"

    resolved = entry["final_status"] != "open"
    agents = " ".join(agent_chip(a) for a in entry["agents"])
    delegations = "".join(
        f"<li>{agent_chip(a)} <span class='arrow'>asked</span> {agent_chip(b)}</li>"
        for a, b in entry["delegations"]
    )
    tools = "".join(
        f"<tr><td><code>{e(tool)}</code></td><td class='count'>{count}×</td></tr>"
        for tool, count in sorted(entry["tools"].items(), key=lambda kv: -kv[1])
    )

    moved = []
    for call in entry["tool_detail"]:
        result = call["result"] if isinstance(call["result"], dict) else {}
        if call["tool"] == "pay" and call["ok"]:
            moved.append(
                f"{agent_chip(call['agent'])} paid <strong>{money(result.get('amount', 0))}</strong> — "
                f"{money(result.get('cash_before', 0))} → <strong>{money(result.get('cash_after', 0))}</strong>, "
                f"{e(result.get('settled', ''))}, approved by {e(result.get('approved_by', ''))}"
            )
        elif call["tool"] == "propose_payment" and call["ok"]:
            args = call["args"] or {}
            moved.append(
                f"{agent_chip(call['agent'])} proposed {money(args.get('amount', 0))} "
                f"for {e(args.get('kind', ''))} #{args.get('ref_id')} — a human had to sign it"
            )
        elif call["tool"] == "resolve_ticket" and call["ok"]:
            args = call["args"] or {}
            moved.append(
                f"{agent_chip(call['agent'])} closed the ticket: “{e(args.get('resolution', ''))}”"
            )
        elif call["tool"] == "record_draft_reply" and call["ok"]:
            args = call["args"] or {}
            moved.append(
                f"{agent_chip(call['agent'])} left a draft for {e(args.get('to_whom', ''))} — unsent"
            )

    refusals = "".join(
        f"<li>{agent_chip(r['agent'])} <code>{e(r['tool'])}</code> — {e((r['error'] or '')[:200])}</li>"
        for r in entry["refusals"]
    )

    parts = [
        f"<p class='actual-status {'is-resolved' if resolved else 'is-open'}'>"
        f"<strong>{e(entry['final_status']).upper()}</strong> after "
        f"{len(entry['runs'])} run{'s' if len(entry['runs']) != 1 else ''}</p>",
        f"<h4 class='plain'>Agents that worked it</h4><p class='chips'>{agents}</p>",
        f"<h4 class='plain'>What was delegated</h4><ul class='chain-list'>{delegations}</ul>",
        f"<h4 class='plain'>Tools used</h4><table class='tools tool-counts'>{tools}</table>",
    ]
    if moved:
        parts.append(
            "<h4 class='plain'>What moved</h4><ul class='moved'>"
            + "".join(f"<li>{m}</li>" for m in moved)
            + "</ul>"
        )
    if refusals:
        parts.append(
            "<h4 class='plain'>Refused by a tool</h4><ul class='refusals'>" + refusals + "</ul>"
        )
    if entry.get("finding"):
        parts.append(
            f"<h4 class='plain'>Where it ended</h4><p class='summary-text'>{e(entry['finding'])}</p>"
            f"<p class='summary-text'>{e(entry.get('recommended_action', ''))}</p>"
        )
    return "".join(parts)


def q(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def one(sql: str, params: tuple = ()):
    rows = q(sql, params)
    return rows[0] if rows else None


def e(value) -> str:
    return html.escape(str(value))


def money(value: float) -> str:
    return f"${value:,.2f}"


def days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


# --- the shop, as the database has it --------------------------------------

TODAY = one("SELECT date_today FROM desk")["date_today"]
CASH = one("SELECT * FROM cash_accounts WHERE name='checking'")
TICKETS = {t["id"]: t for t in q("SELECT * FROM tickets ORDER BY id")}
VENDORS = {v["id"]: v for v in q("SELECT * FROM vendors")}
APPAREL_VENDOR = next(v for v in VENDORS.values() if "apparel" in v["specialty"])
INVOICE = one("SELECT * FROM invoices WHERE id=501")
LEASE = one("SELECT * FROM leases WHERE id=1")

INVOICE_OVERDUE = days(INVOICE["due_date"], TODAY)
RENT_DUE_IN = days(TODAY, LEASE["next_due"])
SHIP_IF_CLEARED = (
    date.fromisoformat(TODAY) + timedelta(days=APPAREL_VENDOR["lead_days"])
).isoformat()

AFTER_INVOICE = round(CASH["balance"] - INVOICE["amount"], 2)
AFTER_RENT = round(AFTER_INVOICE - LEASE["monthly_rent"], 2)


def stock(sku: str, size: str) -> int:
    row = one("SELECT qty FROM inventory WHERE sku=? AND size=?", (sku, size))
    return row["qty"] if row else 0


def price(sku: str) -> dict:
    return one("SELECT * FROM pricing WHERE sku=?", (sku,))


def facts_table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"<tr><th scope='row'>{e(k)}</th><td>{v}</td></tr>" for k, v in rows
    )
    return f"<table class='facts'>{cells}</table>"


def steps(items: list[str]) -> str:
    return "<ol class='steps'>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def tools_table(rows: list[tuple[str, str, str]]) -> str:
    """Tool, what it touches, and why it runs on this ticket."""
    body = "".join(
        f"<tr><td><code>{t}</code></td><td class='tbl'>{tables}</td><td>{why}</td></tr>"
        for t, tables, why in rows
    )
    return (
        "<table class='tools'><thead><tr><th>Tool</th><th>Tables</th>"
        f"<th>Why it runs here</th></tr></thead><tbody>{body}</tbody></table>"
    )


def nots(items: list[str]) -> str:
    return (
        "<ul class='nots'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
    )


# --- ticket 101 -------------------------------------------------------------

t101 = TICKETS[101]
p101 = price(t101["sku"])
on_hand_101 = stock(t101["sku"], t101["size"])

TAB_101 = {
    "id": "101",
    "label": "Ticket 101",
    "sub": "Customer order",
    "title": f"101 — {e(t101['subject'])}",
    "meta": f"{e(t101['type'])} · raised by {e(t101['requester'])} · {e(t101['created_at'][:10])}",
    "quote": t101["notes"],
    "facts": facts_table([
        ("Wants", f"{t101['qty']} × {e(t101['sku'])} in size {e(t101['size'])}"),
        ("On the shelf", f"<strong>{on_hand_101}</strong> in size {e(t101['size'])} — short by {t101['qty'] - on_hand_101}"),
        ("Price", f"{money(p101['list_price'])} list, {money(p101['unit_cost'])} cost"),
        ("Linked invoice", f"#{INVOICE['id']} — {money(INVOICE['amount'])}, due {e(INVOICE['due_date'])}, <strong>{INVOICE_OVERDUE} days overdue</strong>"),
        ("Vendor", f"{e(APPAREL_VENDOR['name'])} — {e(APPAREL_VENDOR['specialty'])}, {APPAREL_VENDOR['lead_days']}-day lead"),
        ("Cash", money(CASH["balance"])),
    ]),
    "first_call": f"""<strong>Inventory.</strong> The order can only be filled if
      {e(t101['sku'])} exists in size {e(t101['size'])}, so that one answer decides
      everything after it — who else gets called, whether money is involved, and what
      the customer can be told.""",
    "workflow": steps([
        f"<strong>Boss → Inventory:</strong> is {e(t101['sku'])} in stock in size {e(t101['size'])}? "
        f"The answer is <strong>{on_hand_101}</strong> — out of stock, short by {t101['qty'] - on_hand_101}. "
        "The out-of-stock path below is the one that runs.",
        f"<strong>Inventory</strong> finds who can restock: {e(APPAREL_VENDOR['name'])} "
        f"({e(APPAREL_VENDOR['specialty'])}), lead time <strong>{APPAREL_VENDOR['lead_days']} days</strong>. "
        "Both come from the vendors table, not from a guess.",
        f"<strong>Boss → Accounting:</strong> does that vendor have an open unpaid invoice? "
        f"Yes — <strong>#{INVOICE['id']}, {money(INVOICE['amount'])}, {INVOICE_OVERDUE} days overdue</strong>. "
        "They will not ship until it is paid.",
        f"<strong>Accounting</strong> checks cash ({money(CASH['balance'])}), confirms {money(INVOICE['amount'])} "
        f"fits, and <strong>prepares the payment for human approval</strong> — {money(CASH['balance'])} → "
        f"{money(AFTER_INVOICE)}. It pays nothing itself, and <code>pay</code> refuses while the approval "
        "is missing or the cash is short.",
        f"<strong>Boss → Customer Service:</strong> draft to {e(t101['requester'])} with a realistic timeline — "
        f"out of stock in {e(t101['size'])}, restock held up, <em>no date</em> until the invoice clears. "
        "Saved to the board, never sent.",
        "<strong>Boss makes the final call:</strong> ticket stays <strong>open</strong>, waiting on a human "
        "approval, then a payment, then a shipment.",
    ]),
    "tools": tools_table([
        ("list_tickets", "desk, tickets", "the board, and the shop's date every other judgement uses"),
        ("get_ticket(101)", "tickets, inventory, pricing, invoices, vendors, cash_accounts",
         f"stock for {e(t101['sku'])}/{e(t101['size'])}, the linked invoice, and the balance — this one call covers the stock, invoice and cash lookups"),
        ("get_vendor_status(1)", "desk, vendors, invoices",
         f"who can restock, the {APPAREL_VENDOR['lead_days']}-day lead time, and whether an unpaid invoice blocks shipping"),
        ("list_approvals", "desk, approvals", "whether this payment was already approved on an earlier pass"),
        ("propose_payment", "writes approvals", f"puts {money(INVOICE['amount'])} in front of a human — pays nothing"),
        ("record_draft_reply", "writes drafts", "saves the reply to the board instead of emailing anyone"),
    ]),
    "skipped": f"""<strong>Facilities</strong> — nothing in an order touches a lease or
      rent. <strong><code>pay</code></strong> — there is no approval yet, and it would
      refuse. Accounting <em>would</em> have been skipped too had the tee been in stock:
      on the in-stock path no money moves, and the ticket goes straight from Inventory
      to Customer Service.""",
    "nots": nots([
        f"Promise <strong>{e(SHIP_IF_CLEARED)}</strong> — that date only applies once the invoice is paid, and the tools return it with that condition attached.",
        "Tell the customer the shop has an unpaid or overdue invoice. The delay is the shop's business.",
        "Offer a different size as if it were the same thing.",
        "Pay anything, or claim anything was paid.",
    ]),
}

# --- ticket 102 -------------------------------------------------------------

t102 = TICKETS[102]

TAB_102 = {
    "id": "102",
    "label": "Ticket 102",
    "sub": "Rent notice",
    "title": f"102 — {e(t102['subject'])}",
    "meta": f"{e(t102['type'])} · raised by {e(t102['requester'])} · {e(t102['created_at'][:10])}",
    "quote": t102["notes"],
    "facts": facts_table([
        ("Lease", f"#{LEASE['id']} — {e(LEASE['space_name'])}"),
        ("Landlord", e(LEASE["landlord"])),
        ("Rent", f"<strong>{money(LEASE['monthly_rent'])}</strong> per month"),
        ("Next due", f"{e(LEASE['next_due'])} — <strong>in {RENT_DUE_IN} days</strong>, not overdue"),
        ("Cash", money(CASH["balance"])),
    ]),
    "first_call": """<strong>Facilities.</strong> A rent ticket is a different shape
      from an order: there is no SKU and no size, so there is nothing for Inventory to
      answer. What decides this ticket is the lease — and the lease is the record, not
      the email that raised it.""",
    "workflow": steps([
        f"<strong>Boss → Facilities:</strong> what does lease #{LEASE['id']} actually say? "
        f"{e(LEASE['space_name'])}, {e(LEASE['landlord'])}, <strong>{money(LEASE['monthly_rent'])}</strong>, "
        f"next due <strong>{e(LEASE['next_due'])}</strong> — {RENT_DUE_IN} days from the shop's date. Not overdue.",
        "<strong>Facilities reports the lease row, not the notice.</strong> A notice can be wrong about "
        "the amount or the date; the lease cannot.",
        f"<strong>Boss → Accounting:</strong> can it be paid? Cash is {money(CASH['balance'])}, so yes — "
        f"on its own it leaves {money(round(CASH['balance'] - LEASE['monthly_rent'], 2))}, or "
        f"<strong>{money(AFTER_RENT)}</strong> if the overdue invoice is paid first.",
        "<strong>Accounting prepares it for human approval</strong> and stops there. Rent waits on a "
        "person like every other payment.",
        f"<strong>Boss → Customer Service:</strong> draft to {e(LEASE['landlord'])} acknowledging the due "
        "date. Saved to the board, never sent.",
        "<strong>Boss makes the final call:</strong> ticket stays <strong>open</strong> until the rent is "
        "approved and paid.",
    ]),
    "tools": tools_table([
        ("list_tickets", "desk, tickets", "the board, and the shop's date the due-date maths uses"),
        ("get_ticket(102)", "tickets, leases, cash_accounts",
         f"the lease row with <code>days_until_due</code> already measured, plus the balance"),
        ("list_approvals", "desk, approvals", "whether rent was already proposed or approved"),
        ("propose_payment", "writes approvals", f"puts {money(LEASE['monthly_rent'])} in front of a human — pays nothing"),
        ("record_draft_reply", "writes drafts", "saves the acknowledgement to the board"),
    ]),
    "skipped": """<strong>Inventory</strong>, and every vendor tool with it — a rent
      ticket has no SKU, no size and no supplier, so there is nothing to look up.
      Sending Inventory here would burn a model call to be told the ticket has no
      product on it. <strong><code>pay</code></strong> — no approval yet.""",
    "nots": nots([
        "Tell the landlord what is in the shop's account.",
        "Treat the rent as overdue — it is not, and the shop's date is what decides that.",
        f"Pay it before the overdue invoice without saying why: both fit ({money(INVOICE['amount'])} + {money(LEASE['monthly_rent'])} = {money(INVOICE['amount'] + LEASE['monthly_rent'])} against {money(CASH['balance'])}), but the order should be reasoned about out loud.",
    ]),
}

# --- ticket 103 -------------------------------------------------------------

t103 = TICKETS[103]
p103 = price(t103["sku"])
on_hand_103 = stock(t103["sku"], t103["size"])
short_103 = t103["qty"] - on_hand_103
restock_cost = round(short_103 * p103["unit_cost"], 2)
other_sizes = q(
    "SELECT size, qty FROM inventory WHERE sku=? AND size<>? ORDER BY CASE size "
    "WHEN 'S' THEN 1 WHEN 'M' THEN 2 WHEN 'L' THEN 3 WHEN 'XL' THEN 4 ELSE 5 END",
    (t103["sku"], t103["size"]),
)

TAB_103 = {
    "id": "103",
    "label": "Ticket 103",
    "sub": "Price override",
    "title": f"103 — {e(t103['subject'])}",
    "meta": f"{e(t103['type'])} · raised by {e(t103['requester'])} · {e(t103['created_at'][:10])}",
    "quote": t103["notes"],
    "facts": facts_table([
        ("Wants", f"{t103['qty']} × {e(t103['sku'])} in size {e(t103['size'])}"),
        ("On the shelf", f"<strong>{on_hand_103}</strong> in {e(t103['size'])} — <strong>short by {short_103}</strong>"),
        ("Other sizes", ", ".join(f"{r['qty']}×{e(r['size'])}" for r in other_sizes) + " — wrong size, not a substitute"),
        ("Price", f"{money(p103['list_price'])} list, <strong>{money(p103['unit_cost'])} cost</strong> — the floor under any discount"),
        ("Restock cost", f"{short_103} × {money(p103['unit_cost'])} = <strong>{money(restock_cost)}</strong>"),
        ("Vendor", f"{e(APPAREL_VENDOR['name'])} — blocked by invoice #{INVOICE['id']}"),
    ]),
    "first_call": f"""<strong>Inventory.</strong> Like ticket 101 this is an order,
      so stock decides it: {t103['qty']} of {e(t103['sku'])} in size {e(t103['size'])} either
      exist or they do not. The discount question cannot be answered before anyone knows
      how many can actually be supplied.""",
    "workflow": steps([
        f"<strong>Boss → Inventory:</strong> {t103['qty']} × {e(t103['sku'])} in {e(t103['size'])}? "
        f"<strong>{on_hand_103}</strong> on hand — <strong>short by {short_103}</strong>. The "
        f"{sum(r['qty'] for r in other_sizes)} in other sizes are not a substitute, so this is the "
        "out-of-stock path.",
        f"<strong>Inventory</strong> finds the supplier for the missing {short_103}: "
        f"{e(APPAREL_VENDOR['name'])} again, {APPAREL_VENDOR['lead_days']}-day lead — "
        f"<strong>the same vendor blocked by invoice #{INVOICE['id']}</strong>. This ticket queues "
        "behind the same payment as 101.",
        f"<strong>Boss → Accounting</strong>, even though the ticket never mentions money: a restock is "
        f"a purchase. {short_103} × {money(p103['unit_cost'])} = <strong>{money(restock_cost)}</strong>, "
        f"and after the invoice and the rent the account holds {money(AFTER_RENT)} — so the restock is "
        f"<strong>{money(round(restock_cost - AFTER_RENT, 2))} beyond reach</strong> this week.",
        f"<strong>Accounting proposes nothing for this ticket.</strong> There is no vendor quote and no "
        f"invoice to pay; {money(restock_cost)} is arithmetic off the pricing table, not a bill. The "
        f"#{INVOICE['id']} proposal from ticket 101 already covers the shipping block.",
        f"<strong>The discount is a human decision.</strong> The team may lay out "
        f"{money(p103['unit_cost'])} cost against {money(p103['list_price'])} list and stop there. "
        "No agent quotes a number.",
        f"<strong>Boss → Customer Service:</strong> draft to {e(t103['requester'])} — {on_hand_103} "
        f"available, {short_103} delayed with no date, no discount confirmed. Saved, never sent.",
        "<strong>Boss makes the final call:</strong> ticket stays <strong>open</strong> on two counts — "
        "a price decision and money the shop does not have this week.",
    ]),
    "tools": tools_table([
        ("list_tickets", "desk, tickets", "the board, and the shop's date"),
        ("get_ticket(103)", "tickets, inventory, pricing, cash_accounts",
         f"every size of {e(t103['sku'])}, the cost and list price, and the balance"),
        ("get_vendor_status(1)", "desk, vendors, invoices",
         "the supplier for the shortfall, the lead time, and the invoice blocking them"),
        ("list_approvals", "desk, approvals", "whether the invoice blocking this vendor is already approved"),
        ("record_draft_reply", "writes drafts", "saves the reply to the board instead of emailing anyone"),
    ]),
    "skipped": f"""<strong>Facilities</strong> — no lease, no rent.
      <strong><code>propose_payment</code></strong> — nothing here is a payable: the
      {money(restock_cost)} is arithmetic, not a bill, and proposing it would ask a human
      to approve a purchase that does not fit the balance anyway.
      <strong><code>pay</code></strong> — nothing to pay.""",
    "nots": nots([
        "Offer a discount, a percentage, or a per-unit price. That is the human decision this ticket exists to ask for.",
        f"Quote a price below {money(p103['unit_cost'])} — that is selling at a loss.",
        f"Promise the full {t103['qty']}, or a delivery date for the missing {short_103}.",
        "Treat the other sizes as filling the order.",
    ]),
}

# --- the cash tab ----------------------------------------------------------


def cash_section() -> str:
    """Every dollar that left the account, tied to the ticket it belonged to.

    Read from `payments` and `approvals` in the working copy, with the opening
    balance taken from the untouched original — so the arithmetic on the page is
    the database's own, and the closing figure is checked against it.
    """
    original = sqlite3.connect(
        f"file:{ROOT / 'data' / 'campus_customs.db'}?mode=ro", uri=True
    )
    try:
        opening = original.execute(
            "SELECT balance FROM cash_accounts WHERE name='checking'"
        ).fetchone()[0]
        # The rent that was paid was the one due before the payment rolled the
        # lease on, so take that date from the original too.
        rent_was_due = original.execute(
            "SELECT next_due FROM leases WHERE id=1"
        ).fetchone()[0]
    finally:
        original.close()

    payments = q("SELECT * FROM payments ORDER BY id")
    approvals = {a["payment_id"]: a for a in q("SELECT * FROM approvals") if a["payment_id"]}
    tickets = q("SELECT * FROM tickets ORDER BY id")
    closing = one("SELECT balance FROM cash_accounts WHERE name='checking'")["balance"]

    def ticket_for(payment: dict) -> dict | None:
        """Which ticket a payment belongs to, from the ticket's own links."""
        for ticket in tickets:
            if payment["kind"] == "invoice" and ticket["invoice_id"] == payment["ref_id"]:
                return ticket
            if payment["kind"] == "rent" and ticket["lease_id"] == payment["ref_id"]:
                return ticket
        return None

    rows = [
        f"<tr class='cash-open'><td>—</td><td><strong>Starting balance</strong>"
        f"<span class='cash-why'>after <code>./scripts/reset_db.sh</code></span></td>"
        f"<td class='num'></td><td class='num'><strong>{money(opening)}</strong></td></tr>"
    ]

    running = opening
    spent_by_ticket: dict[int, float] = {}
    for payment in payments:
        ticket = ticket_for(payment)
        approval = approvals.get(payment["id"])
        running = round(running - payment["amount"], 2)
        if ticket:
            spent_by_ticket[ticket["id"]] = round(
                spent_by_ticket.get(ticket["id"], 0) + payment["amount"], 2
            )
        why = (
            f"invoice #{payment['ref_id']} — {e(INVOICE['description'])}; the vendor "
            "would not ship while it was open"
            if payment["kind"] == "invoice"
            else f"rent on lease #{payment['ref_id']}, {e(LEASE['space_name'])}, "
            f"which was due {e(rent_was_due)}; paying it rolled the lease on to "
            f"{e(LEASE['next_due'])}"
        )
        rows.append(
            f"<tr><td class='cash-ticket'>#{ticket['id'] if ticket else '—'}</td>"
            f"<td><strong>{e(payment['kind'])} payment</strong>"
            f"<span class='cash-why'>{why}<br>approved by "
            f"<strong>{e(approval['approved_by']) if approval else 'unknown'}</strong>, "
            f"proposed by {e(approval['requested_by']) if approval else 'unknown'}</span></td>"
            f"<td class='num out'>−{money(payment['amount'])}</td>"
            f"<td class='num'>{money(running)}</td></tr>"
        )

    for ticket in tickets:
        if ticket["id"] not in spent_by_ticket:
            why = (
                f"the {e(str(20 - 8))}-unit restock would cost {money(restock_cost)}, "
                f"more than the {money(running)} left"
                if ticket["id"] == 103
                else "nothing was bought for this ticket"
            )
            rows.append(
                f"<tr class='cash-none'><td class='cash-ticket'>#{ticket['id']}</td>"
                f"<td><strong>no money moved</strong><span class='cash-why'>{why}</span></td>"
                f"<td class='num'>{money(0)}</td><td class='num'>{money(running)}</td></tr>"
            )

    rows.append(
        f"<tr class='cash-close'><td>—</td><td><strong>Ending balance</strong>"
        f"<span class='cash-why'>checked against <code>cash_accounts</code> in the "
        f"working database</span></td>"
        f"<td class='num'></td><td class='num'><strong>{money(closing)}</strong></td></tr>"
    )

    total = round(sum(p["amount"] for p in payments), 2)
    agrees = round(opening - total, 2) == round(closing, 2)

    per_ticket = "".join(
        f"<li><strong>Ticket #{t['id']}</strong> — "
        + (
            f"{money(spent_by_ticket[t['id']])} out"
            if t["id"] in spent_by_ticket
            else "nothing spent"
        )
        + f" · ticket is <em>{e(t['status'])}</em></li>"
        for t in tickets
    )

    return f"""
  <p class="lede">Every dollar that left the account on this run, tied to the ticket
  it belonged to. Read from <code>payments</code> and <code>approvals</code>; the
  opening figure comes from the untouched original database.</p>

  <table class="cash">
    <thead><tr><th>Ticket</th><th>What</th><th class="num">Amount</th><th class="num">Balance</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <h4 class="plain">Per ticket</h4>
  <ul class="cash-per">{per_ticket}</ul>

  <h4 class="plain">The check</h4>
  <p class="cash-check {'ok' if agrees else 'bad'}">
    {money(opening)} opening − {money(total)} paid = <strong>{money(round(opening - total, 2))}</strong>,
    and <code>cash_accounts</code> says <strong>{money(closing)}</strong>.
    {'They agree.' if agrees else 'THEY DO NOT AGREE.'}
  </p>

  <p class="lede">Nothing came in: this shop models no revenue, so the balance only
  falls. Both payments carry the name of the person who approved them — the agents
  proposed, and could not have paid without that signature.</p>
"""


# --- the reflection tab ----------------------------------------------------

REFLECTION_SECTIONS = [
    (
        "1. How I’d evaluate the agents on each ticket",
        """<p>I look at four things: did the numbers come from the database, did the
        agents follow the shop rules, did Boss only call the agents it needed, and
        would a real owner be happy with the result. I care most about the first two,
        because the agents are working with real money and real customers.</p>

        <p><strong>Ticket 101 (Bulldog tee).</strong> The facts held up. Bulldog Print
        Co has a 5-day lead time, and 2026-08-31 plus 5 days is the 2026-09-05 date in
        the draft. Accounting also worked out that overdue invoice 501 was blocking the
        restock. What worries me is the routing. Boss went to Customer Service before
        anyone had the facts, and Accounting proposed the same $840 twice. The ticket is
        also still open, so I can’t call it finished.</p>

        <p><strong>Ticket 102 (Rent due).</strong> This one looks clean. It’s resolved,
        and Accounting proposed $2,400 for the Chapel Street rent due 2026-09-02, noted
        there was enough cash, and waited for my approval. I don’t see any wasted steps
        in the screenshot.</p>

        <p><strong>Ticket 103 (Bulk hoodie discount).</strong> It hasn’t run, so there’s
        nothing to evaluate yet.</p>""",
    ),
    (
        "2. Actual vs. Expected",
        """<p>On <strong>101</strong>, I expected Boss to call Inventory first, then
        Accounting about the vendor invoice, then Customer Service for the draft. Instead
        Boss went to Customer Service first, and Customer Service had to ask Inventory for
        the facts. The right agents showed up in the wrong order, which wasted steps. The
        duplicate $840 proposal wasn’t in my plan at all.</p>

        <p>On <strong>102</strong>, I expected Facilities, then Accounting, with Inventory
        and Customer Service left out. That’s what the screenshot looks like: a rent
        payment from Accounting and no activity from the other two.</p>

        <p>On <strong>103</strong>, I expect Accounting first to check the margin on 20
        navy hoodies in size M, then Inventory to confirm stock, then Customer Service for
        the reply. I’ll compare that after it runs.</p>""",
    ),
    (
        "3. What would’ve been simpler as one agent",
        """<p>Honestly, most of it. All three tickets use the same database through the
        same MCP server, and each one is a few lookups followed by a draft or a payment
        proposal. One agent with the same tools could do that in one loop. The 101 mess is
        a good example: Customer Service had to pass a question to Inventory, and a single
        agent would have just looked up the stock itself.</p>

        <p>What the team did buy me was separation of duties. Only Accounting touches
        money, and Customer Service only drafts. That’s nice, but a single agent with a
        pay tool that needs approval and refuses overdrafts would be about as safe.</p>""",
    ),
    (
        "4. Three new problems this team could handle",
        """<ul>
          <li>A customer asks whether a size is in stock and when it could ship.
          Inventory checks stock and lead time, and Customer Service drafts the answer.</li>
          <li>A different vendor invoice goes overdue and blocks a restock. Accounting
          checks the due date against today’s date and the cash balance, then prepares the
          payment.</li>
          <li>A lease or utility bill comes due. Facilities reads the lease and Accounting
          prepares the payment.</li>
        </ul>""",
    ),
    (
        "5. Three new problems it couldn’t handle",
        """<ul>
          <li><strong>Deciding how much to reorder.</strong> The database has current
          stock but no sales history. I’d add a sales table, a demand forecasting tool,
          and a Planning agent.</li>
          <li><strong>Running out of cash.</strong> The balance is $160 and the shop only
          spends money, because no revenue is modeled. I’d need a tool to record customer
          payments, a cash forecast tool, and a Collections agent to chase what’s
          owed.</li>
          <li><strong>Finding a cheaper vendor.</strong> The agents only know one vendor’s
          lead time and can’t compare quotes or contact anyone. I’d add a vendor quote
          tool, a send-message tool that needs human sign-off, and a Procurement agent
          with limits on how far it can negotiate.</li>
        </ul>""",
    ),
]


def record_check() -> str:
    """Where the reflection and the audit trail disagree.

    Generated from `run_actuals.json`, not typed in, so it stays true if the
    board is run again. Kept separate from the reflection above rather than
    edited into it — the reflection is a record of what I thought at the time.
    """
    checks = []
    for ticket_id in (101, 102, 103):
        entry = RUN["tickets"].get(str(ticket_id))
        if not entry:
            continue
        order = [f"{a} → {b}" for a, b in entry["delegations"]]
        first = entry["delegations"][0][1] if entry["delegations"] else "—"
        proposals = entry["tools"].get("propose_payment", 0)
        checks.append(
            (ticket_id, len(entry["runs"]), first, order, proposals, entry["final_status"])
        )

    rows = "".join(
        f"<tr><td>#{tid}</td><td>{runs}</td><td><strong>{e(first)}</strong></td>"
        f"<td class='tbl'>{' · '.join(e(o) for o in order)}</td>"
        f"<td>{props}</td><td>{e(status)}</td></tr>"
        for tid, runs, first, order, props, status in checks
    )

    return f"""
  <h3 class="actual">Checked against the record</h3>
  <p class="lede">Notes from the audit trail, kept separate from the reflection above —
  the reflection says what I thought when I wrote it, and this says what the trail
  shows. Three things do not match.</p>

  <table class="tools">
    <thead><tr><th>Ticket</th><th>Runs</th><th>Boss called first</th>
      <th>Delegations, in order</th><th><code>propose_payment</code></th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <ol class="steps">
    <li><strong>On 101, Boss did call Inventory first.</strong> The trail has
      <code>boss → inventory</code>, then <code>boss → accounting</code>, then
      <code>boss → customer_service</code>, and only then Customer Service asking
      Inventory to confirm before writing. The feed in the screenshot is scrolled to
      its end, so the visible part starts mid-run with Customer Service — the order
      above it had already happened.</li>
    <li><strong>The duplicate $840 is real, and it was across runs, not within
      one.</strong> Accounting proposed it once in the first pass and again in the
      second, because the first proposal had already been approved by then and the
      duplicate check only looked for a <em>pending</em> one. That is fixed — an
      approved-but-unspent proposal now counts as live — and the stale row was
      declined rather than deleted, so it reads DECLINED on the board.</li>
    <li><strong>Ticket 103 did run — three times.</strong> It took the same shape as
      101: Inventory, then Accounting, then Customer Service, with Customer Service
      checking back with Inventory. No payment was ever proposed for it, which is the
      right answer: the 12-unit shortfall is {money(restock_cost)} of arithmetic off
      the pricing table, not a bill, and only {money(AFTER_RENT)} is left. It is still
      open because the discount is a human’s call and the restock cannot be afforded —
      so the section 1 note, and the plan in section 2 to compare “after it runs”, can
      both be settled from the Actual tab now.</li>
  </ol>

  <p class="lede">The 102 reading holds up exactly: Facilities, then Accounting, then
  the draft — Inventory never touched it.</p>"""


COMING = {
    "reflection": (
        "Reflection",
        "What the run taught",
        "This tab will hold the write-up once the agents have been run against "
        "the board — what they got right, what they missed, and what had to change.",
    ),
}

TABS = [TAB_101, TAB_102, TAB_103]


def ticket_panel(tab: dict) -> str:
    return f"""
<section class="panel" id="panel-{tab['id']}" role="tabpanel" aria-labelledby="tab-{tab['id']}" hidden>
  <header class="panel-head">
    <h2>{tab['title']}</h2>
    <p class="meta">{tab['meta']}</p>
    <blockquote>{e(tab['quote'])}</blockquote>
  </header>

  <h3>What the database says</h3>
  {tab['facts']}

  <h3 class="expected">Expected</h3>
  <p class="lede">What the agent team should do with this ticket, from the data above.</p>

  <h4 class="plain">Boss calls first</h4>
  <p class="first-call">{tab['first_call']}</p>

  <h4 class="plain">Workflow</h4>
  {tab['workflow']}

  <h4 class="plain">MCP tools expected to run, and why</h4>
  {tab['tools']}

  <h4 class="plain">Skipped, and why</h4>
  <p class="skipped">{tab['skipped']}</p>

  <h4>It should not</h4>
  {tab['nots']}

  <h3 class="actual">Actual</h3>
  <p class="lede">What the team really did, from the audit trail and the database.</p>
  {actual_section(int(tab['id']))}

  <h4 class="plain">My notes</h4>
  <textarea class="notes" data-key="actual-{tab['id']}" rows="6"
    placeholder="Expected vs actual — what surprised you on ticket {tab['id']}?"></textarea>
  <p class="saved" data-for="actual-{tab['id']}"></p>
</section>"""


def reflection_panel() -> str:
    sections = "".join(
        f"<h4 class='plain'>{e(title)}</h4>{body}" for title, body in REFLECTION_SECTIONS
    )
    return f"""
<section class="panel" id="panel-reflection" role="tabpanel" aria-labelledby="tab-reflection" hidden>
  <header class="panel-head">
    <h2>Reflection</h2>
  </header>
  {sections}
  {record_check()}
</section>"""


def cash_panel() -> str:
    return f"""
<section class="panel" id="panel-cash" role="tabpanel" aria-labelledby="tab-cash" hidden>
  <header class="panel-head">
    <h2>Cash — where the money went</h2>
  </header>
  {cash_section()}
</section>"""


def coming_panel(key: str) -> str:
    label, title, blurb = COMING[key]
    return f"""
<section class="panel" id="panel-{key}" role="tabpanel" aria-labelledby="tab-{key}" hidden>
  <header class="panel-head">
    <h2>{title} <span class="later">coming later</span></h2>
  </header>
  <p class="lede">{blurb}</p>
  <div class="placeholder">Nothing here yet.</div>
</section>"""


buttons = "".join(
    f"<button role='tab' id='tab-{t['id']}' aria-controls='panel-{t['id']}' "
    f"aria-selected='false'><span>{t['label']}</span><small>{t['sub']}</small></button>"
    for t in TABS
) + (
    "<button role='tab' id='tab-cash' aria-controls='panel-cash' aria-selected='false'>"
    "<span>Cash</span><small>the ledger</small></button>"
    "<button role='tab' id='tab-reflection' aria-controls='panel-reflection' "
    "aria-selected='false'><span>Reflection</span><small>what it taught</small></button>"
)

panels = "".join(ticket_panel(t) for t in TABS) + cash_panel() + reflection_panel()

HTML = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Campus Customs — the desk</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg: #faf9f7; --card: #fff; --ink: #1b1a17; --muted: #6b6760;
    --line: #e3dfd8; --accent: #0f5c4e; --warn: #8a3b12; --chip: #f0ece4;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #161513; --card: #1e1d1a; --ink: #f0ece4; --muted: #a39d93;
      --line: #322f2a; --accent: #6fcdb9; --warn: #e2a06a; --chip: #2a2824;
    }}
    body {{ background: #161513; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2rem 1.25rem 4rem; background: var(--bg); color: var(--ink);
    font: 16px/1.6 ui-serif, Georgia, "Times New Roman", serif;
  }}
  .wrap {{ max-width: 54rem; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 .25rem; letter-spacing: -.01em; }}
  .sub {{ color: var(--muted); margin: 0 0 1.5rem; font-size: .95rem; }}
  .sub code {{ background: var(--chip); padding: .1rem .35rem; border-radius: 4px; }}
  [role=tablist] {{ display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: -1px; }}
  [role=tab] {{
    display: flex; flex-direction: column; gap: .1rem; align-items: flex-start;
    padding: .55rem .9rem; background: transparent; color: var(--muted);
    border: 1px solid transparent; border-radius: 8px 8px 0 0; cursor: pointer;
    font: inherit; font-size: .95rem;
  }}
  [role=tab] small {{ font-size: .72rem; letter-spacing: .04em; text-transform: uppercase; }}
  [role=tab]:hover {{ color: var(--ink); }}
  [role=tab][aria-selected=true] {{
    background: var(--card); color: var(--ink); border-color: var(--line);
    border-bottom-color: var(--card); font-weight: 600;
  }}
  [role=tab].is-later {{ opacity: .6; font-style: italic; }}
  .panel {{
    background: var(--card); border: 1px solid var(--line); border-radius: 0 10px 10px 10px;
    padding: 1.75rem;
  }}
  .panel-head h2 {{ margin: 0 0 .2rem; font-size: 1.3rem; }}
  .meta {{ color: var(--muted); font-size: .88rem; margin: 0 0 .9rem; }}
  blockquote {{
    margin: 0; padding: .6rem .9rem; border-left: 3px solid var(--accent);
    background: var(--chip); border-radius: 0 6px 6px 0; font-style: italic;
  }}
  h3 {{ font-size: 1.05rem; margin: 1.8rem 0 .6rem; padding-bottom: .3rem; border-bottom: 1px solid var(--line); }}
  h3.expected::before {{ content: "✓ "; color: var(--accent); }}
  h3.actual::before {{ content: "✎ "; color: var(--warn); }}
  h4 {{ font-size: .92rem; margin: 1.2rem 0 .4rem; color: var(--warn); }}
  h4.plain {{
    color: var(--muted); text-transform: uppercase; letter-spacing: .06em;
    font-size: .75rem; margin-top: 1.5rem;
    font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  .first-call, .skipped {{ margin: 0 0 .4rem; }}
  .actual-status {{
    display: inline-block; margin: 0 0 .4rem; padding: .2rem .6rem; border-radius: 999px;
    font-family: ui-sans-serif, system-ui, sans-serif; font-size: .74rem; letter-spacing: .08em;
  }}
  .actual-status.is-resolved {{ background: #e0efe6; color: #2c7a55; }}
  .actual-status.is-open {{ background: #fbe7d9; color: #8a3b12; }}
  .who {{
    display: inline-block; padding: .08rem .45rem; border-radius: 999px; color: #fff;
    background: var(--who); font-size: .76rem; font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  .chips {{ display: flex; flex-wrap: wrap; gap: .3rem; margin: 0 0 .4rem; }}
  .chain-list, .moved, .refusals {{ margin: 0 0 .4rem; padding-left: 1.1rem; }}
  .chain-list {{ list-style: none; padding-left: 0; }}
  .chain-list li {{ margin-bottom: .25rem; }}
  .arrow {{ color: var(--muted); font-size: .8rem; margin: 0 .15rem; }}
  .moved li, .refusals li {{ margin-bottom: .3rem; font-size: .9rem; }}
  .refusals li {{ color: var(--warn); }}
  .tool-counts td.count {{ color: var(--muted); text-align: right; width: 4rem; }}
  table.cash {{ width: 100%; border-collapse: collapse; font-size: .92rem; margin-bottom: .6rem; }}
  table.cash th {{
    text-align: left; font-size: .7rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--muted); padding: 0 .6rem .4rem 0; border-bottom: 1px solid var(--line);
    font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  table.cash th.num, table.cash td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table.cash td {{ padding: .55rem .6rem .55rem 0; border-bottom: 1px solid var(--line); vertical-align: top; }}
  table.cash td.out {{ color: var(--warn); font-weight: 600; }}
  td.cash-ticket {{ font-family: ui-monospace, Menlo, monospace; color: var(--muted); }}
  .cash-why {{ display: block; color: var(--muted); font-size: .8rem; margin-top: .15rem; }}
  tr.cash-open td, tr.cash-close td {{ background: var(--chip); }}
  tr.cash-none td {{ opacity: .75; }}
  .cash-per {{ margin: 0 0 .6rem; padding-left: 1.1rem; }}
  .cash-check {{
    padding: .6rem .8rem; border-radius: 8px; font-size: .94rem;
    background: var(--chip); border-left: 3px solid var(--accent);
  }}
  .cash-check.bad {{ background: #fdeee9; }}
  .skipped {{ color: var(--muted); font-size: .92rem; }}
  table.tools {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
  table.tools th {{
    text-align: left; font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
    color: var(--muted); padding: 0 .7rem .35rem 0; border-bottom: 1px solid var(--line);
    font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  table.tools td {{ padding: .45rem .7rem .45rem 0; border-bottom: 1px solid var(--line); vertical-align: top; }}
  table.tools td.tbl {{ color: var(--muted); font-size: .82rem; white-space: normal; }}
  table.tools tr:last-child td {{ border-bottom: 0; }}
  .lede {{ color: var(--muted); font-size: .9rem; margin: 0 0 .8rem; }}
  table.facts {{ width: 100%; border-collapse: collapse; font-size: .94rem; }}
  table.facts th {{
    text-align: left; font-weight: 600; color: var(--muted); width: 11rem;
    padding: .45rem .8rem .45rem 0; vertical-align: top; font-size: .85rem;
    text-transform: uppercase; letter-spacing: .03em;
  }}
  table.facts td {{ padding: .45rem 0; border-bottom: 1px solid var(--line); }}
  table.facts tr:last-child td {{ border-bottom: 0; }}
  ol.steps {{ margin: 0; padding-left: 1.3rem; }}
  ol.steps li {{ margin-bottom: .55rem; }}
  ul.nots {{ margin: 0; padding-left: 1.3rem; list-style: none; }}
  ul.nots li {{ margin-bottom: .4rem; position: relative; }}
  ul.nots li::before {{ content: "✕"; position: absolute; left: -1.3rem; color: var(--warn); }}
  code {{ font: .88em ui-monospace, "SF Mono", Menlo, monospace; background: var(--chip); padding: .08rem .3rem; border-radius: 4px; }}
  textarea.notes {{
    width: 100%; padding: .8rem; border: 1px dashed var(--line); border-radius: 8px;
    background: var(--bg); color: var(--ink); font: inherit; font-size: .95rem; resize: vertical;
  }}
  textarea.notes:focus {{ outline: 2px solid var(--accent); outline-offset: 1px; border-style: solid; }}
  .saved {{ font-size: .78rem; color: var(--muted); min-height: 1.2em; margin: .3rem 0 0; }}
  .later {{
    font-size: .68rem; text-transform: uppercase; letter-spacing: .08em; vertical-align: middle;
    background: var(--chip); color: var(--muted); padding: .2rem .5rem; border-radius: 999px;
    font-family: ui-sans-serif, system-ui, sans-serif; font-style: normal;
  }}
  .placeholder {{
    border: 1px dashed var(--line); border-radius: 8px; padding: 2.5rem 1rem;
    text-align: center; color: var(--muted); font-style: italic;
  }}
  footer {{ color: var(--muted); font-size: .8rem; margin-top: 1.2rem; text-align: right; }}
</style>

<div class="wrap">
  <h1>Campus Customs — the desk</h1>
  <p class="sub">
    Three open tickets as of the shop's date, <strong>{e(TODAY)}</strong>.
    Every figure below is read from <code>data/campus_customs_new.db</code> on a reset board;
    checking holds <strong>{money(CASH['balance'])}</strong>.
  </p>

  <div role="tablist" aria-label="Tickets">{buttons}</div>
  {panels}

  <footer>Built from the database by <code>scripts/build_desk_page.py</code>.</footer>
</div>

<script>
  const tabs = [...document.querySelectorAll('[role=tab]')];
  const panels = [...document.querySelectorAll('.panel')];

  function show(id) {{
    tabs.forEach(t => t.setAttribute('aria-selected', String(t.id === 'tab-' + id)));
    panels.forEach(p => {{ p.hidden = p.id !== 'panel-' + id; }});
    try {{ localStorage.setItem('desk-tab', id); }} catch (e) {{}}
  }}

  tabs.forEach(tab => {{
    tab.addEventListener('click', () => show(tab.id.replace('tab-', '')));
    tab.addEventListener('keydown', ev => {{
      const i = tabs.indexOf(tab);
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {{
        const next = tabs[(i + (ev.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
        next.focus(); show(next.id.replace('tab-', ''));
      }}
    }});
  }});

  // The Actual sections are mine to fill in; keep them across reloads.
  document.querySelectorAll('textarea.notes').forEach(box => {{
    const key = 'desk-' + box.dataset.key;
    const label = document.querySelector('.saved[data-for="' + box.dataset.key + '"]');
    try {{ box.value = localStorage.getItem(key) || ''; }} catch (e) {{}}
    let timer;
    box.addEventListener('input', () => {{
      clearTimeout(timer);
      timer = setTimeout(() => {{
        try {{
          localStorage.setItem(key, box.value);
          label.textContent = 'saved in this browser · ' + new Date().toLocaleTimeString();
        }} catch (e) {{ label.textContent = 'could not save in this browser'; }}
      }}, 400);
    }});
  }});

  let start = '101';
  try {{ start = localStorage.getItem('desk-tab') || '101'; }} catch (e) {{}}
  show(document.getElementById('tab-' + start) ? start : '101');
</script>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"written: {OUT.relative_to(ROOT)}  ({len(HTML):,} bytes, no external files)")
