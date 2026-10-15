"""The API the dashboard calls.

    ./.venv/bin/python -m uvicorn backend.main:app --reload --port 8000

Two rules shape this file:

* **Shop facts come from the MCP server.** Every read and every write goes
  through the same tools the agents use — there is no second query layer here.
  The one exception is `POST /api/reset`, which copies a file; that is an
  operator action on the database, not a fact about the shop.
* **The agents still cannot move money.** They propose. `POST
  /api/approvals/{id}` is the human's click: it records the approval and then
  calls `pay`, which is where cash actually changes. If the approval is missing
  or the balance cannot take it, `pay` refuses and the refusal is handed back
  rather than hidden.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from . import audit
from .boss import review_board
from .models import (
    AgentEvent,
    ApprovalDecision,
    ApprovalSummary,
    BoardState,
    CashBalance,
    EventPage,
    PaymentResult,
    ResetResult,
    RunHandle,
    TicketSummary,
)
from .settings import PROJECT_ROOT

ORIGINAL_DB = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DB = PROJECT_ROOT / "data" / "campus_customs_new.db"

#: One MCP connection for the API's own reads and writes, opened at startup.
_mcp: Client | None = None

#: Board runs this process has started, newest last.
_runs: dict[str, RunHandle] = {}

#: One run at a time: the team shares a database, and two boards at once would
#: have them proposing against each other's half-finished state.
_run_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _mcp
    transport = StdioTransport(
        command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(PROJECT_ROOT)
    )
    _mcp = Client(transport)
    async with _mcp:
        yield
    _mcp = None


app = FastAPI(
    title="Campus Customs back office",
    summary="The desk, for the dashboard to draw.",
    lifespan=lifespan,
)

# The dashboard is served by Vite in development, on a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def tool(name: str, args: dict[str, Any] | None = None) -> Any:
    """Call an MCP tool, turning a refusal into a readable HTTP error."""
    if _mcp is None:  # pragma: no cover - only before startup
        raise HTTPException(503, "the MCP server is not connected yet")
    try:
        result = await _mcp.call_tool(name, args or {})
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return result.structured_content or json.loads(result.content[0].text)


# --- the board --------------------------------------------------------------


@app.get("/api/tickets", response_model=BoardState)
async def get_tickets() -> BoardState:
    """The three tickets, each with whether it is open or resolved."""
    data = await tool("list_tickets", {"status": None})
    tickets = [TicketSummary(**t) for t in data["tickets"]]
    return BoardState(
        shop_date=data["today"],
        tickets=tickets,
        open_count=sum(t.status == "open" for t in tickets),
        resolved_count=sum(t.status != "open" for t in tickets),
    )


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket with everything it links to — stock, invoice, lease, cash."""
    return await tool("get_ticket", {"ticket_id": ticket_id})


# --- running the team -------------------------------------------------------


async def _work_ticket(run_id: str, ticket_id: int) -> None:
    """Run the team in the background so the board can watch it happen."""
    handle = _runs[run_id]
    try:
        async with _run_lock:
            review = await review_board(
                f"Work ticket {ticket_id} only. Read it, delegate what you cannot "
                "settle yourself, and report what should happen with it.",
                new_run=False,  # the run id is already open, and already reported
            )
        handle.review = review
        handle.status = "finished"
    except Exception as exc:
        handle.status = "failed"
        handle.error = f"{type(exc).__name__}: {exc}"
    finally:
        handle.finished_at = _now()


@app.post("/api/tickets/{ticket_id}/run", response_model=RunHandle, status_code=202)
async def run_ticket(ticket_id: int) -> RunHandle:
    """Run the agent team on one ticket.

    Returns immediately with a run id: a board run takes a minute or two, so the
    dashboard polls `/api/events` to watch it and `/api/runs/{id}` for the
    result. Nothing here can move money.
    """
    board = await get_tickets()
    if ticket_id not in {t.id for t in board.tickets}:
        raise HTTPException(404, f"no ticket {ticket_id} on the board")
    if _run_lock.locked():
        raise HTTPException(409, "a board run is already in progress")

    run_id = audit.start_run()
    handle = RunHandle(
        run_id=run_id, ticket_id=ticket_id, status="running", started_at=_now()
    )
    _runs[run_id] = handle
    asyncio.create_task(_work_ticket(run_id, ticket_id))
    return handle


@app.get("/api/runs/{run_id}", response_model=RunHandle)
async def get_run(run_id: str) -> RunHandle:
    """Where a run got to, and its review once it finished."""
    if run_id not in _runs:
        raise HTTPException(404, f"no run {run_id} in this process")
    return _runs[run_id]


# --- what the agents did ----------------------------------------------------

#: Which audit field carries the readable detail, per event type.
_DETAIL_FIELDS = ("prompt", "question", "output", "result", "instruction", "arguments")


def _to_event(record: dict[str, Any]) -> AgentEvent:
    detail = next(
        (record[f] for f in _DETAIL_FIELDS if record.get(f) not in (None, "")), None
    )
    if isinstance(detail, (dict, list)):
        detail = json.dumps(detail, default=str)
    return AgentEvent(
        run_id=record["run_id"],
        seq=record["seq"],
        at=record["at"],
        event=record["event"],
        agent=record.get("agent"),
        tool=record.get("tool"),
        asked=record.get("asked"),
        requested_by=record.get("requested_by"),
        delegated_by=record.get("delegated_by"),
        ticket_id=record.get("ticket_id"),
        ok=record.get("ok"),
        error=record.get("error"),
        ms=record.get("ms"),
        detail=(detail[:800] if isinstance(detail, str) else None),
    )


@app.get("/api/events", response_model=EventPage)
async def get_events(
    limit: int = Query(60, ge=1, le=500),
    after_seq: int | None = Query(None, description="Only events newer than this."),
    run_id: str | None = Query(None, description="Only this run."),
) -> EventPage:
    """Recent agent events: what each agent said and which tools it used.

    Straight off the audit trail, so what the dashboard shows is the same record
    that gets kept — including the failures. Poll with `after_seq` set to the
    previous `latest_seq` to get only what is new.
    """
    records = audit.read_all()
    if run_id:
        records = [r for r in records if r.get("run_id") == run_id]
    if after_seq is not None:
        records = [r for r in records if r.get("seq", 0) > after_seq]

    page = records[-limit:]
    return EventPage(
        events=[_to_event(r) for r in page],
        latest_seq=max((r.get("seq", 0) for r in records), default=after_seq or 0),
        total=len(records),
    )


# --- money ------------------------------------------------------------------


@app.get("/api/approvals", response_model=list[ApprovalSummary])
async def get_approvals(status: str | None = None) -> list[ApprovalSummary]:
    """Payments the agents have proposed, and what became of them."""
    data = await tool("list_approvals", {"status": status})
    return [ApprovalSummary(**a) for a in data["approvals"]]


@app.post("/api/approvals/{approval_id}", response_model=PaymentResult)
async def decide_approval(approval_id: int, decision: ApprovalDecision) -> PaymentResult:
    """A human approves (or declines) a proposed payment.

    This is the only route that changes cash. The agents prepare a payment and
    stop; the click lands here, the approval is recorded against the person who
    gave it, and `pay` runs. If `pay` refuses — no approval, already spent, or
    the balance cannot take it — the refusal comes back in
    `refused_because` rather than being swallowed.
    """
    recorded = await tool(
        "approve_payment",
        {
            "approval_id": approval_id,
            "approved_by": decision.approved_by,
            "decision": decision.decision,
        },
    )

    if decision.decision == "declined" or not decision.pay_now:
        return PaymentResult(
            approval_id=approval_id, decision=recorded["status"], paid=False
        )

    try:
        paid = await tool(
            "pay",
            {
                "kind": recorded["kind"],
                "ref_id": recorded["ref_id"],
                "account": recorded["account"],
            },
        )
    except HTTPException as exc:
        # The guardrail refusing is a result, not a server fault.
        return PaymentResult(
            approval_id=approval_id,
            decision=recorded["status"],
            paid=False,
            refused_because=str(exc.detail),
        )

    return PaymentResult(
        approval_id=approval_id,
        decision=recorded["status"],
        paid=True,
        payment_id=paid["payment_id"],
        amount=paid["amount"],
        cash_before=paid["cash_before"],
        cash_after=paid["cash_after"],
        settled=paid["settled"],
    )


@app.get("/api/cash", response_model=CashBalance)
async def get_cash() -> CashBalance:
    """The current checking balance, from `cash_accounts`."""
    ticket = await tool("get_ticket", {"ticket_id": 101})
    accounts = ticket["cash_accounts"]
    checking = next(
        (a for a in accounts if a["name"] == "checking"), accounts[0] if accounts else None
    )
    if checking is None:
        raise HTTPException(500, "no cash account in the database")
    return CashBalance(
        account=checking["name"], balance=checking["balance"], as_of=checking["date"]
    )


# --- starting over ----------------------------------------------------------


@app.post("/api/reset", response_model=ResetResult)
async def reset_database() -> ResetResult:
    """Restore the working copy from the untouched original.

    The only route that does not go through MCP, because it is not a fact about
    the shop: it replaces the database file, the same thing
    `./scripts/reset_db.sh` does. The audit trail is deliberately **not**
    touched — it is append-only, and a reset is itself worth having recorded.
    """
    if _run_lock.locked():
        raise HTTPException(409, "a board run is in progress; let it finish first")
    if not ORIGINAL_DB.exists():
        raise HTTPException(500, f"the original database is missing at {ORIGINAL_DB}")

    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    WORKING_DB.chmod(0o644)
    audit.append("database_reset", by="api", path=str(WORKING_DB.name))

    board = await get_tickets()
    cash = await get_cash()
    return ResetResult(
        reset=True,
        shop_date=board.shop_date,
        cash=cash.balance,
        tickets=board.tickets,
        note="working copy restored from the original; approvals, payments and drafts are gone",
    )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Is the API up, and can it reach the shop?"""
    data = await tool("list_tickets", {"status": None})
    return {
        "ok": True,
        "shop_date": data["today"],
        "tickets": data["count"],
        "runs_this_process": len(_runs),
    }
