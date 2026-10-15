import type { CSSProperties } from 'react'
import { AGENTS, STATUS_LABEL } from '../agents'
import type { AgentStatus } from '../agents'

// The team, each with its own colour and glyph. A status pill says where each
// one is in this run, and whoever is working gets a glowing ring — so who is
// busy is readable at a glance, without reading the feed.

interface Props {
  statuses: Record<string, AgentStatus>
}

export function AgentRoster({ statuses }: Props) {
  return (
    <ul className="roster">
      {AGENTS.map((agent) => {
        const status: AgentStatus = statuses[agent.key] ?? 'idle'
        return (
          <li
            key={agent.key}
            className={`roster-item is-${status}`}
            style={{ '--agent': agent.color } as CSSProperties}
            title={agent.role}
          >
            <span className="roster-icon" aria-hidden="true">
              {agent.icon}
            </span>
            <span className="roster-text">
              <span className="roster-name">{agent.label}</span>
              <span className="roster-role">{agent.role}</span>
            </span>
            <span className={`roster-pill pill-${status}`}>{STATUS_LABEL[status]}</span>
          </li>
        )
      })}
    </ul>
  )
}
