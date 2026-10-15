// Every call the dashboard makes. Vite proxies /api to the backend on :8000,
// so these stay relative and same-origin in development.

import type {
  Approval,
  BoardState,
  CashBalance,
  EventPage,
  PaymentResult,
  RunHandle,
} from './types'

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(await describe(response))
  return response.json() as Promise<T>
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) throw new Error(await describe(response))
  return response.json() as Promise<T>
}

/** FastAPI puts the useful part in `detail`; keep it rather than "500". */
async function describe(response: Response): Promise<string> {
  try {
    const data = await response.json()
    return typeof data?.detail === 'string' ? data.detail : JSON.stringify(data)
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

export const api = {
  board: () => get<BoardState>('/api/tickets'),
  cash: () => get<CashBalance>('/api/cash'),
  approvals: () => get<Approval[]>('/api/approvals'),
  run: (ticketId: number) => post<RunHandle>(`/api/tickets/${ticketId}/run`),
  runStatus: (runId: string) => get<RunHandle>(`/api/runs/${runId}`),
  events: (runId: string, afterSeq: number) =>
    get<EventPage>(`/api/events?run_id=${runId}&after_seq=${afterSeq}&limit=200`),
  approve: (approvalId: number, approvedBy: string) =>
    post<PaymentResult>(`/api/approvals/${approvalId}`, {
      approved_by: approvedBy,
      decision: 'approved',
      pay_now: true,
    }),
  decline: (approvalId: number, approvedBy: string) =>
    post<PaymentResult>(`/api/approvals/${approvalId}`, {
      approved_by: approvedBy,
      decision: 'declined',
      pay_now: false,
    }),
  reset: () => post<{ reset: boolean; cash: number }>('/api/reset'),
}
