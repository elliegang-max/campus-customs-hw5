"""Write output/resolved_tickets.json and output/resolved_board.html.

Both are built from the record rather than from memory: the audit trail for who
did what, the working database for the final state, and the saved board reviews
for the Boss's own words.

    ./.venv/bin/python scripts/collect_actuals.py   # mines the trail first
    ./.venv/bin/python scripts/build_resolved.py
"""

from __future__ import annotations

import html
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
ACTUALS = ROOT / "output" / "run_actuals.json"
SHOTS_DIR = ROOT / "output" / "board_shots"
JSON_OUT = ROOT / "output" / "resolved_tickets.json"
HTML_OUT = ROOT / "output" / "resolved_board.html"

AGENT_COLORS = {
    "boss": "#2F4A86",
    "inventory": "#2C7A55",
    "accounting": "#B4581C",
    "facilities": "#6B4BA3",
    "customer_service": "#0E7A84",
}


def q(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def e(v) -> str:
    return html.escape(str(v))


def money(v: float) -> str:
    return f"${v:,.2f}"


run = json.loads(ACTUALS.read_text())
tickets = q("SELECT * FROM tickets ORDER BY id")
payments = q("SELECT * FROM payments ORDER BY id")
approvals = q("SELECT * FROM approvals ORDER BY id")
drafts = q("SELECT * FROM drafts ORDER BY id")
cash = q("SELECT * FROM cash_accounts")[0]
shop_date = q("SELECT date_today FROM desk")[0]["date_today"]

# What each agent contributed, in its own tools' terms.
CONTRIBUTION = {
    "inventory": "checked stock for the SKU and size, and whether the vendor could resupply",
    "accounting": "weighed the obligations against cash and prepared payments for approval",
    "facilities": "read the lease: rent, landlord, and when it falls due",
    "customer_service": "drafted the reply to the requester and left it on the board, unsent",
    "boss": "triaged the ticket, delegated, and decided what should happen",
}


def payments_for(ticket: dict) -> list[dict]:
    out = []
    for payment in payments:
        linked = (payment["kind"] == "invoice" and ticket["invoice_id"] == payment["ref_id"]) or (
            payment["kind"] == "rent" and ticket["lease_id"] == payment["ref_id"]
        )
        if linked:
            approval = next((a for a in approvals if a["payment_id"] == payment["id"]), None)
            out.append(
                {
                    "payment_id": payment["id"],
                    "kind": payment["kind"],
                    "ref_id": payment["ref_id"],
                    "amount": payment["amount"],
                    "paid_at": payment["paid_at"],
                    "approved_by": payment["approved_by"],
                    "proposed_by": approval["requested_by"] if approval else None,
                    "approval_id": approval["id"] if approval else None,
                }
            )
    return out


records = []
for ticket in tickets:
    entry = run["tickets"].get(str(ticket["id"]), {})
    agents = entry.get("agents", [])
    # The Boss ran every ticket, whether or not it appears as a delegated agent.
    chain = ["boss"] + [a for a in agents if a != "boss"]
    ticket_payments = payments_for(ticket)
    draft = next((d for d in drafts if d["ticket_id"] == ticket["id"]), None)

    records.append(
        {
            "id": ticket["id"],
            "type": ticket["type"],
            "requester": ticket["requester"],
            "subject": ticket["subject"],
            "final_status": ticket["status"],
            "outcome": entry.get("finding", "").strip(),
            "recommended_action": entry.get("recommended_action", "").strip(),
            "still_open_because": (
                None
                if ticket["status"] != "open"
                else entry.get("recommended_action", "").strip()
            ),
            "resolution_note": (
                ticket["notes"].split("]")[-1].strip()
                if ticket["status"] != "open" and "]" in (ticket["notes"] or "")
                else None
            ),
            "runs": len(entry.get("runs", [])),
            "agents": [
                {
                    "agent": agent,
                    "contributed": CONTRIBUTION.get(agent, ""),
                }
                for agent in chain
            ],
            "delegations": [
                {"from": a, "to": b} for a, b in entry.get("delegations", [])
            ],
            "tools_used": entry.get("tools", {}),
            "tool_refusals": [
                {"agent": r["agent"], "tool": r["tool"], "refused": r["error"]}
                for r in entry.get("refusals", [])
            ],
            "human_approvals": [
                {
                    "approval_id": p["approval_id"],
                    "approved_by": p["approved_by"],
                    "for": f"{p['kind']} #{p['ref_id']}",
                    "amount": p["amount"],
                    "proposed_by": p["proposed_by"],
                }
                for p in ticket_payments
            ],
            "cash_effect": {
                "paid_out": round(sum(p["amount"] for p in ticket_payments), 2),
                "payments": ticket_payments,
            },
            "draft_reply": (
                {"to": draft["to_whom"], "subject": draft["subject"], "sent": bool(draft["sent"])}
                if draft
                else None
            ),
        }
    )

JSON_OUT.write_text(
    json.dumps(
        {
            "shop_date": shop_date,
            "checking_end": cash["balance"],
            "tickets": records,
            "note": (
                "Built from output/audit_trail.json and the working database. "
                "A ticket is resolved only when the team called resolve_ticket."
            ),
        },
        indent=2,
    )
    + "\n"
)

# --- the board page --------------------------------------------------------

SHOTS_DIR.mkdir(parents=True, exist_ok=True)


def shot_for(ticket_id: int) -> str:
    """The board screenshot for a ticket, or a placeholder saying how to make it."""
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = SHOTS_DIR / f"ticket-{ticket_id}{suffix}"
        if candidate.exists():
            return (
                f"<img src='board_shots/{candidate.name}' alt='The React board "
                f"showing ticket {ticket_id}' loading='lazy'>"
            )
    return f"""<div class="shot-missing">
      <p><strong>No screenshot yet for ticket {ticket_id}.</strong></p>
      <p>Start the board, work ticket {ticket_id}, and save the screenshot as
      <code>output/board_shots/ticket-{ticket_id}.png</code>. Re-run
      <code>scripts/build_resolved.py</code> and it appears here.</p>
    </div>"""


cards = []
for record in records:
    resolved = record["final_status"] != "open"
    agents = "".join(
        f"<li style='--who:{AGENT_COLORS.get(a['agent'], '#7A6E5D')}'>"
        f"<strong>{e(a['agent'].replace('_', ' '))}</strong> {e(a['contributed'])}</li>"
        for a in record["agents"]
    )
    approvals_html = (
        "".join(
            f"<li>{e(h['approved_by'])} approved {e(h['for'])} — "
            f"<strong>{money(h['amount'])}</strong>, proposed by {e(h['proposed_by'])}</li>"
            for h in record["human_approvals"]
        )
        or "<li class='none'>no payment was needed for this ticket</li>"
    )
    cards.append(f"""
<section class="card">
  <header>
    <h2>Ticket #{record['id']} — {e(record['subject'])}</h2>
    <span class="status {'resolved' if resolved else 'open'}">{e(record['final_status'])}</span>
  </header>
  <p class="meta">{e(record['type'])} · {e(record['requester'])} · {record['runs']} run(s)</p>

  <figure class="shot">{shot_for(record['id'])}
    <figcaption>the React board, ticket #{record['id']}</figcaption>
  </figure>

  <h3>Outcome</h3>
  <p>{e(record['outcome'])}</p>

  <h3>Who did what</h3>
  <ul class="agents">{agents}</ul>

  <h3>Human approvals</h3>
  <ul class="approvals">{approvals_html}</ul>

  <p class="cash">cash out on this ticket: <strong>{money(record['cash_effect']['paid_out'])}</strong></p>
</section>""")

HTML_OUT.write_text(f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Campus Customs — the board, ticket by ticket</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ --cream:#faf4e8; --paper:#fffdf7; --navy:#14233f; --muted:#7b8398;
           --line:#e2d7c3; --accent:#d6451f; --good:#2c7a55; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:2rem 1.25rem 4rem; background:var(--cream); color:var(--navy);
         font:16px/1.55 ui-sans-serif, -apple-system, system-ui, sans-serif; }}
  .wrap {{ max-width:60rem; margin:0 auto; display:flex; flex-direction:column; gap:1.5rem; }}
  h1 {{ font-family:ui-serif, Georgia, serif; font-size:1.8rem; margin:0; }}
  h1::after {{ content:""; display:block; width:3rem; height:4px; background:var(--accent); margin-top:.5rem; }}
  .lede {{ color:var(--muted); margin:0; font-size:.95rem; }}
  .card {{ background:var(--paper); border:1px solid var(--line); border-radius:12px;
           padding:1.4rem 1.5rem; box-shadow:0 10px 24px -18px rgba(20,35,63,.5); }}
  .card header {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; }}
  .card h2 {{ font-family:ui-serif, Georgia, serif; font-size:1.25rem; margin:0; }}
  .status {{ padding:.2rem .6rem; border-radius:999px; font-size:.7rem; letter-spacing:.1em;
             text-transform:uppercase; }}
  .status.resolved {{ background:#e0efe6; color:var(--good); font-weight:700; }}
  .status.open {{ background:#fbe7d9; color:#8a3b12; }}
  .meta {{ color:var(--muted); font-size:.85rem; margin:.2rem 0 1rem; }}
  h3 {{ font-size:.74rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted);
        margin:1.2rem 0 .4rem; }}
  figure.shot {{ margin:0; }}
  figure.shot img {{ width:100%; border:1px solid var(--line); border-radius:8px; display:block; }}
  figcaption {{ color:var(--muted); font-size:.78rem; margin-top:.35rem; text-align:center; }}
  .shot-missing {{ border:1px dashed var(--line); border-radius:8px; padding:1.5rem;
                   text-align:center; color:var(--muted); font-size:.9rem; background:#fbf7ee; }}
  .shot-missing code {{ background:#f0ece4; padding:.1rem .35rem; border-radius:4px; }}
  ul {{ margin:0; padding-left:1.1rem; }}
  ul.agents {{ list-style:none; padding:0; }}
  ul.agents li {{ border-left:3px solid var(--who); padding-left:.6rem; margin-bottom:.4rem; font-size:.92rem; }}
  ul.approvals li {{ font-size:.92rem; margin-bottom:.3rem; }}
  li.none {{ color:var(--muted); font-style:italic; list-style:none; margin-left:-1.1rem; }}
  .cash {{ margin:1rem 0 0; padding-top:.7rem; border-top:1px solid var(--line);
           font-variant-numeric:tabular-nums; }}
  footer {{ color:var(--muted); font-size:.82rem; text-align:center; }}
</style>
<div class="wrap">
  <header>
    <h1>The board, ticket by ticket</h1>
    <p class="lede">Shop date {e(shop_date)} · checking ended at
      <strong>{money(cash['balance'])}</strong> · built from the audit trail and the
      working database.</p>
  </header>
  {''.join(cards)}
  <footer>Rebuild with <code>scripts/build_resolved.py</code>.</footer>
</div>
</html>
""")

print(f"written: {JSON_OUT.relative_to(ROOT)}")
print(f"written: {HTML_OUT.relative_to(ROOT)}")
missing = [r["id"] for r in records if "shot-missing" in shot_for(r["id"])]
if missing:
    print(f"screenshots still needed for tickets: {missing} -> output/board_shots/ticket-<id>.png")
