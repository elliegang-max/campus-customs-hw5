# Harness Notes — hw5 (Campus Customs back office)

A running write-up of how this assignment is built and why. Sections are added as
the assignment progresses.

**Setup shared by every step:** all model calls go through the Portkey gateway,
authenticated with the `PORTKEY_API_KEY` environment variable. **Every agent uses
`gpt-6-luna` and nothing else** — multi-agent chats burn tokens fast, and any
other model appearing in the code or in a run costs points. Credentials resolve
process env → `./.env` → `~/.config/ai-keys/keys.env`.

**The data.** Everything lives in `data/`:

- `data/campus_customs.db` — the original pack, kept read-only, never written to.
- `data/campus_customs_new.db` — the working copy. The MCP server, the backend,
  and every tool point here; tools write here as tickets get resolved.
- `./scripts/reset_db.sh` restores the working copy from the original before a
  full run.

**How this file grows.** One numbered section per problem, appended in order.
Later sections cover the tools, the agents, approval and safety, and the specs;
earlier sections are not rewritten when later ones land, so the file reads as a
record of how the build actually went rather than a tidied-up summary.

---

## 1. The database

Nine tables, 21 rows. A small hand-built world: one desk, one lease, one cash
account, one open invoice, three vendors, three tickets. The walkthrough of how
the three open tickets chain together is in
[`data_model.md`](data_model.md); this section is the field reference.

### 1.1 `desk` — the shop's clock

| Field | Type | Note |
|---|---|---|
| `date_today` | TEXT | `2026-08-31`. The shop's "today". |
| `notes` | TEXT | Free scratchpad, empty at the start. |

**Why it matters to the agent.** Every overdue judgement is made against this
field, never the system clock — an agent that reaches for the wall clock gets
the answer wrong on every run after the one it was written on.

### 1.2 `tickets` — the work to be done

| Field | Type | Note |
|---|---|---|
| `id` | INTEGER, PK | 101, 102, 103. |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override`. |
| `requester` | TEXT | Who asked — a customer, a landlord, a student org. |
| `subject` | TEXT | One-line summary. |
| `sku` | TEXT, nullable | → `pricing.sku`, `inventory.sku`. |
| `size` | TEXT, nullable | With `sku`, the `inventory` key. |
| `qty` | INTEGER, nullable | Units requested. |
| `lease_id` | INTEGER, nullable | FK → `leases.id`. |
| `invoice_id` | INTEGER, nullable | FK → `invoices.id`. |
| `status` | TEXT | `open` for all three at the start. |
| `notes` | TEXT | The ask, in prose. |
| `created_at` | TEXT | ISO-8601 with offset. |

**Why it matters to the agent.** This is the queue and the routing table at
once: which of `sku`/`lease_id`/`invoice_id` is filled tells the agent what kind
of work it is and which tables to read next. `status` is also the agent's own
output — resolving a ticket means writing back here.

### 1.3 `inventory` — what is on the shelf

| Field | Type | Note |
|---|---|---|
| `sku` | TEXT | PK with `size`. |
| `size` | TEXT | S / M / L / XL / OS. |
| `name` | TEXT | Display name. |
| `qty` | INTEGER | Units on hand. |
| `location` | TEXT | Aisle A–D. |

**Why it matters to the agent.** It answers the first question of any order —
can this be filled from stock at all? Two rows sit at zero, so the honest answer
is often no, and the agent has to say so rather than promise.

### 1.4 `pricing` — cost and list, per SKU

| Field | Type | Note |
|---|---|---|
| `sku` | TEXT, PK | Four SKUs. |
| `unit_cost` | REAL | What the shop pays. |
| `list_price` | REAL | What the shop charges. |

**Why it matters to the agent.** `unit_cost` is the floor under any discount and
the price of any restock; without it a bulk-discount answer is just a guess that
may sell below cost.

### 1.5 `vendors` — who can resupply, and how fast

| Field | Type | Note |
|---|---|---|
| `id` | INTEGER, PK | 1–3. |
| `name` | TEXT | Bulldog Print Co, Elm City Gifts, QuickShip CT. |
| `specialty` | TEXT | apparel reprint / mugs and small goods / local courier. |
| `lead_days` | INTEGER | 5 / 3 / 1. |

**Why it matters to the agent.** Any date the agent promises comes from
`lead_days` here, and `specialty` decides who can even supply the item — apparel
is one vendor only.

### 1.6 `invoices` — what the shop owes vendors

| Field | Type | Note |
|---|---|---|
| `id` | INTEGER, PK | |
| `vendor_id` | INTEGER | FK → `vendors.id`. |
| `amount` | REAL | |
| `due_date` | TEXT | Compared against `desk.date_today`. |
| `status` | TEXT | `open` until paid. |
| `description` | TEXT | What the invoice was for. |

**Why it matters to the agent.** An open invoice is a shipping blocker, not just
a debt: a vendor will not ship new product while one is outstanding, so the
agent must check here before promising any restock.

### 1.7 `leases` — the rent obligation

| Field | Type | Note |
|---|---|---|
| `id` | INTEGER, PK | |
| `space_name` | TEXT | Chapel Street shop. |
| `landlord` | TEXT | Elm City Properties. |
| `monthly_rent` | REAL | 2400.00. |
| `next_due` | TEXT | 2026-09-02. |
| `notes` | TEXT | Empty at the start. |

**Why it matters to the agent.** Rent is the largest single claim on the
account, so it sets the budget every other decision has to fit inside.

### 1.8 `cash_accounts` — the money

| Field | Type | Note |
|---|---|---|
| `name` | TEXT, PK | `checking`. |
| `balance` | REAL | 3400.00 at the start. |
| `date` | TEXT | As-of date. |

**Why it matters to the agent.** The hard ceiling on everything. Cash only goes
out in this shop — no revenue is modelled — so the balance only falls, and the
pay tool must refuse anything that would take it below zero.

### 1.9 `payments` — the record of money leaving

| Field | Type | Note |
|---|---|---|
| `id` | INTEGER, PK | |
| `kind` | TEXT | What was paid — invoice vs rent. |
| `ref_id` | INTEGER | The id in the table `kind` names. |
| `amount` | REAL | |
| `account` | TEXT | → `cash_accounts.name`. |
| `paid_at` | TEXT | |
| `approved_by` | TEXT | Who approved it. |

**Why it matters to the agent.** This is the audit trail and the proof that a
human approved the spend. Empty at the start, so every row in it is something
this system did.

### 1.10 What the schema does not enforce

Three gaps the tools have to close, because SQLite will not:

- **Paying is three writes, not one** — insert into `payments`, flip
  `invoices.status` (or roll the lease's `next_due`), and decrement
  `cash_accounts.balance`. There is no foreign key tying them together, so a
  partial write leaves the books disagreeing with each other.
- **Nothing prevents a negative balance.** `balance` is a plain REAL with no
  CHECK constraint; the refusal lives in the pay tool or nowhere.
- **`payments.kind` + `ref_id` is an unenforced polymorphic pointer.**
  `kind='invoice'` means `ref_id` is an `invoices.id`, `kind='rent'` means a
  `leases.id`. Nothing in the schema says so, so the tool must be consistent.

---

## 2. The MCP server

`mcp_server/` — a FastMCP server named `campus-customs`. **Every agent in this
assignment reaches the shop through these tools; no agent opens the database
itself.** That is what keeps the house rules enforceable: a rule written only in
a prompt is a suggestion, but a rule written into a tool holds for every agent
that calls it.

### 2.1 Three files, so the SQL is testable without a client

| File | Holds |
|---|---|
| `server.py` | the FastMCP instance and the tool definitions — docstrings are the agent-facing contract |
| `queries.py` | the SQL behind each tool, as plain functions |
| `db.py` | connections, path resolution, the read-only guard |

The split exists so the queries can be exercised directly, without installing an
MCP client or standing up a server — which is how the three tools below were
checked against the real data before any agent existed.

### 2.2 Two rules enforced in `db.py`, not in every tool

- **Tools talk to the working copy.** `data/campus_customs_new.db` by default,
  overridable with `CAMPUS_CUSTOMS_DB` for tests. The pristine original is never
  opened by a tool.
- **Read tools open the file read-only** (`file:...?mode=ro`). A SELECT-only
  tool *cannot* write, even by mistake — SQLite refuses at the connection. Tools
  that spend money or resolve a ticket will pass `readonly=False` and carry
  their own approval step.

### 2.3 The three tools

Each answers one question the agent has to ask about every ticket.

**`list_tickets(status="open")` — what needs doing?**
Returns the board plus `today` from the desk, in the same payload. The date
travels with the tickets deliberately: every overdue judgement is made against
`desk.date_today`, and an agent that has to make a second call to learn the date
is an agent that will sometimes skip it and reach for the real-world clock.

**`get_ticket(ticket_id)` — what does this ticket touch?**
Resolves the three nullable link columns in one call, and only the links the
ticket actually has: `sku`+`size` → `pricing` and the `inventory` rows (with
`on_hand` and `short_by` for the size asked for), `lease_id` → the lease with
`days_until_due`, `invoice_id` → the invoice with `days_overdue` and the vendor
behind it. Cash balances come along because no decision can exceed them. Sizes
come back smallest-first rather than alphabetically.

**`get_vendor_status(vendor_id)` — will they ship, and when?**
`lead_days` is read from the `vendors` table, never assumed. `can_ship` is false
while the vendor has any open unpaid invoice — the house rule that blocks
restocks — and `blocked_reason` names the invoices responsible.
`earliest_ship_date_if_ordered_today` is the shop's date plus the vendor's lead
days.

### 2.4 Never inventing data

- Only columns that were read come back. Nothing is defaulted or filled in from
  the model's own knowledge.
- An unknown id **raises**, and the error lists the ids that do exist
  (`no ticket with id 999; tickets on the board: [101, 102, 103]`). A tool that
  quietly returned an empty result would invite the agent to make something up.
- The only computed values are date arithmetic and sums over rows just read, and
  each is named so it reads as derived: `days_overdue`, `short_by`,
  `earliest_ship_date_if_ordered_today`.

### 2.5 What these three tools say about the board today

Running them against the untouched working copy, with no model involved:

| Ticket | What the tools report |
|---|---|
| 101 | `on_hand` 0, `short_by` 1; invoice #501 **3 days overdue**, vendor Bulldog Print Co |
| 102 | lease 1, rent 2400.00, **due in 2 days**; checking holds 3400.00 |
| 103 | `on_hand` 8 of 20, `short_by` 12; cost 22.00 against list 58.00 |
| vendor 1 | `can_ship` **false** — blocked by #501; would otherwise ship by 2026-09-05 |

Tickets 101 and 103 both queue behind the same unpaid invoice. Nothing here
needed a model to work out.

### 2.6 Deferred

Still to come, in later problems: paying an invoice and paying rent (both behind
human approval, both refusing to overdraw), resolving a ticket, and drafting
replies that stay on the board.

### 2.7 Tool → table → ticket

Which tables each tool reads, and which ticket it unlocks. All three read
`desk` first, because every date judgement is made against `desk.date_today`.

| Tool | Tables it reads | Unlocks | Why it is the right tool for that ticket |
|---|---|---|---|
| `list_tickets` | `desk`, `tickets` | **101, 102, 103** | It is the only way onto the board at all — nothing can be worked until the agent knows which tickets are open and what the shop's date is. |
| `get_ticket` | `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `invoices`, `leases`, `cash_accounts` | **102** (and the stock and money side of 101 and 103) | A ticket's meaning lives in the tables it links to, and resolving those links in one call is what turns "Rent due" into 2400.00 due in 2 days against a 3400.00 balance. |
| `get_vendor_status` | `desk`, `vendors`, `invoices` | **101, 103** | Both tickets are short of stock and can only be filled by a restock, so the question that decides them is whether the vendor will ship — and the answer is no while invoice #501 is open. |

Read down the *Unlocks* column and the shape of the board shows up: ticket 102
is answered by reading the shop's own records, while 101 and 103 both depend on
a vendor who is refusing to ship. That is why `get_vendor_status` earns a tool
of its own rather than being folded into `get_ticket` — it answers a question
about a *vendor*, and the same answer gates two different tickets.

A gap worth naming: ticket 103 needs a discount decision, and these three tools
deliberately stop at the facts it rests on (`unit_cost` 22.00, `list_price`
58.00, 8 of 20 in stock). Setting the price is a judgement a human should sign
off on, so no tool here offers to make it.

### 2.8 Connecting the server

`.mcp.json` at the project root registers the server with Claude:

```json
{
  "mcpServers": {
    "campus-customs": {
      "command": "./.venv/bin/python",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

Three decisions worth recording:

- **The venv's Python, not the system one.** `fastmcp` lives in `.venv`, and the
  system Python cannot import it. `.venv/` is not committed, so the venv has to
  exist before the server can start.
- **A relative command.** The client launches the server from the project root,
  so `./.venv/bin/python` keeps the file portable between machines in a way an
  absolute path would not.
- **No `env` block.** The first draft passed `CAMPUS_CUSTOMS_DB` as a relative
  path, which would have broken the moment the server was launched from a
  different directory. `db.py` already resolves the database from its own file
  location, so the default is strictly more robust than overriding it.

Verified before wiring it up, by running the server as a client would — as a
subprocess over stdio, not just imported in-process:

| Check | Result |
|---|---|
| Tools advertised | `list_tickets`, `get_ticket`, `get_vendor_status` |
| `get_vendor_status(1)` | `can_ship` false — "vendor has open unpaid invoice(s): #501 (840.00)" |
| `get_ticket(103)` | `short_by` 12, cash 3400.00 |
| `get_ticket(999)` | error reaches the client intact: "no ticket with id 999; tickets on the board: [101, 102, 103]" |

That last row is the one worth checking: a raise inside a tool has to arrive at
the agent as an error it can read, not as a silent empty result.

### 2.9 Smoke test: the tools against the database

`scripts/mcp_smoke.py` → `output/mcp_smoke.json`. **22 checks, all passing.**

The test is deliberately not an in-process import of the tool functions. It
starts the server the way a client does — as a subprocess over stdio, using the
command from the committed `.mcp.json` — then calls each tool and compares every
value it returns against `data/campus_customs_new.db`, re-read with its own
`sqlite3` connection. Agreement between a tool and the module it calls would
prove nothing; agreement between the tool's answer and an independent read of
the file is the thing worth evidencing.

| Tool | Checks | What was compared |
|---|---|---|
| `list_tickets` | 4 | `today` against `desk.date_today`, the open count, the ticket ids, and every ticket row field-for-field |
| `get_ticket` | 11 | the ticket row, pricing, `on_hand`, `short_by`, the invoice's amount / status / due date, `days_overdue` recomputed from the dates, the vendor behind it, and cash |
| `get_vendor_status` | 7 | the vendor row, `lead_days`, the open invoice ids and total, `can_ship`, and the ship date recomputed as `today + lead_days` |

Each entry in the evidence file records the prompt that asked for the test, the
tool name and arguments, the full tool output, and the list of comparisons with
both values side by side — so a reader can see what the tool said *and* what the
database says, rather than taking a pass/fail on trust.

Two things the run also establishes:

- **The database is unchanged.** Its SHA-256 is recorded in the evidence and
  re-checked after the run. Read-only tools really are read-only.
- **The committed `.mcp.json` command works.** A bug surfaced here and was worth
  keeping: resolving the relative command with `Path.resolve()` followed
  `.venv/bin/python` through its symlink to the *system* interpreter, which has
  no `fastmcp`, and the server died at startup with nothing but "Connection
  closed" at the client. The fix is to make the path absolute without resolving
  symlinks. Worth remembering for any venv-based MCP command.

---

## 3. The agent team

Five PydanticAI agents — **Boss, Inventory, Accounting, Facilities, Customer
Service** — all on `gpt-6-luna` through Portkey, all reaching the shop only
through the MCP tools from section 2.

### 3.1 Who does what, and who may ask whom

```
          Boss ─┬─> Inventory ◂──────────────┐
                ├─> Accounting               │
                ├─> Facilities               │
                └─> Customer Service ────────┘
```

Delegation runs one way. The Boss may ask any specialist; Customer Service may
ask Inventory; nothing asks the Boss. That is deliberate — a cycle between two
agents is a bill that grows until a request limit stops it, and there is no
question here that needs one.

| Agent | Owns | May delegate to |
|---|---|---|
| **Boss** | triage, deciding, the order things happen in | all four |
| **Inventory** | stock, shortfalls, whether a vendor can resupply | — |
| **Accounting** | cash, invoices, proposing payments for approval | — |
| **Facilities** | leases, landlords, rent | — |
| **Customer Service** | the reply to the requester | Inventory |

The one sideways edge exists for a reason: a reply written from the ticket
alone is exactly where invented delivery dates come from, so Customer Service
has to be able to ask what is actually true before it promises anything.

### 3.2 One place per decision

- **One model factory.** `settings.model()` is the only way to get a client, and
  it raises on any name but `gpt-6-luna`. An agent cannot quietly use something
  else, because there is no other constructor to call.
- **One agent builder.** `base.build_agent()` gives every agent the same four
  things: the model, the shared MCP toolset, a prompt file, and a typed output.
- **One copy of the house rules.** `prompts/_shared.md` holds the seven rules
  that bind every agent — the shop's date, never invent, never pay, never
  overdraw, never contact anyone, the vendor shipping block, and say so when you
  cannot answer. Each agent prompt splices it in at `{SHARED_RULES}`, so a rule
  cannot drift between agents.
- **One request budget.** Delegated runs are passed `ctx.usage`, so the team
  shares one budget rather than one per agent, capped at 60 requests a run.

### 3.3 The types the team passes around

`backend/models.py`. Each specialist returns a typed result rather than prose,
which is what makes the Boss's job assembly instead of interpretation:
`StockAssessment`, `MoneyAssessment`, `RentAssessment`, `DraftReply`, and the
Boss's own `TicketOutcome` / `BoardReview`.

The important one is **`ApprovalRequest`**. A payment is not an action in this
system, it is a *proposal*: payee, amount, `cash_before`, `cash_after`, what it
unblocks, and `approved` left null for a human to set. No agent has a tool that
moves money, so the type is the only way a payment can be expressed at all.
`DraftReply.sent` is typed `Literal[False]` for the same reason — the schema
itself says a draft stays on the board.

### 3.4 Two things the live run taught

**The gateway refuses function tools with reasoning effort on.** The first run
died on a 400: *"Function tools with reasoning_effort are not supported for
gpt-6-luna-global in /v1/chat/completions"*. Every agent on this team uses
tools, so `openai_reasoning_effort="none"` is set once in `base.py` rather than
remembered at five call sites.

**The first draft reply leaked the shop's books.** Working ticket 102, Customer
Service wrote to the *landlord*: "The checking balance is $3,400 ... would leave
$1,000." Every figure was true and came from the database, and it still should
not have been written — rule 2 (never invent) does not imply rule "never
disclose". The prompt now says cash balances, unit costs, and margins are
internal; a landlord hears about their own lease and nothing else. Re-running
the same ticket produced a draft with no internal figures in it.

### 3.5 Live run — ticket 102

`python -m backend.run_board --ticket 102`, against the untouched working copy:

- Boss delegated to **facilities → accounting → customer_service**.
- Facilities: Chapel Street shop, 2400.00, due 2026-09-02, **2 days**, not
  overdue — all matching the `leases` row.
- Accounting: affordable, `cash_before` 3400.00, `cash_after` 1000.00, raised as
  an `ApprovalRequest` with `approved: null`.
- Customer Service: a draft, `sent: false`, no internal figures.
- `resolved: false`, `needs_human: true` — correct, since nothing is paid until
  a person approves it.

Nothing was written to the database: the tools are read-only, and the payment
exists only as a proposal.

### 3.6 Full board run

Database reset first, as the rules require. `python -m backend.run_board -o
output/board_review.json` — one run, 88 seconds, all three tickets.

| Ticket | Delegated to | What the team concluded |
|---|---|---|
| 101 | inventory → accounting → customer_service | S tee is 0, short by 1; Bulldog Print Co blocked by invoice #501, 3 days overdue; **no arrival date promised** |
| 102 | facilities → accounting → customer_service | 2400.00 due 2026-09-02, two days out, not overdue |
| 103 | inventory → customer_service | 8 of 20 in stock, short by 12; restock blocked by the same invoice; cost 22.00 against list 58.00, **discount left to a human** |

The spending plan it produced on its own:

> Pay invoice #501 (840.00) first — it is overdue *and* it is the verified
> shipping blocker — leaving 2,560.00. Then rent (2,400.00), leaving **160.00**.
> Both fit; neither is paid.

That is the same order and the same arithmetic as the hand analysis in
[`data_model.md`](data_model.md), reached from the tools alone. All three
tickets came back `needs_human: true` and `resolved: false`, which is correct:
nothing can be closed until a person approves a payment.

**Nothing was written.** After the run: `payments` still empty, invoice #501
still `open`, checking still 3400.00, all three tickets still `open`, and the
file's SHA-256 unchanged. The two payments exist only as `ApprovalRequest`s with
`approved: null`.

**The drafts held up.** No cash balances, no unit costs, no margins, and no
invented dates — ticket 101's draft says plainly that there is no restock date
to give rather than inventing 2026-09-05, which the tools had offered it.

### 3.7 Three faults in the run, worth keeping

None of these are crashes; all three are the agents being less careful than the
data allows, and all three are prompt problems rather than code problems.

1. **`unblocks` undercounts.** The approval request for invoice #501 lists
   `unblocks: [101]`. Paying it also unblocks **103** — same vendor, same
   block — and the Boss said so in prose for ticket 103 while leaving it out of
   the structured field. A human skimming the approval sees one ticket's worth
   of benefit for an 840.00 payment instead of two.
2. **Accounting was never asked about 103.** The Boss delegated it to Inventory
   and Customer Service only, so nobody checked whether the restock could be
   paid for. It cannot: 12 units at 22.00 is **264.00**, and the two approved
   payments would leave **160.00**. The run never surfaces that the restock is
   unaffordable this week — the one fact that decides what the Yale AI Club can
   actually be promised.
3. **The customer was told the shop has an overdue invoice.** Ticket 101's
   draft explains the delay as "the vendor is unable to ship while an overdue
   invoice remains open". True, and sourced — but it is the shop's debt, and the
   prompt rule that keeps balances and margins internal did not name it.

The pattern across all three: the rules say *never invent*, and the agents
obeyed. They say much less about what to **volunteer** — which links to draw
between tickets, which specialist to consult when money is implied rather than
stated, and which true fact is nobody else's business.

### 3.8 The three faults, fixed in the prompts

No code changed — all three were gaps in what the prompts asked for.

| Fault | The rule added | Where |
|---|---|---|
| `unblocks` named one ticket | "Fill `unblocks` with every ticket the payment frees, not just the one you were asked about" — and the Boss checks the list against the board before accepting it | `accounting.md`, `boss.md` |
| Accounting skipped on 103 | "**Money is often implied rather than stated.** A restock, a reprint, or a larger order all cost cash even when the ticket never mentions it... A ticket about stock is still a ticket about money." | `boss.md` |
| The customer was told about the shop's debt | "**That includes the shop's own debts.** Never write that an invoice is unpaid, overdue, or holding up a vendor... Why it is delayed is the shop's business." | `customer_service.md` |

Re-run from a reset database, 81 seconds:

| Fault | Before | After |
|---|---|---|
| 1 | `unblocks: [101]` | **`unblocks: [101, 103]`** |
| 2 | 103 → inventory, customer_service | **103 → inventory, accounting, customer_service** |
| 3 | "the vendor is unable to ship while an overdue invoice remains open" | **no mention of invoices, debts, or balances in any of the three drafts** |

Fixing the second one bought more than the delegation. With Accounting in the
loop on 103, the run worked out what the first one never reached:

> Do not include hoodie replenishment as a payment proposal yet: the $264 is
> only 12 × $22 unit-cost arithmetic, not a vendor quote. Adding even that
> arithmetic to the two known obligations would total $3,504, **$104 more than
> current checking.**

That is the fact that actually decides ticket 103, and it took asking the right
specialist to surface it. The distinction it drew unprompted — that 12 × 22.00
is arithmetic rather than a quote, because no quote exists in the database — is
the "never invent" rule applied to a number it had every excuse to treat as
settled.

The plan and the figures are otherwise unchanged: #501 then rent, 3400.00 →
2560.00 → 160.00, nothing paid, all three tickets still needing a human. The
database was untouched again: `payments` empty, invoice #501 `open`, checking
3400.00, all tickets `open`.

---

## 4. Working the tickets: write tools, approval, and the audit trail

Section 2's tools could only look. These let the team act — within limits the
tools themselves enforce.

### 4.1 The agents

| Agent | What it owns | MCP tools it uses | Delegates to |
|---|---|---|---|
| **Boss** | triage, deciding, ordering, closing | `list_tickets`, `get_ticket`, `list_approvals`, `resolve_ticket` | all four specialists |
| **Inventory** | stock, shortfalls, resupply | `get_ticket`, `get_vendor_status`, `list_tickets` | — |
| **Accounting** | cash, invoices, proposing and paying | `get_ticket`, `get_vendor_status`, `list_tickets`, `list_approvals`, `propose_payment`, `pay` | — |
| **Facilities** | leases, landlords, rent | `get_ticket`, `list_tickets` | — |
| **Customer Service** | the reply to the requester | `get_ticket`, `list_tickets`, `record_draft_reply` | Inventory |

No agent uses `approve_payment`. It is served by the same MCP server, but
`backend/toolset.py` filters it out of the agents' view — they cannot call a
tool they cannot see.

### 4.2 Every MCP tool and the tables it touches

Writes are marked **w**; everything else is a read. All nine read `desk` first,
because every date judgement is made against the shop's date.

| Tool | Tables | What it does |
|---|---|---|
| `list_tickets` | `desk`, `tickets` | the board, with the shop's date |
| `get_ticket` | `desk`, `tickets`, `inventory`, `pricing`, `leases`, `invoices`, `vendors`, `cash_accounts` | one ticket with every link resolved |
| `get_vendor_status` | `desk`, `vendors`, `invoices` | will a vendor ship, and how fast |
| `list_approvals` | `desk`, `approvals` | every proposal and where it stands |
| `propose_payment` | `desk`, `invoices`/`leases`, `cash_accounts`, **w** `approvals` | records a proposal; pays nothing |
| `approve_payment` | `desk`, **w** `approvals` | **human only** — records a person's decision |
| `pay` | `desk`, `approvals`, `invoices`/`leases`, `cash_accounts`, **w** `payments`, **w** `cash_accounts`, **w** `approvals`, **w** `invoices`/`leases` | the only tool that moves money |
| `record_draft_reply` | `desk`, `tickets`, **w** `drafts` | pins a draft to the board; sends nothing |
| `resolve_ticket` | `desk`, **w** `tickets` | closes a ticket with a note |

`approvals` and `drafts` are not in the original pack. They are created on the
working copy the first time something writes, so `reset_db.sh` wiping them is
correct: a fresh board has no approvals and no drafts.

### 4.3 Safety

**The guardrail: no payment executes without explicit human approval. Agents can
only propose; `pay` refuses when no approval is recorded, and refuses any
payment that would push a cash account below zero.**

How that is actually enforced, in order of how hard it is to get around:

1. **The approving tool is not in the agents' toolset.** An agent cannot
   approve its own proposal because `approve_payment` never appears in its tool
   list. A person approves through `scripts/approve.py`, which calls the same
   MCP server — there is no second path to the database for anyone.
2. **`pay` checks the approvals table, not its instructions.** No approval row
   at status `approved` for that exact kind, id and account, and it raises.
   This is a database read at the moment of payment, so no amount of persuasion
   in a prompt changes the answer.
3. **One approval buys one payment.** Paying marks the approval `used`, so a
   second attempt finds nothing approved. Two approvals for the same obligation
   still cannot pay twice: `pay` checks the invoice's own status, and refuses
   rent already paid today for that lease.
4. **No negative balances.** `pay` computes the remaining balance before
   writing and refuses when it would go below zero, naming the figure it
   refused.
5. **A payment is one transaction.** The payment row, the new balance, the
   invoice marked paid (or the lease rolled on), and the approval marked used
   all happen in a single connection — the gap §1.10 warned about is closed.
6. **Reads cannot write.** Read tools open the file with `mode=ro`; SQLite
   refuses a write on that connection.
7. **Nothing leaves the building.** There is no tool that sends mail or calls a
   vendor. `record_draft_reply` stores a draft with `sent` false, and that is
   the only outbound path there is.

Proven directly against the database, not by asking an agent nicely:

| Attempt | Result |
|---|---|
| `pay` with no approval | refused — "no recorded human approval for invoice 501" |
| `pay` while the proposal is only *proposed* | refused — "Proposal 1 is still awaiting a human decision" |
| `pay` after a human approves | paid: 3400.00 → 2560.00, invoice marked paid, approval marked used |
| `pay` the same invoice again | refused — the approval is spent and the invoice is no longer open |
| `pay` rent of 2400.00 with 160.00 in the account | refused — "would leave -2240.00. Cash accounts may not go below zero." |

### 4.4 The audit trail

`output/audit_trail.json` — a JSON array that **grows**. Each run appends; the
file is never truncated, so it holds every run this system has ever done.
Writes go to a temporary file and are moved into place, so an interrupted write
cannot leave the trail unparseable.

Six record types, enough to reconstruct a run afterwards:

| Event | Carries |
|---|---|
| `run_started` / `run_finished` | the instruction; then requests, tokens, tickets touched, or the error |
| `agent_started` / `agent_finished` | which agent, **who delegated to it**, the prompt, the output, requests, tokens, duration |
| `delegation` | who asked whom, about which ticket, and what was asked |
| `tool_call` | the agent, the tool, the arguments, the result or the error, and the duration |

Every record carries a `run_id` and a `seq`, so one run can be pulled out of the
file and read in order. **Failures are recorded, not dropped** — the refused
second payment in 4.5 is in the trail with its error text, which is exactly the
kind of thing an audit exists to catch.

### 4.5 The approval loop, end to end

Three runs against one reset board.

**Pass 1 — nothing is approved yet.** The team worked all three tickets, wrote
one draft per ticket, and recorded exactly two proposals: rent 2400.00 and
invoice #501 840.00. `payments` empty, cash 3400.00 untouched. Ending a pass
with proposals and open tickets is the system working, not failing.

**A human decides.** `scripts/approve.py 2 --by "Shutong Gang"` — approving the
invoice only, leaving rent proposed.

**Pass 2 — one approval exists.** Accounting called `pay` for invoice 501: paid,
3400.00 → 2560.00, invoice marked paid, approval marked `used`, `approved_by`
recorded as the human who signed it. It then called `pay` for the same invoice
again and was **refused**. Rent, still only proposed, was not paid.

That is the guardrail doing its job twice in one run: once by allowing exactly
the payment a person authorised, and once by refusing the one they did not.

### 4.6 Two faults the write tools exposed

Both were the same shape — an agent calling a write tool more than once — and
both were fixed in the tools rather than the prompts, because a prompt that
says "call this once" is a request, while a tool that refuses is a guarantee.

- **Six drafts for three tickets.** Customer Service recorded each draft, and
  then the Boss recorded all three again. `record_draft_reply` now replaces the
  live draft for a ticket instead of adding another; the Boss's prompt also now
  says drafting is not its job.
- **Nine proposals for two obligations.** Accounting proposed the same invoice
  on every pass through. `propose_payment` now returns the existing pending
  proposal instead of stacking duplicates. This one mattered: nine identical
  approvals is a trap for whoever is approving, and approving two of them is two
  payments.

---

## 5. The desk page

`output/desk_tickets.html` — one file, no external anything, double-click to
open. Five tabs: one per ticket, plus **Cash** and **Reflection** marked
*coming later*.

### 5.1 Generated from the database, not typed

`scripts/build_desk_page.py` reads `data/campus_customs_new.db` and writes the
page, so every figure on it traces to a row rather than to someone's memory of
one. Rebuild it after a reset with:

```bash
./scripts/reset_db.sh
./.venv/bin/python scripts/build_desk_page.py
```

The working copy was reset first, deliberately: the **Expected** sections
describe what the team should do with a *fresh* board. Had the page been built
from the state left by §4.5, it would have claimed invoice #501 was still open
while the database said `paid`.

Checked after generating — all eleven figures on the page match the database:
the shop date, the balance, the invoice amount and due date, the rent and its
due date, both running balances (2560.00 and 160.00), the 264.00 restock, the
zero tee stock, and the 12-unit hoodie shortfall.

### 5.2 What is on a ticket tab

| Section | Holds |
|---|---|
| **What the database says** | the ticket's own row plus the rows it links to |
| **Boss calls first** | which specialist opens the ticket, and why that answer decides the rest |
| **Workflow** | the delegation path step by step, with the figure each step should produce |
| **MCP tools expected to run, and why** | the tools by name, the tables they touch, and what each is for *on this ticket* |
| **Skipped, and why** | the specialists and tools that should **not** run |
| **It should not** | the specific wrong moves this ticket invites — promising 2026-09-05 on 101, quoting a discount on 103 |
| **Actual** | empty, for filling in after a run |

**The three tickets open differently, and that is the point.** 101 and 103 are
orders, so **Inventory** goes first: whether the SKU exists in that size decides
who else is called and whether money is involved at all. 102 is rent, so
**Facilities** goes first — there is no SKU to look up, and the lease, not the
notice that raised the ticket, is the record. Sending every specialist at every
ticket would cost a model call each time to be told the ticket has no product on
it.

The *Skipped* sections are written as carefully as the workflows. On 101,
Accounting runs only because the tee is out of stock and the vendor is blocked —
had it been in stock, the path would go Inventory → Customer Service with no
money involved at all, and that counterfactual is on the tab. On 103,
`propose_payment` is skipped deliberately: the 264.00 restock is arithmetic off
the pricing table, not a bill, and proposing it would put a purchase in front of
a human that the balance cannot cover anyway.

The "It should not" lists are the useful half. Each one names a mistake the
data actively tempts an agent into: `get_vendor_status` *returns*
`earliest_ship_date_if_ordered_today`, so promising that date on ticket 101 is
one copy-paste away, and only the `can_ship: false` beside it says otherwise.

The Actual boxes are plain textareas that keep what is typed in them in the
browser's local storage, so closing the page does not lose the notes. Nothing
leaves the file — there is no network call in it.

### 5.3 Not visually checked

The page's structure was verified — five tabs, five panels, three Expected and
three Actual sections, the Actual boxes empty, zero external references — but
Chrome was not reachable from this session, so **nobody has looked at it
rendered**. If something is off visually, that is why.

---

## 6. The API

`backend/main.py` — FastAPI, for the dashboard to call. Started from the
`backend/` folder:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

It serves on **http://localhost:8000**, which is where the dashboard looks.
(From the project root the same app is `backend.main:app`. `main.py` puts the
project root on `sys.path` when it is loaded as a top-level module, so both
spellings work.)

### 6.1 The routes, one line each

- **`GET /api/health`** — is the API up, and can it reach the shop.
- **`GET /api/tickets`** — the three tickets, each marked open or resolved, with the shop's date.
- **`GET /api/tickets/{id}`** — one ticket with every link resolved: stock, pricing, invoice, lease, cash.
- **`POST /api/tickets/{id}/run`** — runs the agent team on that ticket; returns a run id straight away.
- **`GET /api/runs/{run_id}`** — where that run got to, and its review once it finishes.
- **`GET /api/events`** — recent agent events: what each agent said and which tools it used, for the board to refresh.
- **`GET /api/approvals`** — payments the agents have proposed, and what became of each.
- **`POST /api/approvals/{id}`** — a human approves or declines; **the only route that changes cash**.
- **`GET /api/cash`** — the current checking balance from `cash_accounts`.
- **`POST /api/reset`** — restore the database to the original values for a fresh run.

Which tool each one goes through:

| Route | Through |
|---|---|
| `/api/tickets`, `/api/health` | `list_tickets` |
| `/api/tickets/{id}`, `/api/cash` | `get_ticket` |
| `/api/tickets/{id}/run`, `/api/runs/{id}` | the agent team |
| `/api/events` | the audit trail |
| `/api/approvals` | `list_approvals` |
| `POST /api/approvals/{id}` | `approve_payment`, then `pay` |
| `/api/reset` | a file copy — the one route that is not MCP |

**Everything goes through MCP**, the same tools the agents use — there is no
second query layer in the API. The single exception is `/api/reset`, which
replaces the database file: that is an operator action on the database, not a
fact about the shop, and it is the one thing MCP has no tool for.

### 6.2 Two decisions worth recording

**A run returns immediately.** A board run takes a minute or two, far too long
to hold a request open. `POST /api/tickets/{id}/run` opens an audit run id,
starts the team in the background, and returns `202` with that id; the dashboard
polls `/api/events?run_id=…&after_seq=…` to watch it happen and
`/api/runs/{id}` for the result. A second run while one is in flight gets
**409** — the team shares one database, and two boards at once would have them
proposing against each other's half-finished state.

**The human's click is where money moves.** The agents propose and stop.
`POST /api/approvals/{id}` records the approval against the person who gave it
and then calls `pay`. If `pay` refuses — no approval, already spent, or the
balance cannot take it — that refusal comes back in `refused_because` with the
cash unchanged, rather than being swallowed into a 500.

### 6.3 Exercised against the running server

Every route was called for real, not just imported:

| Call | Result |
|---|---|
| `POST /api/reset` | board back to 3 open tickets, 3400.00 |
| `GET /api/tickets` | 101, 102, 103 — all `open`, shop date 2026-08-31 |
| `POST /api/tickets/101/run` | `202`, run id returned straight away |
| `POST /api/tickets/102/run` *during* that run | **409**, as intended |
| `GET /api/events?run_id=…` | the whole delegation tree streamed: boss → inventory, boss → accounting (which called `propose_payment`), boss → customer_service → **inventory**, then `record_draft_reply` |
| `GET /api/approvals` | the one proposal the team made: invoice 501, 840.00, `proposed` |
| `POST /api/approvals/1` | **paid** — 3400.00 → 2560.00, invoice marked paid |
| `POST /api/approvals/2` (rent) | **paid** — 2560.00 → 160.00, lease rolled to 2026-10-02 |
| `POST /api/approvals/3` (same rent again) | `paid: false`, `refused_because: "rent for lease 1 was already paid today"`, **cash still 160.00** |
| `POST /api/approvals/1` twice | refused — "a decision cannot be changed" |

### 6.4 Two bugs the API surfaced

Neither could have shown up from the CLI, and both were in older code:

- **`list_approvals` broke on a freshly reset board.** The `approvals` and
  `drafts` tables are created on first *write*, but reading them opens the file
  read-only — so straight after `POST /api/reset`, the very first thing a
  dashboard would ask for returned *"no such table: approvals"*. `db.py` now
  creates the extra tables whenever the file is opened and lacks them, keyed to
  the file's mtime so a reset re-triggers it.
- **Event sequence numbers restarted with every process.** Fine for a CLI that
  runs once; wrong for a server, where the dashboard polls with `after_seq` and
  a restarted counter makes old records look new. The counter now continues the
  file's own numbering.

A third was fixed before it could bite: the audit run id was generated once at
import, so every run served by one process would have shared it. It is now
opened per run — which is also what lets the run route hand the browser an id
before the run has finished.

---

## 7. The dashboard

`frontend/` — React + Vite + TypeScript, calling the routes from §6.

```bash
cd backend && uvicorn main:app --reload --port 8000   # one terminal
cd frontend && npm install && npm run dev             # another
```

Vite proxies `/api` to the backend, so every request is same-origin in
development and the app uses plain relative URLs. `VITE_API_TARGET` overrides
the target when something else already holds 8000.

### 7.1 What the board does

| Requirement | How |
|---|---|
| List the three tickets | `GET /api/tickets`, drawn as paper tags |
| Pick one and start the team | click a tag, then **Send the team in** → `POST /api/tickets/{id}/run` |
| Show each agent and what it is doing | `GET /api/events` polled every 1.5s while a run is in flight |
| Mark a ticket resolved when the run finishes | the board refetches and stamps any ticket the database now reports as resolved |
| Short summary of what each agent did | the Boss's outcome for that ticket: who was consulted, what was found, what is recommended |
| Approve a pay when asked | pending approvals are receipt slips with an **Approve** button → `POST /api/approvals/{id}` |
| Show the checking balance, dropping after a pay | `GET /api/cash`, counted down on change |

### 7.2 The look

Warm cream paper, navy ink, one accent — a vermilion `#d6451f` used for the
accent rule under the masthead, the send button, the approve button, and
nothing else that is not a decision.

- **Tickets are paper tags.** Punched hole, a thread drawn across it, each one
  rotated half a degree off square and straightening when you hover. The
  rotation alternates so a column of them looks hung rather than stacked.
- **Approvals are till receipts.** Monospaced, dashed rules, the total in large
  figures, and a torn bottom edge cut with a `clip-path` zigzag.
- **Each agent owns a colour** — Boss indigo, Inventory green, Accounting amber,
  Facilities violet, Customer Service teal — used for its roster chip, the left
  edge of its feed lines, and the delegation chain in the summary. Whichever
  agent spoke last while a run is in flight gets a **ring that pulses** out from
  its chip.
- **The balance is the biggest thing on the page**, in a serif face with
  tabular figures so the digits do not jiggle while it moves.
- **Motion with a reason.** Feed items slide up as they arrive; the balance
  *counts down* over 1.1 seconds on an ease-out curve rather than jumping, so
  money leaving the account is something you watch; RESOLVED lands with a
  stamp that overshoots and settles. All of it collapses under
  `prefers-reduced-motion`.

Three columns on a desk-width screen, two at 1080px with the money column
spanning, one on a phone.

### 7.3 Two things the board is careful about

**The RESOLVED stamp follows the database, not the run.** A finished run does
not stamp a ticket; the board refetches `/api/tickets` and stamps whatever the
shop now says is resolved. Since the team only calls `resolve_ticket` when
nothing is left for a human, a stamp means the ticket is genuinely finished —
on a fresh board all three stay open, waiting on approvals, and that is the
honest picture.

**A refusal is shown, not swallowed.** If `pay` refuses — no approval, already
spent, would overdraw — the message comes back in `refused_because` and is
shown in the error banner with the balance unmoved. The feed does the same with
failed tool calls, tinting them and keeping the error text, because a refused
payment is the most interesting line in a run.

### 7.4 Checked, and not checked

- `npm run build` — TypeScript strict (`noUnusedLocals`, `noUnusedParameters`,
  `verbatimModuleSyntax`) and the production bundle both clean: 24 modules,
  233 kB JS, 12 kB CSS.
- The chain was run for real: Vite served the app, proxied `/api/tickets` and
  `/api/cash` through to the backend, through MCP, to the database — shop date
  2026-08-31, three open tickets, 3400.00.
- **Not seen rendered.** Chrome was not reachable from this session, so no one
  has looked at the page in a browser. The layout, the colours, and the
  animations are unverified by eye.
