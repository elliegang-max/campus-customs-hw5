import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { agentLook } from '../agents'
import type { AgentEvent } from '../types'

// What each agent is saying and doing, newest at the bottom, sliding in as it
// arrives. Failures are shown, not hidden: a refused payment is the most
// interesting line in the feed.

function line(event: AgentEvent): { title: string; detail?: string } {
  switch (event.event) {
    case 'run_started':
      return { title: 'run started', detail: event.detail ?? undefined }
    case 'run_finished':
      return { title: event.ok === false ? 'run failed' : 'run finished', detail: event.error ?? undefined }
    case 'agent_started':
      return {
        title: event.delegated_by ? `called in by ${agentLook(event.delegated_by).label}` : 'started',
        detail: event.detail ?? undefined,
      }
    case 'agent_finished':
      return { title: event.ok === false ? 'failed' : 'answered', detail: event.error ?? event.detail ?? undefined }
    case 'delegation':
      return { title: `asks ${agentLook(event.asked).label}`, detail: event.detail ?? undefined }
    case 'tool_call':
      return {
        title: `${event.ok === false ? 'refused by' : 'used'} ${event.tool}`,
        detail: event.ok === false ? event.error ?? undefined : event.detail ?? undefined,
      }
    case 'database_reset':
      return { title: 'database reset' }
    default:
      return { title: event.event, detail: event.detail ?? undefined }
  }
}

export function AgentFeed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [events.length])

  if (events.length === 0) {
    return (
      <div className="feed-empty">
        {running ? 'waking the team…' : 'Pick a ticket and send the team in.'}
      </div>
    )
  }

  return (
    <ol className="feed">
      {events.map((event) => {
        const who = agentLook(event.agent ?? event.requested_by)
        const { title, detail } = line(event)
        const failed = event.ok === false
        return (
          <li
            key={`${event.run_id}-${event.seq}`}
            className={`feed-item ${failed ? 'is-failed' : ''}`}
            style={{ '--agent': who.color } as CSSProperties}
          >
            <span className="feed-who">{who.label}</span>
            <div className="feed-body">
              <p className="feed-title">{title}</p>
              {detail && <p className="feed-detail">{detail}</p>}
            </div>
            {event.ms != null && <span className="feed-ms">{event.ms}ms</span>}
          </li>
        )
      })}
      <div ref={end} />
    </ol>
  )
}
