# Campus Customs — the back office

A back-office desk for a fictional campus apparel shop. Three tickets sit on a
board; a team of five PydanticAI agents works them through an MCP server, and a
React dashboard shows what they are doing. **No agent can spend money** — a
payment is proposed, a person signs it, and only then does the balance move.

> Campus Customs is a fictional shop built for a course assignment. It is not
> affiliated with, endorsed by, or a partner of Yale University.

---

## Quick start

**0. Install.** Python 3.11+ and Node 18+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Credentials: the agents call `gpt-6-luna` through the Portkey gateway. Copy the
template and fill it in — or export the two variables, or leave them in
`~/.config/ai-keys/keys.env`, which is checked last.

```bash
cp .env.example .env     # then set PORTKEY_API_KEY and PORTKEY_BASE_URL
```

**1. Get a clean database.** The pristine original is `data/campus_customs.db`
and is never written to. Everything writes to the working copy. Copy one over
the other whenever you want a clean run:

```bash
cp data/campus_customs.db data/campus_customs_new.db   # or: ./scripts/reset_db.sh
```

**2. The MCP server** — every agent's only route to the database. The backend
starts it automatically as a subprocess, so you only need this to poke at the
tools yourself:

```bash
./.venv/bin/python -m mcp_server.server    # stdio transport
```

**3. The FastAPI backend**, from the `backend/` folder:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

**4. The React board**, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The board calls the API at http://localhost:8000,
which allows any localhost origin.

**5. Before a full three-ticket run, reset the database** so the board starts
clean:

```bash
./scripts/reset_db.sh
```

Then work the tickets from the board — pick one, *Send the team in*, approve the
payment it proposes — or from the command line:

```bash
./.venv/bin/python -m backend.run_board --ticket 101   # one ticket
./.venv/bin/python -m backend.run_board                # the whole board
./.venv/bin/python scripts/approve.py --list           # payments waiting on a human
./.venv/bin/python scripts/approve.py 1 --by "Your Name"
```

A first pass ends with proposals and open tickets — that is the system working.
Approve a payment and run again, and the agents can pay **that one** and close
what is finished.

---

## Layout

```
hw5/
├── AI_prompts.md        # every prompt used to build this, with its date
├── RULES.md             # the shop rules every agent and tool obeys
├── requirements.txt
├── .env.example         # environment template (copy to .env; .env is git-ignored)
├── .mcp.json            # registers the MCP server with Claude Code
├── README.md
├── data/
│   ├── campus_customs.db       # the original — never written to
│   └── campus_customs_new.db   # the working copy — tools write here
├── mcp_server/          # the only route to the database
│   ├── server.py        # the nine tools
│   ├── queries.py       # the SQL behind them, and the guardrails
│   ├── db.py            # connections; reads open read-only
│   └── README.md
├── backend/             # the agent team and the API
│   ├── main.py          # FastAPI app — the dashboard calls this
│   ├── models.py        # the types the team and the API pass around
│   ├── boss.py  inventory.py  accounting.py  facilities.py  customer_service.py
│   ├── base.py  settings.py  toolset.py  audit.py  run_board.py
│   └── prompts/         # one prompt per agent, plus _shared.md house rules
├── frontend/            # React + Vite + TypeScript dashboard
├── scripts/
│   ├── reset_db.sh      # restore the working copy from the original
│   ├── approve.py       # the human's approval tool — agents cannot call it
│   ├── mcp_smoke.py     # tool output vs the database, 22 checks
│   ├── build_desk_page.py  build_resolved.py  collect_actuals.py
└── output/              # the write-ups and the evidence
```

## The database

Eleven tables. Nine came with the assignment — `desk`, `tickets`, `inventory`,
`pricing`, `vendors`, `invoices`, `leases`, `cash_accounts`, `payments` — and
two are created on the working copy at first write: `approvals` and `drafts`.
Walked through in [output/data_model.md](output/data_model.md).

`desk.date_today` is the shop's date (2026-08-31). Everything overdue is
measured against it, never the real clock.

## The team

| Agent | Owns | Delegates to |
| --- | --- | --- |
| **Boss** | triage, deciding, closing | all four |
| **Inventory** | stock, shortfalls, resupply | — |
| **Accounting** | cash, invoices, proposing and paying | — |
| **Facilities** | leases, landlords, rent | — |
| **Customer Service** | the reply to the requester | Inventory |

All five run `gpt-6-luna` and nothing else: one factory builds the model and
refuses any other name.

## Safety

**No payment executes without explicit human approval.** Agents may only
propose; `pay` refuses when no approval is recorded, and refuses anything that
would push a cash account below zero.

It holds because of where it lives, not because a prompt says so:
`approve_payment` is filtered out of the agents' toolset, `pay` reads the
`approvals` table at the moment of payment, read tools open the database
read-only, and no tool can send mail or contact a vendor. The full list, and the
tests behind it, are in [output/harness.md](output/harness.md) §4.3.

## The API

| Route | Does |
| --- | --- |
| `GET /api/tickets` | the three tickets, each open or resolved |
| `GET /api/tickets/{id}` | one ticket with every link resolved |
| `POST /api/tickets/{id}/run` | runs the team on one ticket, in the background |
| `GET /api/runs/{run_id}` | where that run got to, and its review |
| `GET /api/events` | recent agent events — who said what, which tools ran |
| `GET /api/approvals` | payments the agents have proposed |
| `POST /api/approvals/{id}` | **a human approves — the only route that changes cash** |
| `GET /api/cash` | the checking balance |
| `POST /api/reset` | restore the database from the original |

Interactive docs at `/docs` once it is running.

## Documentation

| File | What |
| --- | --- |
| [output/harness.md](output/harness.md) | how the whole system works, problem by problem |
| [output/data_model.md](output/data_model.md) | the database and how the tickets link |
| [output/design.md](output/design.md) | why the dashboard looks as it does |
| [output/desk_tickets.html](output/desk_tickets.html) | per ticket: Expected, Actual, the cash ledger, the reflection |
| [output/resolved_board.html](output/resolved_board.html) | the board ticket by ticket, with screenshots |
| [output/resolved_tickets.json](output/resolved_tickets.json) | per ticket: status, outcome, agent contributions, approvals |
| [output/audit_trail.json](output/audit_trail.json) | every run this system has done, appended |
| [output/mcp_smoke.json](output/mcp_smoke.json) | tool output checked against the database |
