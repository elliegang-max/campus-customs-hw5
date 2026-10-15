import type { Ticket } from '../types'

// A ticket is a paper tag: punched hole, string, a little off-square. The
// RESOLVED stamp only appears when the database says so — the board shows the
// shop's state, not what we hope happened.

const KIND_LABEL: Record<string, string> = {
  customer_order: 'customer order',
  rent_notice: 'rent notice',
  price_override: 'price request',
}

interface Props {
  ticket: Ticket
  selected: boolean
  running: boolean
  onSelect: (id: number) => void
}

export function TicketTag({ ticket, selected, running, onSelect }: Props) {
  const resolved = ticket.status !== 'open'
  return (
    <button
      type="button"
      className={[
        'tag',
        selected ? 'is-selected' : '',
        resolved ? 'is-resolved' : '',
        running ? 'is-running' : '',
      ].join(' ')}
      onClick={() => onSelect(ticket.id)}
      aria-pressed={selected}
    >
      <span className="tag-hole" aria-hidden="true" />
      <span className="tag-no">#{ticket.id}</span>
      <span className="tag-kind">{KIND_LABEL[ticket.type] ?? ticket.type}</span>
      <h3 className="tag-subject">{ticket.subject}</h3>
      <p className="tag-requester">{ticket.requester}</p>
      {ticket.sku && (
        <p className="tag-sku">
          {ticket.qty} × {ticket.sku}
          {ticket.size ? ` · ${ticket.size}` : ''}
        </p>
      )}
      <span className={`tag-status ${resolved ? 'resolved' : 'open'}`}>
        {resolved ? ticket.status : 'open'}
      </span>
      {resolved && (
        <span className="stamp" aria-label="resolved">
          RESOLVED
        </span>
      )}
      {running && <span className="tag-working">working…</span>}
    </button>
  )
}
