import type { CSSProperties } from 'react'
import { agentLook } from '../agents'
import type { TicketOutcome } from '../types'

// What the team concluded, once a run finishes: who was consulted, what they
// found, what should happen, and whether a person is still needed.

export function RunSummary({ outcome }: { outcome: TicketOutcome }) {
  return (
    <section className="summary">
      <header className="summary-head">
        <h3>Ticket #{outcome.ticket_id} — what the team did</h3>
        <span className={`pill ${outcome.resolved ? 'pill-done' : 'pill-waiting'}`}>
          {outcome.resolved ? 'resolved' : outcome.needs_human ? 'needs a human' : 'still open'}
        </span>
      </header>

      <p className="summary-label">consulted</p>
      <ul className="summary-chain">
        {outcome.delegated_to.map((key, index) => {
          const look = agentLook(key)
          return (
            <li key={`${key}-${index}`} style={{ '--agent': look.color } as CSSProperties}>
              {look.label}
            </li>
          )
        })}
      </ul>

      <p className="summary-label">found</p>
      <p className="summary-text">{outcome.finding}</p>

      <p className="summary-label">recommends</p>
      <p className="summary-text">{outcome.recommended_action}</p>

      {outcome.draft_reply && (
        <details className="summary-draft">
          <summary>
            draft to {outcome.draft_reply.to}
            <span className="unsent">unsent</span>
          </summary>
          <p className="draft-subject">{outcome.draft_reply.subject}</p>
          <p className="draft-body">{outcome.draft_reply.body}</p>
        </details>
      )}
    </section>
  )
}
