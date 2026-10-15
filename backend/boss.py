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
from pydantic_ai.usage import UsageLimits

from .accounting import accounting_agent
from .base import MAX_REQUESTS_PER_RUN, build_agent
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
    result = await inventory_agent.run(
        f"Ticket {ticket_id}. {question}", usage=ctx.usage
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
    result = await accounting_agent.run(f"{prefix}{question}", usage=ctx.usage)
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
    result = await facilities_agent.run(
        f"Ticket {ticket_id}. {question}", usage=ctx.usage
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
    result = await customer_service_agent.run(
        f"Draft the reply for ticket {ticket_id}. {what_to_say}", usage=ctx.usage
    )
    return result.output


DEFAULT_INSTRUCTION = (
    "Work the board. List the open tickets, read each one, delegate what you "
    "cannot settle yourself, and report what should happen — including the "
    "order payments should be made in and what each one leaves in the account."
)


async def review_board(instruction: str = DEFAULT_INSTRUCTION) -> BoardReview:
    """Run the team over the open tickets and return the Boss's review.

    Nothing here writes to the database or pays anything: the tools are
    read-only, and payments come back as `ApprovalRequest`s for a human.
    """
    async with boss_agent:  # opens the shared MCP server once for the whole run
        result = await boss_agent.run(
            instruction,
            usage_limits=UsageLimits(request_limit=MAX_REQUESTS_PER_RUN),
        )
    return result.output
