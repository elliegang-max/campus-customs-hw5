# The shop database — tables, fields, and how the three tickets link up

Source: `data/campus_customs.db` (never written to). The working copy the tools
use is `data/campus_customs_new.db`; `./scripts/reset_db.sh` restores it.

Nine tables, 21 rows in total. It is a small, hand-built world: one desk, one
lease, one cash account, one open invoice, three vendors, three tickets.

---

## 1. Every table and its fields

### `desk` — the shop's clock and scratchpad (1 row)

| Field | Type | Value today |
| --- | --- | --- |
| `date_today` | TEXT | `2026-08-31` |
| `notes` | TEXT | empty |

**This is "today".** Overdue is measured against it, never against the system
clock.

### `tickets` — the work to be done (3 rows, all `open`)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | 101, 102, 103 |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT | person or organisation who asked |
| `subject` | TEXT | one-line summary |
| `sku` | TEXT | nullable → `pricing.sku`, `inventory.sku` |
| `size` | TEXT | nullable → with `sku`, the `inventory` key |
| `qty` | INTEGER | nullable, units requested |
| `lease_id` | INTEGER | nullable FK → `leases.id` |
| `invoice_id` | INTEGER | nullable FK → `invoices.id` |
| `status` | TEXT | `open` for all three |
| `notes` | TEXT | the ask, in prose |
| `created_at` | TEXT | ISO-8601 with offset |

The three nullable link columns are the whole design: a ticket points at
**stock** (`sku` + `size`), at a **lease**, or at an **invoice**, and which one
is filled tells you what kind of work it is.

### `inventory` — what is on the shelf (10 rows)

| Field | Type | Notes |
| --- | --- | --- |
| `sku`, `size` | TEXT | composite primary key |
| `name` | TEXT | display name |
| `qty` | INTEGER | units on hand |
| `location` | TEXT | Aisle A–D |

Four SKUs. Two rows sit at zero: `CC-TEE-WHITE`/`S` and `CC-MUG-CREST`/`OS`.

### `pricing` — cost and list, per SKU (4 rows)

| Field | Type | Notes |
| --- | --- | --- |
| `sku` | TEXT PK | |
| `unit_cost` | REAL | what the shop pays |
| `list_price` | REAL | what the shop charges |

| SKU | unit cost | list | margin |
| --- | --- | --- | --- |
| `CC-HOOD-NAVY` | 22.00 | 58.00 | 36.00 |
| `CC-TEE-WHITE` | 8.00 | 28.00 | 20.00 |
| `CC-HAT-BLUE` | 6.00 | 22.00 | 16.00 |
| `CC-MUG-CREST` | 3.50 | 14.00 | 10.50 |

`unit_cost` is the floor for any discount — below it the shop loses money.

### `vendors` — who can resupply, and how fast (3 rows)

| id | name | specialty | lead_days |
| --- | --- | --- | --- |
| 1 | Bulldog Print Co | apparel reprint | 5 |
| 2 | Elm City Gifts | mugs and small goods | 3 |
| 3 | QuickShip CT | local courier | 1 |

**Lead times come from here**, never from a guess. Specialty decides who can
supply what: apparel (tees, hoodies) is vendor 1 only.

### `invoices` — what the shop owes vendors (1 row)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | |
| `vendor_id` | INTEGER | FK → `vendors.id` |
| `amount` | REAL | |
| `due_date` | TEXT | |
| `status` | TEXT | `open` / paid |
| `description` | TEXT | |

One row: **#501, Bulldog Print Co, $840.00, due 2026-08-28, open** —
"Rush reprint CC-TEE-WHITE S". Three days overdue as of today.

### `leases` — the rent obligation (1 row)

| Field | Type | Value |
| --- | --- | --- |
| `id` | INTEGER PK | 1 |
| `space_name` | TEXT | Chapel Street shop |
| `landlord` | TEXT | Elm City Properties |
| `monthly_rent` | REAL | 2400.00 |
| `next_due` | TEXT | 2026-09-02 |
| `notes` | TEXT | empty |

### `cash_accounts` — the money (1 row)

| Field | Type | Value |
| --- | --- | --- |
| `name` | TEXT PK | checking |
| `balance` | REAL | 3400.00 |
| `date` | TEXT | 2026-08-31 |

**$3,400.00 is the hard ceiling on everything below.** Cash only goes out.

### `payments` — the record of money leaving (0 rows)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | |
| `kind` | TEXT | what was paid — invoice vs rent |
| `ref_id` | INTEGER | the id *in the table `kind` names* |
| `amount` | REAL | |
| `account` | TEXT | → `cash_accounts.name` |
| `paid_at` | TEXT | |
| `approved_by` | TEXT | **who approved it — the audit trail** |

Empty: nothing has been paid yet. `kind` + `ref_id` is a loose polymorphic
pointer — `kind='invoice'` means `ref_id` is an `invoices.id`, `kind='rent'`
means it is a `leases.id`. Nothing in the schema enforces that, so the pay tool
has to.

---

## 2. How the tables link

```
          desk.date_today  ── "today" for every overdue check
                 │
    tickets ─────┼── sku + size ──→ inventory (sku, size)     what's on the shelf
      │          └── sku ────────→ pricing (sku)              cost floor & list
      ├── invoice_id ───────────→ invoices (id) ──→ vendors (id)   lead_days
      └── lease_id ─────────────→ leases (id)
                                      │                │
                      payments.ref_id ┘   (kind='rent') │ (kind='invoice')
                                                        │
                      payments.account ──→ cash_accounts (name) ── balance
```

Two things the schema does **not** do, which the tools must:

- **No foreign key from `invoices` to `payments`.** Paying is two writes plus a
  third: insert into `payments`, set `invoices.status` to paid, and decrement
  `cash_accounts.balance`. Miss one and the books disagree.
- **No constraint stops a negative balance.** `balance` is a plain REAL. The
  refusal has to live in the pay tool.

---

## 3. The three open tickets

Today is **2026-08-31**. Checking holds **$3,400.00**.

### Ticket 101 — `customer_order` — Tauhid Zaman — "Bulldog tee"

`sku=CC-TEE-WHITE`, `size=S`, `qty=1`, **`invoice_id=501`**

The chain that makes this ticket interesting:

1. The customer wants one white tee in **S**.
2. `inventory` says `CC-TEE-WHITE`/`S` = **0**. Nothing to sell.
3. The ticket points at **invoice 501**, whose description is
   *"Rush reprint CC-TEE-WHITE S"* — the restock was **already ordered** from
   Bulldog Print Co.
4. Invoice 501 is **$840.00, due 2026-08-28 — 3 days overdue**.
5. House rule: *a vendor will not ship while they have an open unpaid invoice.*
   So the tee is not coming until #501 is paid.
6. Bulldog Print Co's `lead_days` is **5**, so paying today puts arrival around
   **2026-09-05** — the customer cannot be served today either way.

So the ticket is not really "sell a tee". It is: **pay the overdue invoice
(with human approval), then tell the customer a realistic date.**

### Ticket 102 — `rent_notice` — Elm City Properties — "Rent due"

`lease_id=1`

Lease 1 is the Chapel Street shop: **$2,400.00 due 2026-09-02**, i.e. **in 2
days** — matching the note. Not overdue yet, but it is the largest single claim
on the account.

### Ticket 103 — `price_override` — Yale AI Club — "Bulk hoodie discount"

`sku=CC-HOOD-NAVY`, `size=M`, `qty=20`

1. They want **20** navy hoodies in **M**.
2. `inventory` has **8** in M. **Short by 12.** (There are 4 S, 14 L, 6 XL —
   wrong sizes; the ask is specific.)
3. The 12 missing units are apparel, so again **Bulldog Print Co** — the same
   vendor blocked by invoice 501, with the same 5-day lead.
4. The discount question is bounded by `pricing`: cost **22.00**, list
   **58.00**. Any quoted price must stay above 22.00, and that is a judgement
   call a human should sign off on, not a number an agent should invent.

### The cash squeeze — why these three are one problem

| | Amount | Running balance |
| --- | --- | --- |
| Opening checking | | **3,400.00** |
| Invoice 501 (unblocks both apparel tickets) | −840.00 | 2,560.00 |
| Rent, lease 1 (due 09-02) | −2,400.00 | **160.00** |
| Reprint 12 × `CC-HOOD-NAVY` @ 22.00 | −264.00 | **−104.00** ❌ |

The two obligations fit, with **$160.00** to spare. The hoodie restock does
**not** — it would overdraw the account, so the pay tool must refuse it. Order
matters too: spend on hoodies first and rent no longer clears.

That is the lesson in the data. Tickets 101 and 103 both queue behind one
overdue $840 invoice, and the account only has room for the invoice and the
rent. Ticket 103 cannot be filled in full this week; it needs a human decision
(part-ship 8 now, quote a date for 12 more, or hold), not an agent improvising.
