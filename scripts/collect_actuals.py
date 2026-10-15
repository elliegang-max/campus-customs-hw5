"""Mine the audit trail for what actually happened, per ticket.

Writes `output/run_actuals.json`, which `build_desk_page.py` reads to fill the
Actual section of each ticket tab. Everything here comes from the trail and the
database — no run is described from memory.

    ./.venv/bin/python scripts/collect_actuals.py
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIL = ROOT / "output" / "audit_trail.json"
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "run_actuals.json"

TICKET_IN_INSTRUCTION = re.compile(r"Work ticket (\d+)")


def db_rows(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


records = json.loads(TRAIL.read_text())

# Which run worked which ticket: the Boss's own instruction says so.
run_ticket: dict[str, int] = {}
for record in records:
    if record["event"] == "run_started":
        match = TICKET_IN_INSTRUCTION.search(str(record.get("instruction", "")))
        if match:
            run_ticket[record["run_id"]] = int(match.group(1))

# Only the runs from the clean sweep: every run after the last database reset.
last_reset = max(
    (r["seq"] for r in records if r["event"] == "database_reset"), default=0
)
sweep = [r for r in records if r["seq"] > last_reset and r["run_id"] in run_ticket]

by_ticket: dict[int, dict] = {}
for record in sweep:
    ticket = run_ticket[record["run_id"]]
    entry = by_ticket.setdefault(
        ticket,
        {
            "ticket_id": ticket,
            "runs": [],
            "agents": [],
            "delegations": [],
            "tools": Counter(),
            "tool_detail": [],
            "refusals": [],
        },
    )
    if record["run_id"] not in entry["runs"]:
        entry["runs"].append(record["run_id"])

    if record["event"] == "agent_started":
        who = record.get("agent")
        if who and who not in entry["agents"]:
            entry["agents"].append(who)
    elif record["event"] == "delegation":
        pair = (record.get("requested_by"), record.get("asked"))
        if pair not in [tuple(d) for d in entry["delegations"]]:
            entry["delegations"].append(list(pair))
    elif record["event"] == "tool_call":
        tool = record.get("tool")
        entry["tools"][tool] += 1
        if tool in ("propose_payment", "pay", "resolve_ticket", "record_draft_reply"):
            entry["tool_detail"].append(
                {
                    "agent": record.get("agent"),
                    "tool": tool,
                    "ok": record.get("ok"),
                    "args": record.get("arguments"),
                    "result": record.get("result"),
                    "error": record.get("error"),
                }
            )
        if record.get("ok") is False:
            entry["refusals"].append(
                {"agent": record.get("agent"), "tool": tool, "error": record.get("error")}
            )

# The final word from the database itself.
tickets = {t["id"]: t for t in db_rows("SELECT * FROM tickets")}
payments = db_rows("SELECT * FROM payments ORDER BY id")
approvals = db_rows("SELECT * FROM approvals ORDER BY id")
cash = db_rows("SELECT * FROM cash_accounts")[0]

for ticket_id, entry in by_ticket.items():
    entry["tools"] = dict(entry["tools"])
    entry["final_status"] = tickets[ticket_id]["status"]
    entry["notes"] = tickets[ticket_id]["notes"]
    # The last review written for this ticket, if the file is there.
    reviews = sorted(ROOT.glob(f"output/run_{ticket_id}_pass*.json"))
    if reviews:
        review = json.loads(reviews[-1].read_text())
        outcome = next(
            (o for o in review["outcomes"] if o["ticket_id"] == ticket_id), None
        )
        if outcome:
            entry["finding"] = outcome["finding"]
            entry["recommended_action"] = outcome["recommended_action"]
            entry["resolved_flag"] = outcome["resolved"]
            entry["needs_human"] = outcome["needs_human"]

OUT.write_text(
    json.dumps(
        {
            "tickets": by_ticket,
            "cash_end": cash["balance"],
            "payments": payments,
            "approvals": approvals,
            "passes": max((len(e["runs"]) for e in by_ticket.values()), default=0),
        },
        indent=2,
    )
    + "\n"
)

for ticket_id in sorted(by_ticket):
    e = by_ticket[ticket_id]
    print(f"ticket {ticket_id}: {len(e['runs'])} runs, status {e['final_status']}")
    print(f"   agents     : {', '.join(e['agents'])}")
    print(f"   delegations: {'; '.join(f'{a} -> {b}' for a, b in e['delegations'])}")
    print(f"   tools      : {e['tools']}")
    if e["refusals"]:
        print(f"   refusals   : {len(e['refusals'])}")
print(f"\ncash at end: {cash['balance']}")
print(f"written: {OUT.relative_to(ROOT)}")
