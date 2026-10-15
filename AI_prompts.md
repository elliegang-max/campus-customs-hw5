# AI Prompt Log — hw5

A log of the prompts I typed into Claude while working on this assignment, in my
own words, organised by problem.

**Convention — one section per problem.** Each section carries:

1. the problem number and title;
2. at least one prompt I typed, quoted verbatim in my own words, with the date;
3. a follow-up prompt where the first one did not get me what I needed, with one
   sentence on what was lacking after the first.

A short note on what Claude did follows each prompt. Sections are numbered to
match the problems in the assignment; everything typed before the problem list
arrived sits in Problem 1 below. Sections are filled in as the assignment
progresses, and nothing is rewritten after the fact.

---

## Problem 1 — Project setup

**Prompt** — 2026-10-14

> start a hw5 folder

**What Claude did.** Created the `hw5` scaffold matching the hw3/hw4 conventions
(`.gitignore`, `.env.example`, `AI_prompts.md`, `output/`, `prompts/`, `data/`,
`requirements.txt`, `README.md`) and initialised a git repo with a first commit.
No assignment brief existed anywhere under `AI Foundation/`, so it asked for the
hw5 problems rather than guessing at application code.

**Follow-up prompt** — 2026-10-14 _(the first prompt only said where to work,
not what to do — the data still had to be unpacked)_ _(with
`~/Desktop/data-2.zip` attached)_

> unzip so you have data/campus_customs.db

**What Claude did.** Extracted the archive into an isolated scratch directory
first (the zip's root is `data-2/`, not `data/`, and it carried `__MACOSX/`
resource-fork noise, which was excluded), checked that it held only `.jpg` and
`.db` files, then moved `campus_customs.db` and `products/` into `hw5/data/`.
The database has four tables — `catalogue` (102 products), `inventory` (612 size
rows), `users` (3), `chat_messages` (22) — and every `image_file_path` in the
catalogue resolves to a file in `data/products/` (102 images). Added `data/` to
`.gitignore` so the pack stays local, matching hw4.

**Follow-up prompt** — 2026-10-14 _(the data pack was in place, but nothing said
which copy of the database the tools should write to)_

> That file is the original shop database. Tables include desk, tickets,
> inventory, pricing, vendors, leases, cash_accounts, payments, and invoices.
> Your tools will update the database as tickets get resolved. Make a copy of the
> database file called data/campus_customs_new.db and point your MCP server and
> backend at that working copy. Keep campus_customs.db untouched so you can reset
> when you want to restart resolving the tickets.

**What Claude did.** Copied the database to `data/campus_customs_new.db`, made
the original read-only so nothing can write to it by accident, added
`scripts/reset_db.sh` to restore the working copy from the original, and wrote
the convention into the README so the MCP server and backend (not yet built)
point at the working copy. It also flagged a mismatch: the database unpacked
from `data-2.zip` holds `catalogue`, `inventory`, `users`, and `chat_messages` —
the hw4 storefront schema — and none of the `desk` / `tickets` / `vendors` /
`leases` / `cash_accounts` / `payments` / `invoices` tables described above, so
the hw5 data pack still has to be supplied.

**Follow-up prompt** — 2026-10-14 _(the rules of the shop, given before the
problem list)_

> Rules of this shop
>
> * The field `desk.date_today` is "today" for the shop. Use this date to
>   determine what is overdue.
> * Vendor lead times come from the `vendors` table.
> * A vendor will not ship new product while they still have an open unpaid
>   invoice.
> * Human approval is required for any payments. Points will be deducted if this
>   is not done. If payment is made, make sure to update the relevant table.
> * If there is not enough cash, the pay tool must refuse — no negative balances.
> * Cash only goes out in this homework — we did not model revenue, so no money
>   comes in.
> * Before a full run to resolve the tickets, make sure to reset the database to
>   the original values.
> * Do not email customers or call real vendors. Drafts stay on the board.
>
> Use your `PORTKEY_API_KEY` for AI calls. For this assignment, use only
> `gpt-6-luna` through Portkey for every agent. Multi-agent chats burn tokens
> fast. Points will be deducted if any other model shows up in your code or runs.

**What Claude did.** Wrote the rules into `RULES.md` — grouped as shop, money,
running, and models — and linked it from the README so every tool and agent is
built against one list rather than against memory of a chat message. It also
checked where the Portkey credentials come from: `~/.config/ai-keys/keys.env`
already has both `PORTKEY_API_KEY` and `PORTKEY_BASE_URL`, so no local `.env` is
needed, and recorded that resolution order in `RULES.md`. No code yet — the hw5
data pack and the problem list are still to come.

**Follow-up prompt** — 2026-10-14 _(asking for the log that was already being
kept — the earlier prompts had not said to keep one, so this confirmed the
convention rather than starting it)_

> Create AI_prompts.md in the project root. Keep it updated with when i give you
> prompts as we work

**What Claude did.** The file already existed at the project root, created with
the scaffold and carrying all four prompts up to this point, so nothing was
recreated. It dated every entry (the follow-ups had carried only the note on
what was lacking, not the date) and wrote the date into the convention at the
top. From here each prompt is appended as it arrives, with its date and a note
on what followed; nothing earlier is rewritten.

**Follow-up prompt** — 2026-10-14 _(the previous prompt asked for the log but
not for its shape — this one gave the required structure)_

> In AI_prompts.md, add one section per problem. Each section should have The
> problem number and title, At least one prompt you typed, in your own words as
> much as possible, One follow-up prompt if you needed it (and one sentence on
> what was lacking after the first)

**What Claude did.** The file already worked this way, so it rewrote the
convention at the top as the three numbered requirements rather than a
paragraph, and said that section numbers track the assignment's problems. Only
one section exists so far — the hw5 problem list has not arrived, so everything
typed to this point is project setup. A new section goes in as each problem
starts.

**Follow-up prompt** — 2026-10-14 _(the data pack that had been promised, now
with the questions to answer about it)_

> Open data/campus_customs.db and show me every table and its fields. Copy it to
> data/campus_customs_new.db as the working copy. help me understand the three
> open tickets and how they link to the other tables.

**What Claude did.** The database in `data/` was still the hw4 storefront one,
so it looked for the real pack and found it already unzipped at
`~/Downloads/data-2/campus_customs.db` with the nine tables described in the
brief. It installed that as the project original (the hw4 copy it replaced is
still recoverable from `~/Desktop/data-2.zip`), kept it read-only, and
regenerated the working copy. Then it dumped every table and all 21 rows and
wrote `output/data_model.md`: field-by-field tables, a map of how `tickets`
links through `sku`/`size`, `lease_id`, and `invoice_id`, and a walkthrough of
the three open tickets. The finding that mattered: tickets 101 and 103 both
queue behind one $840 invoice that is 3 days overdue, and with $3,400 in
checking the invoice and the $2,400 rent fit together with $160 to spare — so
the 12-hoodie restock ticket 103 needs cannot be paid for this week.

**Follow-up prompt** — 2026-10-14 _(the walkthrough existed, but the assignment
wants a running write-up that grows problem by problem)_

> Start output/harness.md. For each table, list the fields and one short line on
> why that table matters for the agent. let's keep growing this harness file as
> we work along through the problems.

**What Claude did.** Created `output/harness.md` in the same shape as the hw3
and hw4 harness files: a header fixing the setup that applies to every section
(Portkey, `gpt-6-luna` only, the original-versus-working-copy split), then
section 1 on the database — every table with its fields and a short *why it
matters to the agent* line, ending on the three things the schema does not
enforce and the tools therefore must. The convention is written into the header:
one numbered section per problem, appended in order, earlier sections left as
written.

**Follow-up prompt** — 2026-10-14 _(the first build step: the tools every agent
will share)_

> Write an MCP server in mcp_server/ using FastMCP that will talk to
> data/campus_customs_new.db. You don't need to connect or run it yet. just so
> you know every agent in this hw uses the tools in this MCP server. We will add
> more tools to it later. for now write three tools you know you will need for
> the tickets in the database. Keep the names clear. Never invent any data, only
> use information in the database.

**What Claude did.** Wrote `mcp_server/` as three files rather than one:
`server.py` (the FastMCP instance and tool docstrings, which are what the agent
actually reads), `queries.py` (the SQL as plain functions), and `db.py`
(connections). The split meant the SQL could be run against the real database
and checked before any agent or MCP client existed — neither FastMCP package was
installed. Two rules went into `db.py` so they hold for every tool ever added:
tools open the working copy, never the original, and read tools open it
read-only so a SELECT-only tool cannot write even by accident. The three tools
are `list_tickets`, `get_ticket`, and `get_vendor_status` — one per question the
agent must ask about any ticket. Unknown ids raise and list the ids that do
exist, so a miss can never look like an empty result worth filling in.

**Follow-up prompt** — 2026-10-14 _(the server existed but nothing tied each
tool to the ticket it exists to unlock)_

> In output/harness.md, list each of the three MCP tools with the table it
> reads, which ticket it helps unlock (101, 102, or 103), and one sentence on
> why it's the right tool for that ticket. Also add a short mcp_server/README.md
> explaining what the server is for, which database file it uses, and the three
> tools.

**What Claude did.** Added section 2.7 to the harness as a tool → tables →
ticket table, with the tables read checked against the SQL in `queries.py`
rather than from memory. Reading down the *Unlocks* column makes the shape of
the board visible: ticket 102 is answered out of the shop's own records, while
101 and 103 both wait on a vendor who will not ship — which is the argument for
`get_vendor_status` being its own tool instead of part of `get_ticket`. It also
noted the deliberate gap: no tool sets the discount ticket 103 asks for, since
that is a human judgement. `mcp_server/README.md` covers the same ground for
someone opening the folder cold — what the server is for, the working-copy
versus original split, and the three tools.

**Follow-up prompt** — 2026-10-14 _(the server was written but nothing could
call it)_

> Add my MCP server in mcp_server/ to this project so you can call its tools.
> Save the connection JSON in .mcp.json at the project root.

**What Claude did.** Created the venv and installed `fastmcp` 4.1.0 (nothing had
been installed until now), then wrote `.mcp.json` pointing at
`./.venv/bin/python -m mcp_server.server`. It dropped its own first draft of the
config: that version passed `CAMPUS_CUSTOMS_DB` as a relative path, which would
break whenever the server was launched from another directory, and `db.py`
already resolves the database from its own file location. Before handing it
over, it ran the server the way a client does — as a subprocess over stdio —
and confirmed all three tools are advertised, that the figures match the
database, and that a raise inside a tool reaches the caller as a readable error
rather than an empty result. Claude Code picks up a new `.mcp.json` when the
project is approved and reloaded, so the tools appear in the next session
rather than this one.

**Follow-up prompt** — 2026-10-14 _(the server was registered but had never been
proven to return the database's own values)_

> test each of your three MCP tools. Save the evidence in output/mcp_smoke.json,
> and for each test include the prompt I asked you, the tool name, and the tool
> output, which must match the values in data/campus_customs_new.db.

**What Claude did.** Wrote `scripts/mcp_smoke.py`, which starts the server as a
subprocess over stdio from the committed `.mcp.json`, calls all three tools, and
checks every value against the database re-read through its own `sqlite3`
connection — 22 comparisons, all passing, each written to
`output/mcp_smoke.json` with the prompt, the tool name and arguments, the full
output, and both values side by side. The run found a real bug on the way:
making the relative command absolute with `Path.resolve()` followed
`.venv/bin/python` through its symlink to the system interpreter, which has no
`fastmcp`, so the server died at startup and the client reported only
"Connection closed". The evidence also records the database's SHA-256 before and
after, showing the read-only tools left it untouched. Note the tools were called
through this client rather than through Claude's own MCP connection, which had
not picked up `.mcp.json` yet in this session.
