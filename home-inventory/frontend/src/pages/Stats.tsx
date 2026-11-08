import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { type StatRow, type Stats as StatsData, api, formatPrice } from '../api'

const HOME = 'SEK'

/** Amounts paid in anything other than kronor, which are listed rather than converted. */
function foreign(spent: Record<string, number>): string {
  return Object.entries(spent)
    .filter(([currency]) => currency !== HOME)
    .map(([currency, minor]) => formatPrice(minor, currency))
    .join(' · ')
}

function Ranking({ title, rows }: { title: string; rows: StatRow[] }) {
  const largest = Math.max(1, ...rows.map((row) => row.spent[HOME] ?? 0))
  return (
    <section className="stat-section">
      <h2>{title}</h2>
      <ul className="stat-list">
        {rows.map((row) => {
          const amount = row.spent[HOME] ?? 0
          const other = foreign(row.spent)
          return (
            <li key={row.label}>
              <span className="stat-label">
                {row.label}
                <span className="muted numeric"> {row.entries}</span>
              </span>
              <span className="stat-value numeric">
                {amount > 0 || !other ? formatPrice(amount, HOME) : ''}
                {other && <span className="muted"> {amount > 0 ? `+ ${other}` : other}</span>}
              </span>
              <span className="stat-track">
                <span className="stat-bar" style={{ width: `${(amount / largest) * 100}%` }} />
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export default function Stats() {
  const [stats, setStats] = useState<StatsData | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch(() => setFailed(true))
  }, [])

  if (failed) return <p className="muted">The figures could not be loaded. Try reloading the page.</p>

  if (!stats) {
    return (
      <div className="centred">
        <span className="spinner" />
      </div>
    )
  }

  const abroad = foreign(stats.totals)
  const secondHand = stats.second_hand_totals[HOME] ?? 0

  return (
    <>
      <div className="page-head">
        <h1>Stats</h1>
        <span className="muted numeric">
          {stats.entries} entries · {stats.units} things · <Link to="/gifts">Gifts</Link>
        </span>
      </div>

      <div className="stat-heroes">
        <div>
          <span className="eyebrow">Replacement value</span>
          <p className="stat-hero numeric">{formatPrice(stats.totals[HOME] ?? 0, HOME)}</p>
          <p className="muted">
            At least this. It adds up what you paid, so second-hand things count at second-hand
            prices and {stats.unpriced} entries with no price count as nothing.
            {abroad && ` Paid abroad and not included: ${abroad}.`}
          </p>
        </div>
        <div>
          <span className="eyebrow">Bought second-hand</span>
          <p className="stat-hero numeric">{formatPrice(secondHand, HOME)}</p>
          <p className="muted">{stats.second_hand_entries} entries.</p>
        </div>
      </div>

      <div className="stat-grid">
        <Ranking title="By shop" rows={stats.by_shop} />
        <Ranking title="By category" rows={stats.by_category} />
        <Ranking title="By room" rows={stats.by_room} />
        <Ranking title="By year" rows={stats.by_year} />
      </div>

      <section className="stat-section">
        <h2>Most expensive</h2>
        <ul className="stat-top">
          {stats.most_expensive.map((item) => (
            <li key={item.id}>
              <Link to={`/items/${item.id}`}>{[item.brand, item.name].filter(Boolean).join(' ')}</Link>
              <span className="numeric">{formatPrice(item.minor, item.currency)}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
