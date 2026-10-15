# hw5

Scaffold for the hw5 assignment. The shop rules are in [RULES.md](RULES.md) and
the database is walked through in [output/data_model.md](output/data_model.md);
the problem list is still to come. The layout below follows the conventions used
in `hw3/` and `hw4/`.

## Repository layout

```
hw5/
├── .mcp.json           # MCP connection config — registers the server with Claude
├── RULES.md            # the shop rules every agent and tool must obey
├── AI_prompts.md       # log of the prompts used to build this
├── requirements.txt    # Python deps
├── .env.example        # environment template (copy to .env)
├── .gitignore
├── README.md
├── mcp_server/         # FastMCP server — every agent's only route to the db
│   ├── README.md       # what it is for, which db, and the three tools
│   ├── server.py       # the tools
│   ├── queries.py      # the SQL behind them
│   └── db.py           # connections (reads open read-only)
├── backend/            # the PydanticAI agent team
│   ├── boss.py         # triage + delegation; review_board()
│   ├── inventory.py  accounting.py  facilities.py  customer_service.py
│   ├── base.py         # one builder: one model, the MCP tools, a typed output
│   ├── settings.py     # the only place a model client is made (gpt-6-luna)
│   ├── toolset.py      # the shared MCP toolset
│   ├── models.py       # the types the team passes around
│   ├── main.py         # the FastAPI app the dashboard calls
│   ├── run_board.py    # CLI: python -m backend.run_board
│   └── prompts/        # one prompt per agent, plus _shared.md house rules
├── prompts/            # system / task prompts
├── scripts/reset_db.sh # restore the working db from the original
├── scripts/approve.py  # the human's approval tool (agents cannot call it)
├── scripts/mcp_smoke.py# tool-vs-database evidence
├── data/               # data pack (not committed)
└── output/             # write-ups and generated artefacts
```

## The database

The data pack is **not** committed. Two files live in `data/`:

| File | Role |
| --- | --- |
| `campus_customs.db` | the original shop database — **never written to** (kept read-only) |
| `campus_customs_new.db` | the working copy — the MCP server and backend point here, and tools write to it as tickets get resolved |

To start the tickets over from scratch:

```bash
./scripts/reset_db.sh
```

## Running the team

```bash
./scripts/reset_db.sh                              # start from a clean board
./.venv/bin/python -m backend.run_board            # the whole board
./.venv/bin/python -m backend.run_board --ticket 102
```

Agents can only *propose* payments. To approve one, as a person:

```bash
./.venv/bin/python scripts/approve.py --list
./.venv/bin/python scripts/approve.py 2 --by "Your Name"
```

Then run the board again and the approved payment — and only that one — goes
through. Every run appends to `output/audit_trail.json`.

## The dashboard

```bash
cd frontend
npm install
npm run dev
```

Opens on http://localhost:5173 and calls the API at http://localhost:8000, which
allows that origin. `VITE_API_BASE` points it elsewhere; set it to an empty
string to go through Vite's proxy instead. The look is explained in
[output/design.md](output/design.md).

## The API

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Serves on http://localhost:8000, where the dashboard looks. From the project
root the same app is `backend.main:app`.

| Route | Does |
| --- | --- |
| `GET /api/tickets` | the three tickets, each open or resolved |
| `POST /api/tickets/{id}/run` | runs the agent team on one ticket, in the background |
| `GET /api/runs/{run_id}` | where that run got to, and its review |
| `GET /api/events` | recent agent events — who said what, which tools ran |
| `GET /api/approvals` | payments the agents have proposed |
| `POST /api/approvals/{id}` | **a human approves — the only route that changes cash** |
| `GET /api/cash` | the checking balance |
| `POST /api/reset` | restore the database from the original |

Interactive docs at `/docs` once it is running.

Nine tables — `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `invoices`,
`leases`, `cash_accounts`, `payments` — walked through in
[output/data_model.md](output/data_model.md), along with how the three open
tickets link to each other.

## Setup

```bash
cp .env.example .env    # then fill in PORTKEY_API_KEY and PORTKEY_BASE_URL
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The venv is required before the MCP server can be connected: `.mcp.json` runs
`./.venv/bin/python -m mcp_server.server`, and `.venv/` is not committed.
