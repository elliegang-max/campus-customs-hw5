# hw5

Scaffold for the hw5 assignment. The shop rules are in [RULES.md](RULES.md) and
the database is walked through in [output/data_model.md](output/data_model.md);
the problem list is still to come. The layout below follows the conventions used
in `hw3/` and `hw4/`.

## Repository layout

```
hw5/
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
├── prompts/            # system / task prompts
├── scripts/reset_db.sh # restore the working db from the original
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
