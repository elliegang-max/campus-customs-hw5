import { useState } from 'react'
import type { Approval } from '../types'

// A payment the agents prepared, drawn as a till receipt. The agents cannot
// approve their own proposals — this slip is the only way one gets signed, and
// the button is what actually moves the money.

const KIND_LABEL: Record<string, string> = { invoice: 'vendor invoice', rent: 'rent' }

interface Props {
  approval: Approval
  approvedBy: string
  busy: boolean
  onApprove: (id: number) => void
  onDecline: (id: number) => void
}

export function ApprovalSlip({ approval, approvedBy, busy, onApprove, onDecline }: Props) {
  const [confirming, setConfirming] = useState(false)
  const pending = approval.status === 'proposed'
  const spent = approval.status === 'used'

  return (
    <article className={`slip ${pending ? 'is-pending' : ''} ${spent ? 'is-spent' : ''}`}>
      <header className="slip-head">
        <span className="slip-shop">CAMPUS CUSTOMS</span>
        <span className="slip-no">approval #{approval.id}</span>
      </header>

      <dl className="slip-rows">
        <div>
          <dt>{KIND_LABEL[approval.kind] ?? approval.kind}</dt>
          <dd>#{approval.ref_id}</dd>
        </div>
        <div>
          <dt>from</dt>
          <dd>{approval.account}</dd>
        </div>
        <div>
          <dt>proposed by</dt>
          <dd>{approval.requested_by}</dd>
        </div>
      </dl>

      {approval.reason && <p className="slip-reason">{approval.reason}</p>}

      <p className="slip-total">
        <span>TOTAL</span>
        <span className="slip-amount">${approval.amount.toFixed(2)}</span>
      </p>

      {pending ? (
        confirming ? (
          <div className="slip-confirm">
            <p>
              Pay <strong>${approval.amount.toFixed(2)}</strong> as {approvedBy}?
            </p>
            <div className="slip-actions">
              <button className="btn btn-accent" disabled={busy} onClick={() => onApprove(approval.id)}>
                {busy ? 'paying…' : 'Yes, pay it'}
              </button>
              <button className="btn btn-quiet" disabled={busy} onClick={() => setConfirming(false)}>
                Back
              </button>
            </div>
          </div>
        ) : (
          <div className="slip-actions">
            <button className="btn btn-accent" disabled={busy} onClick={() => setConfirming(true)}>
              Approve
            </button>
            <button className="btn btn-quiet" disabled={busy} onClick={() => onDecline(approval.id)}>
              Decline
            </button>
          </div>
        )
      ) : (
        <p className="slip-decided">
          {spent ? 'PAID' : approval.status.toUpperCase()}
          {approval.approved_by ? ` · ${approval.approved_by}` : ''}
          {approval.decided_at ? ` · ${approval.decided_at}` : ''}
        </p>
      )}
    </article>
  )
}
