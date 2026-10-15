"""Customer Service — drafts the reply to whoever raised the ticket.

The only agent that delegates sideways: before promising a customer anything it
asks Inventory what is actually true. That edge exists because a reply written
from the ticket alone is exactly where invented delivery dates come from.
"""

from __future__ import annotations

from pydantic_ai import RunContext

from .base import build_agent
from .inventory import inventory_agent
from .models import DraftReply, StockAssessment

customer_service_agent = build_agent(
    "customer_service", DraftReply, name="customer_service"
)


@customer_service_agent.tool
async def ask_inventory(
    ctx: RunContext[None], ticket_id: int, question: str
) -> StockAssessment:
    """Ask Inventory what is in stock, or when a restock could arrive.

    Args:
        ticket_id: The ticket being answered.
        question: What you need to know before you can write the reply.
    """
    result = await inventory_agent.run(
        f"Ticket {ticket_id}. {question}",
        usage=ctx.usage,  # one budget for the whole team run
    )
    return result.output
