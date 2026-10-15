// The shapes the API hands back. These mirror backend/models.py — the names are
// the same on purpose, so a change there is easy to find here.

export type TicketStatus = 'open' | 'resolved' | string

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: TicketStatus
  sku: string | null
  size: string | null
  qty: number | null
  notes: string | null
  created_at: string
}

export interface BoardState {
  shop_date: string
  tickets: Ticket[]
  open_count: number
  resolved_count: number
}

export interface CashBalance {
  account: string
  balance: number
  as_of: string
}

export interface Approval {
  id: number
  kind: 'invoice' | 'rent' | string
  ref_id: number
  amount: number
  account: string
  reason: string | null
  requested_by: string
  status: 'proposed' | 'approved' | 'declined' | 'used' | string
  approved_by: string | null
  decided_at: string | null
}

export interface PaymentResult {
  approval_id: number
  decision: string
  paid: boolean
  payment_id: number | null
  amount: number | null
  cash_before: number | null
  cash_after: number | null
  settled: string | null
  refused_because: string | null
}

export interface AgentEvent {
  run_id: string
  seq: number
  at: string
  event: string
  agent: string | null
  tool: string | null
  asked: string | null
  requested_by: string | null
  delegated_by: string | null
  ticket_id: number | null
  ok: boolean | null
  error: string | null
  ms: number | null
  detail: string | null
}

export interface EventPage {
  events: AgentEvent[]
  latest_seq: number
  total: number
}

export interface ApprovalRequest {
  kind: string
  ref_id: number
  payee: string
  amount: number
  account: string
  reason: string
  cash_before: number
  cash_after: number
  unblocks: number[]
  urgency: string
  approved: boolean | null
}

export interface TicketOutcome {
  ticket_id: number
  kind: string
  requester: string
  delegated_to: string[]
  finding: string
  recommended_action: string
  needs_human: boolean
  approval_requests: ApprovalRequest[]
  draft_reply: { to: string; subject: string; body: string; sent: boolean } | null
  resolved: boolean
}

export interface BoardReview {
  shop_date: string
  cash_available: number
  outcomes: TicketOutcome[]
  spending_plan: string[]
  summary: string
}

export interface RunHandle {
  run_id: string
  ticket_id: number | null
  status: 'running' | 'finished' | 'failed'
  started_at: string
  finished_at: string | null
  error: string | null
  review: BoardReview | null
}
