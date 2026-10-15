import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { AgentFeed } from './components/AgentFeed'
import { AgentRoster } from './components/AgentRoster'
import { ApprovalSlip } from './components/ApprovalSlip'
import { BalanceCard } from './components/BalanceCard'
import { RunSummary } from './components/RunSummary'
import { TicketTag } from './components/TicketTag'
import type { AgentStatus } from './agents'
import type { AgentEvent, Approval, BoardState, CashBalance, RunHandle } from './types'

const POLL_MS = 1500
const DEFAULT_APPROVER = 'Shutong Gang'

export default function App() {
  const [board, setBoard] = useState<BoardState | null>(null)
  const [cash, setCash] = useState<CashBalance | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [run, setRun] = useState<RunHandle | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busyApproval, setBusyApproval] = useState<number | null>(null)
  const [cashFalling, setCashFalling] = useState(false)
  const [approvedBy] = useState(DEFAULT_APPROVER)
  const lastSeq = useRef(0)

  const refresh = useCallback(async () => {
    try {
      const [nextBoard, nextCash, nextApprovals] = await Promise.all([
        api.board(),
        api.cash(),
        api.approvals(),
      ])
      setBoard(nextBoard)
      setCash(nextCash)
      setApprovals(nextApprovals)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // While a run is in flight, pull new events and watch for it to finish. The
  // events are the same records the audit trail keeps, so what the board shows
  // is what gets written down.
  useEffect(() => {
    if (!run || run.status !== 'running') return
    let alive = true

    const tick = async () => {
      try {
        const page = await api.events(run.run_id, lastSeq.current)
        if (!alive) return
        if (page.events.length > 0) {
          lastSeq.current = page.latest_seq
          setEvents((current) => [...current, ...page.events])
        }
        const status = await api.runStatus(run.run_id)
        if (!alive) return
        if (status.status !== 'running') {
          setRun(status)
          void refresh()
        }
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : String(err))
      }
    }

    const timer = window.setInterval(() => void tick(), POLL_MS)
    void tick()
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [run, refresh])

  const running = run?.status === 'running'

  const startRun = async (ticketId: number) => {
    setError(null)
    setNotice(null)
    setEvents([])
    lastSeq.current = 0
    try {
      setRun(await api.run(ticketId))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const decide = async (approvalId: number, approve: boolean) => {
    setBusyApproval(approvalId)
    setError(null)
    setNotice(null)
    try {
      const result = approve
        ? await api.approve(approvalId, approvedBy)
        : await api.decline(approvalId, approvedBy)
      if (result.refused_because) {
        setError(result.refused_because)
      } else if (result.paid) {
        setCashFalling(true)
        setNotice(
          `Paid $${result.amount?.toFixed(2)} — ${result.settled}. ` +
            `Checking is now $${result.cash_after?.toFixed(2)}.`,
        )
        window.setTimeout(() => setCashFalling(false), 1400)
      } else {
        setNotice(`Approval ${approvalId} ${result.decision}.`)
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyApproval(null)
    }
  }

  const resetBoard = async () => {
    if (!window.confirm('Reset the database to the original values?')) return
    try {
      await api.reset()
      setRun(null)
      setEvents([])
      lastSeq.current = 0
      setNotice('Board reset — fresh tickets, nothing paid.')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  // Where each agent is in this run: started and not yet finished = working,
  // finished at least once = done, never called = idle. The Boss is working
  // from the moment the run starts, since it is the one that opens every run.
  const agentStatuses = useMemo(() => {
    const statuses: Record<string, AgentStatus> = {}
    if (events.length > 0 && running) statuses.boss = 'working'
    for (const event of events) {
      const who = event.agent
      if (!who) continue
      if (event.event === 'agent_started') statuses[who] = 'working'
      else if (event.event === 'agent_finished') statuses[who] = 'done'
    }
    if (!running) {
      for (const key of Object.keys(statuses)) {
        if (statuses[key] === 'working') statuses[key] = 'done'
      }
    }
    return statuses
  }, [events, running])

  const pending = approvals.filter((a) => a.status === 'proposed')
  const decided = approvals.filter((a) => a.status !== 'proposed')
  const outcome = run?.review?.outcomes.find((o) => o.ticket_id === run.ticket_id)
  const selectedTicket = board?.tickets.find((t) => t.id === selected) ?? null

  return (
    <div className="desk">
      <header className="topbar">
        <div className="topbar-left">
          <h1>Campus Customs</h1>
          <p className="topbar-sub">
            back office desk
            {board ? ` · ${board.shop_date}` : ''}
          </p>
        </div>
        <div className="topbar-right">
          {cash && (
            <BalanceCard
              balance={cash.balance}
              asOf={cash.as_of}
              account={cash.account}
              falling={cashFalling}
            />
          )}
          <button className="btn btn-quiet" onClick={() => void resetBoard()} disabled={running}>
            Reset board
          </button>
        </div>
      </header>

      {error && (
        <p className="banner banner-error" role="alert">
          {error}
        </p>
      )}
      {notice && !error && <p className="banner banner-ok">{notice}</p>}

      <main className="columns">
        <section className="col col-tickets">
          <h2 className="col-head">
            Tickets
            {board && (
              <span className="col-count">
                {board.open_count} open · {board.resolved_count} resolved
              </span>
            )}
          </h2>

          <div className="tags">
            {board?.tickets.map((ticket) => (
              <TicketTag
                key={ticket.id}
                ticket={ticket}
                selected={selected === ticket.id}
                running={running && run?.ticket_id === ticket.id}
                onSelect={setSelected}
              />
            ))}
          </div>

          <button
            className="btn btn-accent btn-send"
            disabled={selected == null || running}
            onClick={() => selected != null && void startRun(selected)}
          >
            {running
              ? `Team is working ticket #${run?.ticket_id}…`
              : selectedTicket
                ? `Send the team in on #${selectedTicket.id}`
                : 'Pick a ticket'}
          </button>
        </section>

        <section className="col col-feed">
          <h2 className="col-head">
            The team
            {running && <span className="col-count live">live</span>}
          </h2>
          <AgentRoster statuses={agentStatuses} />
          <AgentFeed events={events} running={running} />
          {run?.status === 'failed' && (
            <p className="banner banner-error">run failed: {run.error}</p>
          )}
          {outcome && <RunSummary outcome={outcome} />}
        </section>

        <section className="col col-money">
          <h2 className="col-head">
            Approvals
            {pending.length > 0 && <span className="col-count urgent">{pending.length} waiting</span>}
          </h2>

          {pending.length === 0 && decided.length === 0 && (
            <p className="muted">
              Nothing to approve. The agents put payments here; they cannot sign them.
            </p>
          )}

          {pending.map((approval) => (
            <ApprovalSlip
              key={approval.id}
              approval={approval}
              approvedBy={approvedBy}
              busy={busyApproval === approval.id}
              onApprove={(id) => void decide(id, true)}
              onDecline={(id) => void decide(id, false)}
            />
          ))}

          {decided.length > 0 && (
            <>
              <h3 className="col-sub">Settled</h3>
              {decided.map((approval) => (
                <ApprovalSlip
                  key={approval.id}
                  approval={approval}
                  approvedBy={approvedBy}
                  busy={false}
                  onApprove={() => undefined}
                  onDecline={() => undefined}
                />
              ))}
            </>
          )}
        </section>
      </main>

      <footer className="deskfoot">
        No agent can pay anything. A payment is proposed, a person signs it here, and only
        then does the balance move.
      </footer>
    </div>
  )
}
