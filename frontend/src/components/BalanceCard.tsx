import { useEffect, useRef, useState } from 'react'

// The biggest number on the page. When it falls after an approved payment it
// counts down rather than jumping, so money leaving the account is something
// you watch happen.

function useCountTo(target: number, ms = 1100) {
  const [shown, setShown] = useState(target)
  const from = useRef(target)

  useEffect(() => {
    const start = performance.now()
    const begin = from.current
    const delta = target - begin
    if (delta === 0) return

    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      // ease-out: fast at first, settling at the end
      const eased = 1 - Math.pow(1 - t, 3)
      setShown(begin + delta * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
      else from.current = target
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, ms])

  return shown
}

interface Props {
  balance: number
  asOf: string
  account: string
  falling: boolean
}

export function BalanceCard({ balance, asOf, account, falling }: Props) {
  const shown = useCountTo(balance)
  const [whole, cents] = shown.toFixed(2).split('.')
  return (
    <section className={`balance ${falling ? 'is-falling' : ''}`} aria-live="polite">
      <p className="balance-label">{account} · as of {asOf}</p>
      <p className="balance-figure">
        <span className="balance-currency">$</span>
        <span className="balance-whole">{Number(whole).toLocaleString('en-US')}</span>
        <span className="balance-cents">.{cents}</span>
      </p>
      <p className="balance-note">
        cash only goes out here — no revenue is modelled
      </p>
    </section>
  )
}
