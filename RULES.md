# Shop rules — hw5

The constraints the system must obey, as given in the assignment. Everything
built here (tools, agents, the MCP server, the backend) is written against this
list.

## The shop

- **"Today" is `desk.date_today`.** Never the system clock. Overdue is measured
  against that field.
- **Vendor lead times come from the `vendors` table.** Not from guesses or
  hard-coded defaults.
- **A vendor will not ship new product while they still have an open unpaid
  invoice.** Check invoices before ordering from a vendor.

## Money

- **Human approval is required for any payment.** No payment goes out without an
  explicit approval step. *Points are deducted if this is skipped.*
- **If payment is made, the relevant table must be updated.** The database is the
  record of what happened.
- **The pay tool must refuse when there is not enough cash.** No negative
  balances, ever.
- **Cash only goes out.** Revenue is not modelled, so no money comes in.

## Running

- **Reset the database before a full ticket run** — `./scripts/reset_db.sh`
  restores `data/campus_customs_new.db` from the untouched original.
- **No real-world contact.** Do not email customers or call real vendors. Drafts
  stay on the board.

## Models

- **Every agent uses `gpt-6-luna` through Portkey, and nothing else.** Multi-agent
  chats burn tokens fast. *Points are deducted if any other model appears in the
  code or in a run.*
- Credentials resolve in this order, first one wins: the process environment,
  then `./.env`, then `~/.config/ai-keys/keys.env` — the same fallback hw4 used.
  Both `PORTKEY_API_KEY` and `PORTKEY_BASE_URL` are already in the `ai-keys`
  file, so no `.env` is needed locally.
