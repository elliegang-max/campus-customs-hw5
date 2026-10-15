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
