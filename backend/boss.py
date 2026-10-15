"""The Boss — triages the board and delegates to the four specialists.

Delegation runs one way, so the team cannot talk in circles:

    Boss ─┬─> Inventory ──────────────┐
          ├─> Accounting              │  (Customer Service may ask
          ├─> Facilities              │   Inventory, and nothing
          └─> Customer Service ───────┘   asks the Boss)

Every delegated run is passed `ctx.usage`, so the whole team shares one request
budget rather than one per agent.
"""

from __future__ import annotations

from pydantic_ai import RunContext

from . import audit
from pydantic_ai.usage import UsageLimits

from .accounting import accounting_agent
from .base import MAX_REQUESTS_PER_RUN, build_agent, run_agent
from .customer_service import customer_service_agent
from .facilities import facilities_agent
from .inventory import inventory_agent
from .models import (
    BoardReview,
    DraftReply,
    MoneyAssessment,
    RentAssessment,
    StockAssessment,
)

boss_agent = build_agent("boss", BoardReview, name="boss")


@boss_agent.tool
async def ask_inventory(
    ctx: RunContext[None], ticket_id: int, question: str
) -> StockAssessment:
    """Ask Inventory about stock, shortfalls, or whether a vendor can resupply.

    Args:
        ticket_id: The ticket this question is about.
        question: What you need to know. Be specific.
    """
    audit.append("delegation", requested_by="boss", asked="inventory",
                 ticket_id=ticket_id, question=audit.summarise(question))
    result = await run_agent(
        inventory_agent, f"Ticket {ticket_id}. {question}",
        usage=ctx.usage, delegated_by="boss",
    )
    return result.output


@boss_agent.tool
async def ask_accounting(
    ctx: RunContext[None], question: str, ticket_id: int | None = None
) -> MoneyAssessment:
    """Ask Accounting what is owed, what fits in cash, and what to propose paying.

    Args:
        question: What you need to know. Be specific.
        ticket_id: The ticket this is about, if it is about one.
    """
    prefix = f"Ticket {ticket_id}. " if ticket_id is not None else ""
    audit.append("delegation", requested_by="boss", asked="accounting",
                 ticket_id=ticket_id, question=audit.summarise(question))
    result = await run_agent(
        accounting_agent, f"{prefix}{question}", usage=ctx.usage, delegated_by="boss"
    )
    return result.output


@boss_agent.tool
async def ask_facilities(
    ctx: RunContext[None], ticket_id: int, question: str
) -> RentAssessment:
    """Ask Facilities about a lease, a landlord, or when rent falls due.

    Args:
        ticket_id: The ticket this question is about.
        question: What you need to know. Be specific.
    """
    audit.append("delegation", requested_by="boss", asked="facilities",
                 ticket_id=ticket_id, question=audit.summarise(question))
    result = await run_agent(
        facilities_agent, f"Ticket {ticket_id}. {question}",
        usage=ctx.usage, delegated_by="boss",
    )
    return result.output


@boss_agent.tool
async def ask_customer_service(
    ctx: RunContext[None], ticket_id: int, what_to_say: str
) -> DraftReply:
    """Ask Customer Service to draft the reply. Call this once the facts are settled.

    Args:
        ticket_id: The ticket to answer.
        what_to_say: The findings the reply must be built on — what is true,
            what cannot be promised, and anything the requester must be told.
    """
    audit.append("delegation", requested_by="boss", asked="customer_service",
                 ticket_id=ticket_id, question=audit.summarise(what_to_say))
    result = await run_agent(
        customer_service_agent,
        f"Draft the reply for ticket {ticket_id}. {what_to_say}",
        usage=ctx.usage, delegated_by="boss",
    )
    return result.output


DEFAULT_INSTRUCTION = (
    "Work the board. List the open tickets, read each one, delegate what you "
    "cannot settle yourself, and report what should happen — including the "
    "order payments should be made in and what each one leaves in the account."
)


async def review_board(
    instruction: str = DEFAULT_INSTRUCTION, *, new_run: bool = True
) -> BoardReview:
    """Run the team over the open tickets and return the Boss's review.

    The team may now proposes payments and write drafts, but it still cannot
    move money: `pay` refuses without a human approval already recorded.

    Args:
        instruction: What the Boss should work on.
        new_run: Start a fresh audit run id. The API server sets this false
            when it has already opened one so it can report the id to the
            browser before the run finishes.
    """
    if new_run:
        audit.start_run()
    audit.append("run_started", instruction=audit.summarise(instruction))
    async with boss_agent:  # opens the shared MCP server once for the whole run
        try:
            result = await boss_agent.run(
                instruction,
                usage_limits=UsageLimits(request_limit=MAX_REQUESTS_PER_RUN),
            )
        except Exception as exc:
            audit.append("run_finished", ok=False, error=f"{type(exc).__name__}: {exc}")
            raise

    audit.append(
        "run_finished",
        ok=True,
        requests=result.usage.requests,
        tokens=result.usage.total_tokens,
        tickets=[o.ticket_id for o in result.output.outcomes],
    )
    return result.output
