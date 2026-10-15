import type { CSSProperties } from 'react'
import { AGENTS } from '../agents'

// The team, each with its own colour. Whoever is working gets a glowing ring.

export function AgentRoster({ active }: { active: string | null }) {
  return (
    <ul className="roster">
      {AGENTS.map((agent) => (
        <li
          key={agent.key}
          className={`roster-item ${active === agent.key ? 'is-active' : ''}`}
          style={{ '--agent': agent.color } as CSSProperties}
        >
          <span className="roster-dot" aria-hidden="true" />
          <span className="roster-name">{agent.label}</span>
          <span className="roster-role">{agent.role}</span>
        </li>
      ))}
    </ul>
  )
}
