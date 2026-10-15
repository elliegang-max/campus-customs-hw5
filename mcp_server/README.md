# `campus-customs` MCP server

The back office of the Campus Customs shop, exposed as MCP tools.

**Every agent in this assignment reaches the shop through this server.** No
agent opens the database itself. That is deliberate: a house rule written into a
prompt is a suggestion that a model may talk itself out of, while a rule written
into a tool holds for every agent that calls it.

## The database it uses

| File | Role |
| --- | --- |
| `data/campus_customs_new.db` | **the working copy — this is what the tools read and write** |
| `data/campus_customs.db` | the pristine original; kept read-only, never opened by a tool |

Set `CAMPUS_CUSTOMS_DB` to point somewhere else (tests). To start the tickets
over from a clean board, run `./scripts/reset_db.sh` from the project root.

Read tools open the file read-only (`file:...?mode=ro`), so a tool that is only
supposed to look cannot write even by mistake — SQLite refuses at the
connection.

## The tools

All three return the shop's own date (`today`, from the `desk` table) with their
results. Overdue is always measured against that date, never the real-world
clock.

### `list_tickets(status="open")`

What is on the board. Returns the tickets with that status — pass `null` for all
of them — alongside `today`.

### `get_ticket(ticket_id)`

One ticket with everything it links to, resolved in a single call. A ticket
reaches the rest of the shop through three nullable columns, and only the ones
it actually has are followed:

- `sku` + `size` → the `pricing` row and the `inventory` rows for that SKU, plus
  `on_hand` and `short_by` for the size requested
- `lease_id` → the lease, with `days_until_due`
- `invoice_id` → the invoice, with `days_overdue` and the vendor behind it

Cash balances come back too, since no decision can exceed them.

### `get_vendor_status(vendor_id)`

Whether a vendor will ship, and how long they take. `lead_days` is read from the
`vendors` table, never assumed. `can_ship` is false while the vendor has any
open unpaid invoice — the house rule that blocks restocks — and `blocked_reason`
names the invoices responsible.

## Never inventing data

Only columns that were read come back; nothing is defaulted or filled in from a
model's own knowledge. An unknown id **raises**, and the error lists the ids
that do exist (`no ticket with id 999; tickets on the board: [101, 102, 103]`) —
a tool that quietly returned nothing would invite the agent to make something
up. The only computed values are date arithmetic and sums over rows just read,
and each is named so it reads as derived: `days_overdue`, `short_by`,
`earliest_ship_date_if_ordered_today`.

## Layout

| File | Holds |
| --- | --- |
| `server.py` | the FastMCP instance and the tool definitions; the docstrings are the agent-facing contract |
| `queries.py` | the SQL behind each tool, as plain functions that can be run without an MCP client |
| `db.py` | connections, path resolution, and the read-only guard |

## Running it

```bash
pip install -r requirements.txt
python -m mcp_server.server
```

Starts on stdio transport. Not wired to an agent yet — the write tools (paying
an invoice, paying rent, resolving a ticket), each behind human approval and
each refusing to overdraw the account, come in later problems.
