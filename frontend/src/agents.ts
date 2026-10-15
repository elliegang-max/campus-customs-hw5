// Each agent gets its own colour, used for its chip, its feed items, and the
// ring that glows while it is working. Five hues that sit together on cream.

export interface AgentLook {
  key: string
  label: string
  role: string
  color: string
  /** A workshop glyph, so an agent is recognisable before the label is read. */
  icon: string
}

export const AGENTS: AgentLook[] = [
  { key: 'boss', label: 'Boss', role: 'triage & decisions', color: '#2F4A86', icon: '✦' },
  { key: 'inventory', label: 'Inventory', role: 'stock & restock', color: '#2C7A55', icon: '▦' },
  { key: 'accounting', label: 'Accounting', role: 'cash & payments', color: '#B4581C', icon: '$' },
  { key: 'facilities', label: 'Facilities', role: 'lease & rent', color: '#6B4BA3', icon: '⌂' },
  { key: 'customer_service', label: 'Customer Service', role: 'the reply', color: '#0E7A84', icon: '✉' },
]

/** Where an agent is in the current run. */
export type AgentStatus = 'idle' | 'working' | 'done'

export const STATUS_LABEL: Record<AgentStatus, string> = {
  idle: 'idle',
  working: 'working',
  done: 'done',
}

const BY_KEY = new Map(AGENTS.map((a) => [a.key, a]))

export function agentLook(key: string | null | undefined): AgentLook {
  return (
    (key ? BY_KEY.get(key) : undefined) ?? {
      key: key ?? 'desk',
      label: key ? key.replace(/_/g, ' ') : 'desk',
      role: '',
      color: '#7A6E5D',
      icon: '•',
    }
  )
}
