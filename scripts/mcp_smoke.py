"""Smoke-test the three MCP tools and save the evidence.

Starts the server exactly as a client would — as a subprocess over stdio, using
the command in the project's `.mcp.json` — calls each tool, and checks every
value it returns against `data/campus_customs_new.db` read independently with
sqlite3. Writes `output/mcp_smoke.json` and exits non-zero on any mismatch.

    ./.venv/bin/python scripts/mcp_smoke.py "<the prompt that asked for this>"
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
MCP_JSON = ROOT / ".mcp.json"
OUT = ROOT / "output" / "mcp_smoke.json"

PROMPT = sys.argv[1] if len(sys.argv) > 1 else "(prompt not supplied)"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def db_rows(sql: str, params: tuple = ()) -> list[dict]:
    """Read the database independently of the server's own code path."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def db_one(sql: str, params: tuple = ()):
    rows = db_rows(sql, params)
    return rows[0] if rows else None


def client_config() -> dict:
    """The committed .mcp.json, with the relative command resolved."""
    config = json.loads(MCP_JSON.read_text())
    entry = config["mcpServers"]["campus-customs"]
    # Make the relative command absolute without resolve(): .venv/bin/python is
    # a symlink to the system interpreter, and following it lands on a Python
    # that has no fastmcp installed.
    entry["command"] = str(ROOT / entry["command"])
    entry["cwd"] = str(ROOT)
    return config


def payload(result) -> dict:
    return result.structured_content or json.loads(result.content[0].text)


class Checks:
    """Collects tool-value vs database-value comparisons."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def expect(self, name: str, tool_value, db_value) -> None:
        self.items.append(
            {
                "check": name,
                "tool_value": tool_value,
                "db_value": db_value,
                "match": tool_value == db_value,
            }
        )

    @property
    def all_match(self) -> bool:
        return all(c["match"] for c in self.items)


async def main() -> int:
    today = db_one("SELECT date_today FROM desk")["date_today"]
    tests = []

    async with Client(client_config()) as client:
        advertised = sorted(t.name for t in await client.list_tools())

        # ---- 1. list_tickets -------------------------------------------------
        args = {"status": "open"}
        out = payload(await client.call_tool("list_tickets", args))
        c = Checks()
        c.expect("today is desk.date_today", out["today"], today)
        open_rows = db_rows("SELECT * FROM tickets WHERE status='open' ORDER BY id")
        c.expect("open ticket count", out["count"], len(open_rows))
        c.expect(
            "ticket ids",
            [t["id"] for t in out["tickets"]],
            [r["id"] for r in open_rows],
        )
        c.expect("every ticket row matches the table", out["tickets"], open_rows)
        tests.append(
            {
                "test": 1,
                "prompt": PROMPT,
                "tool": "list_tickets",
                "arguments": args,
                "tool_output": out,
                "database_checks": c.items,
                "passed": c.all_match,
            }
        )

        # ---- 2. get_ticket ---------------------------------------------------
        args = {"ticket_id": 101}
        out = payload(await client.call_tool("get_ticket", args))
        c = Checks()
        c.expect("today is desk.date_today", out["today"], today)
        c.expect(
            "ticket row",
            out["ticket"],
            db_one("SELECT * FROM tickets WHERE id=101"),
        )
        c.expect(
            "pricing row for the ticket's sku",
            out["pricing"],
            db_one("SELECT * FROM pricing WHERE sku='CC-TEE-WHITE'"),
        )
        on_hand = db_one(
            "SELECT qty FROM inventory WHERE sku='CC-TEE-WHITE' AND size='S'"
        )["qty"]
        c.expect("on_hand for the size requested", out["on_hand"], on_hand)
        c.expect("short_by = qty wanted - on_hand", out["short_by"], 1 - on_hand)
        invoice = db_one("SELECT * FROM invoices WHERE id=501")
        c.expect("invoice amount", out["invoice"]["amount"], invoice["amount"])
        c.expect("invoice status", out["invoice"]["status"], invoice["status"])
        c.expect("invoice due date", out["invoice"]["due_date"], invoice["due_date"])
        c.expect(
            "days_overdue = today - due_date",
            out["invoice"]["days_overdue"],
            (date.fromisoformat(today) - date.fromisoformat(invoice["due_date"])).days,
        )
        c.expect(
            "vendor behind the invoice",
            out["invoice"]["vendor"],
            db_one("SELECT * FROM vendors WHERE id=?", (invoice["vendor_id"],)),
        )
        c.expect(
            "cash accounts",
            out["cash_accounts"],
            db_rows("SELECT * FROM cash_accounts ORDER BY name"),
        )
        tests.append(
            {
                "test": 2,
                "prompt": PROMPT,
                "tool": "get_ticket",
                "arguments": args,
                "tool_output": out,
                "database_checks": c.items,
                "passed": c.all_match,
            }
        )

        # ---- 3. get_vendor_status -------------------------------------------
        args = {"vendor_id": 1}
        out = payload(await client.call_tool("get_vendor_status", args))
        c = Checks()
        vendor = db_one("SELECT * FROM vendors WHERE id=1")
        open_invoices = db_rows(
            "SELECT * FROM invoices WHERE vendor_id=1 AND status='open' ORDER BY due_date"
        )
        c.expect("today is desk.date_today", out["today"], today)
        c.expect("vendor row", out["vendor"], vendor)
        c.expect("lead_days from the vendors table", out["lead_days"], vendor["lead_days"])
        c.expect(
            "open invoice ids",
            [i["id"] for i in out["open_invoices"]],
            [i["id"] for i in open_invoices],
        )
        c.expect(
            "open invoice total",
            out["open_invoice_total"],
            round(sum(i["amount"] for i in open_invoices), 2),
        )
        c.expect("can_ship is false while an invoice is open", out["can_ship"], not open_invoices)
        c.expect(
            "earliest ship date = today + lead_days",
            out["earliest_ship_date_if_ordered_today"],
            (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat(),
        )
        tests.append(
            {
                "test": 3,
                "prompt": PROMPT,
                "tool": "get_vendor_status",
                "arguments": args,
                "tool_output": out,
                "database_checks": c.items,
                "passed": c.all_match,
            }
        )

    digest_before = sha256(DB)
    evidence = {
        "server": {
            "name": "campus-customs",
            "config": ".mcp.json",
            "command": " ".join(
                [json.loads(MCP_JSON.read_text())["mcpServers"]["campus-customs"]["command"]]
                + json.loads(MCP_JSON.read_text())["mcpServers"]["campus-customs"]["args"]
            ),
            "transport": "stdio (server run as a subprocess, as a client runs it)",
            "tools_advertised": advertised,
        },
        "database": {
            "path": "data/campus_customs_new.db",
            "sha256": digest_before,
            "opened": "read-only; every check re-read the file with its own sqlite3 connection",
        },
        "shop_date": today,
        "tests": tests,
        "summary": {
            "tools_tested": [t["tool"] for t in tests],
            "checks_run": sum(len(t["database_checks"]) for t in tests),
            "checks_passed": sum(
                1 for t in tests for c in t["database_checks"] if c["match"]
            ),
            "all_passed": all(t["passed"] for t in tests),
        },
    }

    OUT.write_text(json.dumps(evidence, indent=2) + "\n")

    s = evidence["summary"]
    for t in tests:
        mark = "PASS" if t["passed"] else "FAIL"
        print(f"{mark}  {t['tool']}({t['arguments']}) — {len(t['database_checks'])} checks")
        for check in t["database_checks"]:
            if not check["match"]:
                print(f"      mismatch: {check['check']}")
                print(f"        tool: {check['tool_value']!r}")
                print(f"        db:   {check['db_value']!r}")
    print(f"\n{s['checks_passed']}/{s['checks_run']} checks passed")
    print(f"database sha256 unchanged by the run: {sha256(DB) == digest_before}")
    print(f"evidence: {OUT.relative_to(ROOT)}")
    return 0 if s["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
