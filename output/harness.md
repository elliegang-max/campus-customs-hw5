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
