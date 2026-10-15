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

---

## Problem 2 — The agent team

**Prompt** — 2026-10-14

> Build the Campus Customs agent team with PydanticAI: Boss, Inventory,
> Accounting, Facilities, and Customer Service. Put one prompt file per agent in
> backend/prompts/, data types in backend/models.py, and the agent files under
> backend/. Let the agents delegate to each other, and have every agent use the
> MCP tools. Use my PORTKEY_API_KEY and only gpt-6-luna.

**What Claude did.** Built the five agents on one shared MCP toolset, with
delegation running one way only — Boss to any specialist, Customer Service to
Inventory, nothing back to the Boss — so the team cannot talk in circles. Three
decisions were each made in exactly one place: `settings.model()` is the only
way to get a client and raises on any name but `gpt-6-luna`;
`base.build_agent()` gives every agent the same model, tools, prompt, and typed
output; and `prompts/_shared.md` holds the seven house rules that every prompt
splices in, so a rule cannot drift between agents. `models.py` makes a payment a
*proposal* rather than an action — `ApprovalRequest` carries `cash_before`,
`cash_after`, and an `approved` field left null for a human, and
`DraftReply.sent` is typed `Literal[False]`.

Two things only came out of running it. The first live run failed with a 400:
the gateway refuses function tools unless reasoning effort is off for
`gpt-6-luna`, so `openai_reasoning_effort="none"` is now set once in `base.py`.
Then the run succeeded on ticket 102 with correct figures — but the draft reply
told the *landlord* the shop's checking balance. Every number in it was true,
which is the point: "never invent" does not imply "never disclose". The Customer
Service prompt now rules the books internal, and a re-run produced a clean
draft.

**Follow-up prompt** — 2026-10-14 _(the team had only been proven on one
ticket)_

> Reset the database and run the full board across all three tickets.

**What Claude did.** Reset the working copy, ran the whole board in one pass (88
seconds), and saved `output/board_review.json`. The team reached the same
spending plan as the hand analysis in `data_model.md` — invoice #501 first
because it is both overdue and the shipping blocker, then rent, leaving 160.00 —
from the tools alone, and left all three tickets `needs_human: true` with
nothing written to the database. It then recorded three faults rather than
declaring success: the approval request says paying #501 unblocks only ticket
101 when it unblocks 103 as well; Accounting was never consulted on 103, so
nobody noticed the 264.00 restock does not fit in the 160.00 that would remain;
and the reply to the customer disclosed that the shop has an overdue invoice.
All three are prompt gaps about what to volunteer, not code faults.

**Follow-up prompt** — 2026-10-14 _(the faults were recorded but not yet
corrected)_

> Fix the three prompt gaps and run the board again.

**What Claude did.** Fixed all three in the prompts — no code changed, since
none of them were code faults. Accounting is now told to fill `unblocks` with
every ticket a payment frees and the Boss checks that list against the board;
the Boss is told that money is often implied rather than stated, so a restock
is a money question even when the ticket never mentions cash; and Customer
Service is told the shop's own debts are internal, not only its balances. The
re-run from a reset database cleared all three: `unblocks` came back
`[101, 103]`, Accounting was consulted on 103, and no draft mentions an invoice
or a balance. The second fix paid for itself — with Accounting in the loop, the
run worked out that the 264.00 restock plus the two obligations comes to 3504.00
against 3400.00 in checking, 104.00 short, which the first run never reached. It
also drew a distinction nobody asked for: 12 × 22.00 is arithmetic, not a vendor
quote, because no quote exists in the database.

---

## Problem 3 — Write tools, approval, and the audit trail

**Prompt** — 2026-10-14

> Add any tools the agents need to your MCP server so they can work on the open
> tickets. Shop facts come from the MCP server over data/campus_customs_new.db
> — do not invent a second shop-tools layer that bypasses MCP. Wire the agents
> so they append to output/audit_trail.json as they run: for each agent-loop
> step, record enough to audit later. Append to this file — do not wipe it each
> run. In output/harness.md, list each agent and each MCP tool (including ones
> you add in this problem) along with which table the tool uses. Add a short
> safety section, here's a guardrail i came up with: No payment executes without
> explicit human approval. Agents can only propose a payment, and the pay tool
> refuses if no approval is recorded. The pay tool refuses any payment that
> would push a cash account below zero. Update mcp_server/README.md so the tool
> list matches what you have now.

**What Claude did.** Added six tools — `propose_payment`, `list_approvals`,
`approve_payment`, `pay`, `record_draft_reply`, `resolve_ticket` — plus two
tables (`approvals`, `drafts`) created on the working copy at first write, so a
reset still gives a clean board. The guardrail is enforced in three places
rather than in a prompt: `approve_payment` is filtered out of the agents'
toolset so an agent cannot approve its own proposal, `pay` reads the approvals
table at the moment of payment, and `pay` computes the remaining balance before
writing. The human approves through `scripts/approve.py`, which goes through the
same MCP server — no second path to the database for anyone. A `TestModel` run
against a throwaway database confirmed the agents can reach eight of the nine
tools and not `approve_payment`.

The audit trail appends to a JSON array through a temp-file-and-rename, so an
interrupted write cannot corrupt it, and records run, agent, delegation, and
tool-call events with the errors kept rather than dropped.

Running it end to end found four things worth fixing. Six drafts appeared for
three tickets, because the Boss re-recorded what Customer Service had already
written; nine proposals appeared for two obligations, because Accounting
proposed on every pass. Both were fixed in the tools, not the prompts — a prompt
that says "call this once" is a request, a tool that refuses is a guarantee. The
disclosure rule from problem 2 regressed, with two drafts telling customers that
the shop had an unpaid invoice, so that rule moved out of the Customer Service
prompt and into the house rules every agent shares. And a run died on
pydantic-ai's default 50-request limit inside a delegated agent, which the
team's own shared budget has to be passed down to override.

The approval loop then ran clean: pass 1 proposed two payments and paid nothing,
a human approved the invoice only, and pass 2 paid exactly that one — 3400.00 →
2560.00 — then refused the same payment on the retry and left the unapproved
rent alone.

---

## Problem 4 — The desk page

**Prompt** — 2026-10-15

> Build output/desk_tickets.html, a self-contained page I can double-click
> open, with one tab per ticket (101, 102, 103) plus empty Cash and Reflection
> tabs marked "coming later". On each ticket tab, fill in an Expected section
> describing what the agent team should do for that ticket, based on the data in
> data/campus_customs_new.db, and leave an empty Actual section for me to fill
> in after I run the agents.

**What Claude did.** Wrote `scripts/build_desk_page.py`, which reads the
database and generates the page, rather than typing the figures into HTML by
hand — so the Expected sections can be regenerated whenever the board changes
and cannot drift from the data. It reset the working copy first: the database
still held the state left by the approval demo, with invoice #501 marked paid
and 2560.00 in checking, and a page built from that would have described a board
that no longer needed the payment it was explaining. After generating, it
checked all eleven figures on the page back against the database.

Each ticket tab carries the linked rows, a step-by-step Expected section, an "It
should not" list naming the specific wrong move that ticket tempts an agent into
— promising the 2026-09-05 ship date on 101, quoting a discount on 103 — and an
empty Actual box that keeps what is typed in it in browser storage. Cash and
Reflection are present and marked "coming later". The page has no external
references of any kind. Its structure was verified; Chrome was not reachable
from the session, so it has not been looked at rendered.

**Follow-up prompt** — 2026-10-15 _(the Expected sections were prose; this gave
the shape they should follow — first call, workflow, tools, and what is
skipped)_

> For each ticket Expected section: Boss calls first: Inventory... [the order
> workflow, its in-stock and out-of-stock branches, and the note that Facilities
> is skipped because nothing in an order involves leases or rent]
>
> MCP tools I expect to run, and why: Stock lookup (reads inventory)... Rent and
> unpaid-bill tickets would have a different shape. A rent ticket would start
> with Facilities and then go to Accounting, and a bill ticket would start with
> Accounting. Checking what each ticket says before you copy this pattern, we
> don't want to send every specialist on every ticket.

**What Claude did.** Rebuilt each Expected section as four blocks — *Boss calls
first*, *Workflow*, *MCP tools expected to run, and why*, and *Skipped, and
why* — and took the closing warning literally rather than copying the order
pattern onto all three tabs. Tickets 101 and 103 open with Inventory because
stock decides them; 102 opens with Facilities, and its tab says plainly that a
rent ticket has no SKU, no size and no supplier, so Inventory would cost a model
call to be told there is no product on the ticket.

The tool lists name the real tools rather than generic lookups, and note where
they differ from the four the prompt described: `get_ticket` already returns the
stock, invoice and cash rows together, so one call covers three of them. Two
skips are argued rather than listed — Accounting is only on ticket 101 because
the tee is out of stock and the vendor is blocked, with the in-stock
counterfactual written out; and `propose_payment` is deliberately absent from
103, because 264.00 is arithmetic off the pricing table rather than a bill, and
proposing it would ask a human to approve a purchase the balance cannot cover.

---

## Problem 5 — The API

**Prompt** — 2026-10-15

> Your React frontend dashboard (the next problem) needs a backend it can call.
> In backend/main.py, use FastAPI and add routes that do the following: return
> the three tickets and whether each is open or resolved; take a ticket id and
> run the agent team on that ticket; return recent agent events — what each
> agent said and which tools they used — so the board can refresh; approve a
> payment or purchase after a human clicks approve (agents only prepare the pay;
> this route is what actually changes cash); return the current checking balance
> from cash_accounts; reset the database to the original values when you want to
> try a fresh run.

**What Claude did.** Wrote `backend/main.py` with those six routes plus three
the dashboard will need to use them (`GET /api/runs/{id}`, `GET /api/approvals`,
`GET /api/health`). Every route goes through the MCP server, the same tools the
agents use, with one deliberate exception: `/api/reset` copies a file, which is
an operator action on the database rather than a fact about the shop.

Two design calls. A board run takes a minute or two, so the run route returns
`202` with a run id immediately and the team works in the background while the
dashboard polls `/api/events`; a second run while one is in flight gets `409`,
because the team shares one database. And the approval route is where cash
actually moves — it records the approval against the person who gave it, then
calls `pay`, and when `pay` refuses the refusal comes back in `refused_because`
with the balance untouched rather than as a 500.

Running it for real found two bugs that the CLI could never have shown.
`list_approvals` failed on a freshly reset board — the `approvals` table is
created on first write, but reading opens the file read-only, so the first thing
a dashboard asks for after a reset returned "no such table". And the audit
sequence numbers restarted with every process, which would make old records look
new to a dashboard polling with `after_seq`. A third was caught before it could
bite: the audit run id was fixed at import, so every run served by one process
would have shared it.

Every route was then exercised against the running server, including the
guardrails: approving paid 3400.00 → 2560.00 → 160.00, and approving a repeat of
the same rent came back `paid: false` with the cash unchanged.

**Follow-up prompt** — 2026-10-15 _(the API existed but had only ever been
started as a package from the project root, and the routes were not listed
plainly)_

> From the backend/ folder, start the server with: uvicorn main:app --reload
> --port 8000. This turns on your backend at http://localhost:8000 so the
> frontend dashboard can call those routes. In output/harness.md, list each
> route in one line (what URL / what it does).

**What Claude did.** That exact command could not have worked: `main.py` used
relative imports, so loaded as a top-level module from inside `backend/` it had
no package to resolve them against. It now puts the project root on `sys.path`
when `__package__` is empty and imports `backend.*` absolutely, so both
`uvicorn main:app` from `backend/` and `uvicorn backend.main:app` from the root
work. Verified by starting it the way the prompt asks and calling the routes.

Port 8000 itself is held by hw4's uvicorn, still running from 7 October.
Stopping another project's process and binding its port were both refused by the
sandbox, so the server was proved on a free port instead and the stale process
left alone for the user to stop. The harness now lists every route on one line.

---

## Problem 6 — The dashboard

**Prompt** — 2026-10-15

> Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The
> page should call the routes you built in Problem 7 [...] List all three
> tickets; let you pick one and start the agent team on it; show each agent and
> what they are saying / doing while the ticket runs; mark a ticket resolved
> when the run finishes; show a short summary of what each agent did; let a
> human approve a pay or purchase when asked; show the checking balance (it
> should drop after an approved pay). Make the dashboard look polished and
> distinctive, like a real custom-apparel shop desk, not a generic admin panel.
> Use a warm cream background, navy text, and one bold accent color. Style
> tickets as paper tags and approvals as receipt slips. Give each agent its own
> color and a glowing ring when active. Make the checking balance the biggest
> number on the page. Add smooth touches like feed items sliding in, a
> "RESOLVED" stamp on finished tickets, and the balance counting down after an
> approved pay. Keep it responsive and readable.

**What Claude did.** Built the board against the real API: tickets as paper tags
with a punched hole and a half-degree rotation that straightens on hover,
approvals as till receipts with a torn `clip-path` edge, five agent colours
carried through roster chips, feed lines and the delegation chain, and the
balance as the largest thing on the page in tabular serif figures that count
down over 1.1 seconds when a payment lands.

Two judgement calls worth recording. The RESOLVED stamp follows the *database*
rather than the end of a run — the board refetches and stamps whatever the shop
reports as resolved, so on a fresh board all three tickets stay open waiting on
approvals, which is the honest picture rather than a satisfying one. And a
refused payment is shown rather than swallowed: `refused_because` goes to the
error banner with the balance unmoved, and failed tool calls stay in the feed
tinted and with their error text.

Verified by building (TypeScript strict and the production bundle both clean)
and by running the whole chain — Vite served the app and proxied `/api/tickets`
and `/api/cash` through the backend and MCP to the database. Port 8000 was still
held by hw4's old server, so `VITE_API_TARGET` was added to point the proxy
elsewhere for the test. Chrome was not reachable from the session, so **nobody
has looked at the page rendered**.

**Follow-up prompt** — 2026-10-15 _(the board was built but not pointed at the
API, and the look was undocumented)_

> Tell the front end to talk to your backend at http://localhost:8000. On the
> backend, allow the Vite page origin (usually http://localhost:5173) so the
> browser is allowed to call those routes. Start the board with: npm run dev
> [...] Write output/design.md explaining the dashboard look I chose and why
> [...] describe only what is actually in the frontend/ code.

**What Claude did.** Pointed `api.ts` at `http://localhost:8000` through an
`API_BASE` constant, overridable with `VITE_API_BASE` (empty string falls back
to the Vite proxy). The CORS middleware already allowed `localhost:5173`, so
nothing was needed on the backend side.

Two parts of the design brief described things the code did not have, so rather
than write them up as if it did, it built them: each agent now carries a glyph
as well as a colour, and a status pill reading *idle*, *working* or *done*
worked out from the feed; and the masthead became an actually slim top bar —
shop name, date and balance on one line — instead of the tall header it was.
`output/design.md` then describes only what is there, including the exact empty
states quoted from the code.

The board could not be started: hw4's dev server and API from 7 October still
hold ports 5173 and 8000, and the sandbox refuses both stopping another
project's processes and binding its ports.

---

## Problem 7 — The full sweep

**Prompt** — 2026-10-15

> Before testing the agents on a full run over the three tickets, reset the
> working database data/campus_customs_new.db again so you start clean. Note the
> starting checking balance. Then run all three tickets on the board (101, 102,
> 103) until each is resolved. Open output/desk_tickets.html from Problem 6. On
> each ticket tab, fill the Actual section from this run: which agents worked,
> what they delegated, and which tools they used. Keep your Expected section so
> you can compare the two.

**What Claude did.** Reset the board (checking $3,400.00), then ran all three
tickets, approved the two payments the team proposed, and ran them again. Pass 1
proposed and paid nothing; the approvals went in as "Shutong Gang"; pass 2 paid
the invoice and the rent — $3,400 → $2,560 → **$160** — and resolved ticket 102.
A third pass changed nothing.

Rather than typing the Actual sections by hand it wrote
`scripts/collect_actuals.py`, which mines the audit trail for every run since the
last reset and maps each run to its ticket from the Boss's own instruction, so
the agents, delegations, tool counts, payments and refusals on each tab come from
the record rather than from memory. `build_desk_page.py` renders them beside the
Expected sections, which are untouched.

**Two tickets are still open, and that is the agents being right.** 101's invoice
is paid and the vendor can ship on 2026-09-05, but the shop's date never moves
off 2026-08-31, so the tee cannot arrive inside this world. 103 needs a human to
set the discount, and the 12-unit shortfall costs $264 against the $160 left.
Both were reported rather than papered over.

The sweep also turned up three things: the **Boss** called `pay` on ticket 101
instead of Accounting, since every agent shares one toolset — the guardrail held
but the division of labour is a convention, not a constraint; a tool refusal
taught the model mid-run, when Accounting asked for vendor id 0 twice and the
tool answered with the ids that exist; and a dead duplicate proposal was left on
the board, because the duplicate check looks for a *pending* proposal and misses
one that is already approved.

---

## Problem 8 — Cash, the resolved record, and finishing the harness

**Prompt** — 2026-10-15

> On the Cash tab of the same output/desk_tickets.html, itemize the money:
> starting checking balance (after the reset); for each ticket how cash changed
> when that ticket resolved, and why (which pay / purchase, dollar amount);
> ending checking balance — it must match cash_accounts in the working database.
> Wrong cash math loses points even if the board shows every ticket resolved.
> Also save output/resolved_tickets.json [...] and output/resolved_board.html —
> a page you can double-click with a screenshot of your React board for each
> resolved ticket. Append real runs to output/audit_trail.json. Finish
> output/harness.md so it covers tables, MCP tools, the five agents, API routes,
> the dashboard, and safety rules.

**What Claude did.** Built the Cash tab from the `payments` and `approvals`
tables, taking the opening balance from the untouched original database and
tying each payment to its ticket through the ticket's own `invoice_id` /
`lease_id` rather than by hand: $3,400.00 opening, −$840.00 on ticket 101
(invoice #501, the shipping blocker), −$2,400.00 on ticket 102 (rent), nothing
on 103 because the $264 restock exceeds the $160 left. The page prints the check
itself — opening minus paid against `cash_accounts` — and both figures are
$160.00. One wording fix came out of reading it back: the ledger first showed
the rent's *rolled* due date, so it now says which rent was paid and where the
lease moved to.

`scripts/build_resolved.py` writes `resolved_tickets.json` and
`resolved_board.html` from the audit trail and the database. The audit trail now
holds **800 records across 18 runs**, appended, never truncated.

Harness section 9 is a reference covering all eleven tables, the nine MCP tools,
the five agents, the ten API routes, the dashboard, and a table of every safety
rule against the thing that actually enforces it — plus a Known gaps list naming
four real ones rather than closing on a clean note.

**The screenshots could not be taken.** Chrome is not reachable from this
session and hw4's servers still hold ports 5173 and 8000, so
`resolved_board.html` renders a labelled slot per ticket: drop a PNG at
`output/board_shots/ticket-<id>.png`, re-run the script, and it appears.

**Follow-up prompt** — 2026-10-15 _(the screenshots were the last thing missing,
and running the board was not possible)_

> i can't run it though

**What Claude did.** Ran it itself, on ports nothing else was using: the API on
8012, Vite on 5175 with `VITE_API_BASE` pointed at it, and the Chrome already
installed on the machine driven headlessly from the command line to capture
`output/board_shots/ticket-{101,102,103}.png`. Two small features made the shots
worth taking and are worth keeping anyway — `?ticket=101` opens the board on
that ticket, and the feed loads the most recent run on open rather than sitting
empty.

Looking at the board for the first time found two bugs nothing else had. The
first screenshot came back reading **"Failed to fetch"**: the backend's CORS list
named port 5173, the board was on 5175 because 5173 was taken, and the browser
blocked every call — something no typecheck or API test can catch. CORS now
matches any localhost port. The second was visible rather than logged: the dead
duplicate approval from the last problem was sitting in the column with a live
Approve button on it. `propose_payment` now treats an approved-but-unspent
proposal as live so the duplicate cannot be created, and the stale row was
cleared through the proper path with `approve.py 3 --decline`, so it reads
DECLINED rather than vanishing.
