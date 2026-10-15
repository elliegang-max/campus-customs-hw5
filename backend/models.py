"""Structured types the agent team passes between each other.

Three groups:

- **What a specialist hands back** — `StockAssessment`, `MoneyAssessment`,
  `RentAssessment`, `DraftReply`. Each is the end of one specialist's work and
  the input to the Boss's decision.
- **What needs a human** — `ApprovalRequest`. Nothing in this system spends
  money on its own; a payment is *proposed* as one of these and a person
  decides.
- **What the Boss produces** — `TicketOutcome` and `BoardReview`.

Every field here is meant to be filled from the MCP tools' output. Where a
specialist cannot establish something from the database it says so in
`notes`/`blocked_by` rather than estimating.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# What a ticket can be. Mirrors `tickets.type` in the database.
TicketKind = Literal["customer_order", "rent_notice", "price_override"]

# Which specialist a piece of work belongs to.
Specialist = Literal["inventory", "accounting", "facilities", "customer_service"]


# --- What the specialists hand back ----------------------------------------


class StockAssessment(BaseModel):
    """Inventory's answer: can this be filled, and if not, when?"""

    ticket_id: int
    sku: str | None = None
    size: str | None = None
    quantity_requested: int | None = None
    quantity_on_hand: int | None = None
    short_by: int = Field(0, description="Units missing. 0 means it can be filled now.")
    can_fill_from_stock: bool
    restock_vendor: str | None = Field(
        None, description="Vendor who could supply the shortfall, from the vendors table."
    )
    restock_blocked: bool = Field(
        False, description="True when the vendor will not ship — e.g. an unpaid invoice."
    )
    blocked_by: str | None = Field(
        None, description="Why the vendor will not ship, in the database's own terms."
    )
    earliest_available_date: str | None = Field(
        None, description="Only once the block clears: shop date + the vendor's lead days."
    )
    notes: str = Field("", description="Anything a human needs that the fields do not carry.")


class MoneyAssessment(BaseModel):
    """Accounting's answer: what is owed, what can be afforded, what to pay."""

    ticket_id: int | None = None
    cash_available: float
    obligations: list[str] = Field(
        default_factory=list, description="What is owed, each with its amount and date."
    )
    affordable: bool = Field(
        description="Whether the proposed spend fits in cash without going negative."
    )
    approval_requests: list["ApprovalRequest"] = Field(
        default_factory=list, description="Payments proposed for a human to approve."
    )
    notes: str = ""


class RentAssessment(BaseModel):
    """Facilities' answer: the state of a lease obligation."""

    ticket_id: int
    lease_id: int
    space_name: str
    landlord: str
    monthly_rent: float
    next_due: str
    days_until_due: int = Field(description="Against the shop's date, not today's real date.")
    is_overdue: bool
    notes: str = ""


class DraftReply(BaseModel):
    """Customer Service's answer: a message that stays on the board.

    Nothing in this system sends mail. A draft is written, recorded, and left
    for a person to send.
    """

    ticket_id: int
    to: str = Field(description="The requester named on the ticket.")
    subject: str
    body: str
    promises_made: list[str] = Field(
        default_factory=list,
        description="Every commitment in the body — each must trace to a database value.",
    )
    sent: Literal[False] = Field(
        False, description="Always false. Drafts stay on the board."
    )


# --- What needs a human ----------------------------------------------------


class ApprovalRequest(BaseModel):
    """A payment proposed for human approval. No agent may pay without one."""

    kind: Literal["invoice", "rent"]
    ref_id: int = Field(description="invoices.id for an invoice, leases.id for rent.")
    payee: str
    amount: float
    account: str = "checking"
    reason: str = Field(description="Why this should be paid, in one line.")
    cash_before: float
    cash_after: float = Field(description="Balance if approved. Must not be negative.")
    unblocks: list[int] = Field(
        default_factory=list, description="Ticket ids this payment would unblock."
    )
    urgency: Literal["overdue", "due_soon", "routine"]
    approved: bool | None = Field(
        None, description="None until a human decides. Never set by an agent."
    )


# --- What the Boss produces ------------------------------------------------


class TicketOutcome(BaseModel):
    """The Boss's decision on one ticket."""

    ticket_id: int
    kind: TicketKind
    requester: str
    delegated_to: list[Specialist] = Field(
        default_factory=list, description="Who was asked, in the order they were asked."
    )
    finding: str = Field(description="What the specialists established, in one or two lines.")
    recommended_action: str = Field(description="What should happen next.")
    needs_human: bool = Field(
        description="True when a person must approve a payment or make a judgement call."
    )
    approval_requests: list[ApprovalRequest] = Field(default_factory=list)
    draft_reply: DraftReply | None = None
    resolved: bool = Field(
        description="True only when nothing further is needed from a human or a vendor."
    )


class BoardReview(BaseModel):
    """The Boss's pass over the whole board."""

    shop_date: str = Field(description="desk.date_today — the date every judgement used.")
    cash_available: float
    outcomes: list[TicketOutcome]
    spending_plan: list[str] = Field(
        default_factory=list,
        description="The order payments should happen in, and what each leaves in the account.",
    )
    summary: str


MoneyAssessment.model_rebuild()
