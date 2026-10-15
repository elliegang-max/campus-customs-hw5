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
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "desk_tickets.html"


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
    "expected": steps([
        f"<strong>Inventory</strong> finds size {e(t101['size'])} at <strong>{on_hand_101}</strong> — nothing to sell. The shortfall is {t101['qty'] - on_hand_101}.",
        f"The ticket already points at invoice <strong>#{INVOICE['id']}</strong>, described as “{e(INVOICE['description'])}” — the restock was ordered and billed.",
        f"<strong>{e(APPAREL_VENDOR['name'])} will not ship</strong> while that invoice is open, so <code>get_vendor_status</code> should come back <code>can_ship: false</code>.",
        f"<strong>Accounting</strong> proposes paying {money(INVOICE['amount'])} — {money(CASH['balance'])} → <strong>{money(AFTER_INVOICE)}</strong> — and the proposal should name <strong>both tickets 101 and 103</strong> as unblocked, since the same vendor supplies both.",
        "<strong>Nothing is paid.</strong> The proposal sits at <code>proposed</code> until a human approves it.",
        f"<strong>Customer Service</strong> drafts to {e(t101['requester'])}: out of stock in {e(t101['size'])}, restock delayed, <em>no date</em>. Stored with <code>sent: false</code>.",
        "The ticket stays <strong>open</strong>: it needs an approval, then a payment, then a vendor shipment.",
    ]),
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
    "expected": steps([
        f"<strong>Facilities</strong> reads lease #{LEASE['id']} and reports {money(LEASE['monthly_rent'])} due {e(LEASE['next_due'])} — <strong>{RENT_DUE_IN} days</strong> from the shop's date of {e(TODAY)}. Not overdue.",
        "The figures come from the <em>lease row</em>, not from the email that raised the ticket. A notice can be wrong; the lease is the record.",
        f"<strong>Accounting</strong> confirms it is affordable and proposes it: {money(CASH['balance'])} → {money(round(CASH['balance'] - LEASE['monthly_rent'], 2))} on its own, or <strong>{money(AFTER_RENT)}</strong> if the invoice is paid first.",
        "<strong>Nothing is paid.</strong> Rent waits on the same human approval as anything else.",
        f"<strong>Customer Service</strong> drafts to {e(LEASE['landlord'])} acknowledging the due date, with <code>sent: false</code>.",
        "The ticket stays <strong>open</strong> until the rent is approved and paid.",
    ]),
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
    "expected": steps([
        f"<strong>Inventory</strong> finds {on_hand_103} of {t103['qty']} in size {e(t103['size'])} — <strong>short by {short_103}</strong>. The {sum(r['qty'] for r in other_sizes)} in other sizes do not count.",
        f"The missing {short_103} are apparel, so the supplier is {e(APPAREL_VENDOR['name'])} — <strong>the same vendor blocked by invoice #{INVOICE['id']}</strong>. This ticket and 101 queue behind one payment.",
        f"<strong>Accounting must be asked</strong>, even though the ticket never mentions money: a restock is a purchase. {short_103} × {money(p103['unit_cost'])} = <strong>{money(restock_cost)}</strong>.",
        f"That restock <strong>does not fit</strong>. After the invoice and the rent the account holds {money(AFTER_RENT)}, so {money(restock_cost)} is {money(round(restock_cost - AFTER_RENT, 2))} beyond it.",
        f"The discount question is bounded by {money(p103['unit_cost'])} cost against {money(p103['list_price'])} list — and <strong>a human sets the number</strong>. No agent should quote one.",
        f"<strong>Customer Service</strong> drafts to {e(t103['requester'])}: {on_hand_103} available now, {short_103} delayed with no date, no discount confirmed.",
        "The ticket stays <strong>open</strong>: it needs a human decision on price, and the shortfall needs money the shop does not have this week.",
    ]),
    "nots": nots([
        "Offer a discount, a percentage, or a per-unit price. That is the human decision this ticket exists to ask for.",
        f"Quote a price below {money(p103['unit_cost'])} — that is selling at a loss.",
        f"Promise the full {t103['qty']}, or a delivery date for the missing {short_103}.",
        "Treat the other sizes as filling the order.",
    ]),
}

COMING = {
    "cash": (
        "Cash",
        "Where the money went",
        "This tab will track the account: what was proposed, what a human approved, "
        "what was actually paid, and what each payment left behind.",
    ),
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
  {tab['expected']}
  <h4>It should not</h4>
  {tab['nots']}

  <h3 class="actual">Actual</h3>
  <p class="lede">For me to fill in after running the agents. Saved in this browser as you type.</p>
  <textarea class="notes" data-key="actual-{tab['id']}" rows="12"
    placeholder="What actually happened on ticket {tab['id']}…"></textarea>
  <p class="saved" data-for="actual-{tab['id']}"></p>
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
) + "".join(
    f"<button role='tab' id='tab-{k}' aria-controls='panel-{k}' aria-selected='false' "
    f"class='is-later'><span>{COMING[k][0]}</span><small>coming later</small></button>"
    for k in COMING
)

panels = "".join(ticket_panel(t) for t in TABS) + "".join(coming_panel(k) for k in COMING)

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
