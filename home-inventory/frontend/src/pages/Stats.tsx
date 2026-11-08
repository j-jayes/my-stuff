import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { type StatItem, type Stats as StatsData, api, formatPrice } from '../api'
import {
  EveryPurchase,
  type Group,
  HOME,
  type Measure,
  ShopRoomGrid,
  TipLayer,
  Treemap,
  YearColumns,
  foreignText,
  fullValue,
  groupItems,
  valueOf,
} from '../components/StatCharts'

const DIMENSIONS = {
  Shop: (item: StatItem) => item.shop,
  Room: (item: StatItem) => item.room ?? 'No room',
  Category: (item: StatItem) => item.category ?? 'No category',
  Brand: (item: StatItem) => item.brand ?? 'No brand',
}
type Dimension = keyof typeof DIMENSIONS

/** The bucket for things nobody recorded. It says more about the records than the spending. */
const GAPS = new Set(['Not recorded', 'No room', 'No category', 'No brand'])

const GALLERY = 12

const title = (item: { brand: string | null; name: string }) =>
  [item.brand, item.name].filter(Boolean).join(' ')

function useWide() {
  const [wide, setWide] = useState(() => window.matchMedia('(min-width: 720px)').matches)
  useEffect(() => {
    const query = window.matchMedia('(min-width: 720px)')
    const change = () => setWide(query.matches)
    query.addEventListener('change', change)
    return () => query.removeEventListener('change', change)
  }, [])
  return wide
}

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

function Amount({ group }: { group: Group }) {
  const other = foreignText(group.foreign)
  return (
    <>
      {group.kronor > 0 && formatPrice(group.kronor, HOME)}
      {other && <span className="muted"> {group.kronor > 0 ? `+ ${other}` : other}</span>}
    </>
  )
}

function Thumb({ url }: { url: string | null }) {
  return url ? <img src={url} alt="" loading="lazy" /> : <span className="thumb-empty" />
}

/** The drill-down: pick a shop (or room, or brand) and see exactly what is behind the number. */
function Explorer({
  groups,
  dimension,
  measure,
  selected,
  onSelect,
}: {
  groups: Group[]
  dimension: Dimension
  measure: Measure
  selected: Group | null
  onSelect: (label: string) => void
}) {
  const largest = Math.max(1, ...groups.map((group) => valueOf(group, measure)))
  const sortedItems = selected
    ? [...selected.items].sort((a, b) => (b.minor ?? -1) - (a.minor ?? -1))
    : []
  // Looking at a shop, the useful split is where its things ended up, and the other way round.
  const splitBy = dimension === 'Room' ? DIMENSIONS.Shop : DIMENSIONS.Room
  const split = selected
    ? groupItems(selected.items, splitBy).sort((a, b) => b.units - a.units)
    : []
  const priced = selected?.items.filter((i) => i.currency === HOME && i.minor) ?? []

  return (
    <div className="explorer">
      <ul className="ex-list">
        {groups.map((group) => {
          const value = valueOf(group, measure)
          return (
            <li key={group.label}>
              <button
                type="button"
                aria-pressed={selected?.label === group.label}
                onClick={() => onSelect(group.label)}
              >
                <span className="ex-label">
                  {group.label} <span className="muted numeric">{group.units}</span>
                </span>
                <span className="ex-value numeric">
                  {measure === 'money' ? <Amount group={group} /> : group.units}
                </span>
                <span className="ex-track">
                  <span style={{ width: `${(value / largest) * 100}%` }} />
                </span>
              </button>
            </li>
          )
        })}
      </ul>

      {selected && (
        <div className="ex-detail">
          <h3>{selected.label}</h3>
          <p className="numeric ex-summary">
            <Amount group={selected} />
            <span className="muted">
              {' '}
              · {selected.units} {selected.units === 1 ? 'thing' : 'things'}
              {priced.length > 1 &&
                ` · ${formatPrice(
                  Math.round(selected.kronor / priced.length),
                  HOME,
                )} on average`}
            </span>
          </p>

          <ul className="ex-split">
            {split.map((part) => (
              <li key={part.label} className="numeric">
                {part.label} <span className="muted">{part.units}</span>
              </li>
            ))}
          </ul>

          <div className="ex-best">
            {sortedItems.slice(0, 4).map((item) => (
              <Link key={item.id} to={`/items/${item.id}`} className="ex-card">
                <span className="photo-mat">
                  <Thumb url={item.thumb_url} />
                </span>
                <span className="ex-card-name">{title(item)}</span>
                <span className="numeric">{formatPrice(item.minor, item.currency)}</span>
              </Link>
            ))}
          </div>

          <h4>All {selected.items.length}</h4>
          <ul className="ex-all">
            {sortedItems.map((item) => (
              <li key={item.id}>
                <span className="photo-mat">
                  <Thumb url={item.thumb_url} />
                </span>
                <Link to={`/items/${item.id}`}>{title(item)}</Link>
                <span className="numeric">{formatPrice(item.minor, item.currency) ?? '–'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Completeness({ items }: { items: StatItem[] }) {
  const measures: [string, (item: StatItem) => unknown][] = [
    ['Has a room', (item) => item.room],
    ['Has a category', (item) => item.category],
    ['Has a price', (item) => item.minor !== null],
    ['Has a date', (item) => item.date],
    ['Has a photo', (item) => item.thumb_url],
    ['Shop is known', (item) => item.shop !== 'Not recorded'],
  ]
  return (
    <ul className="meters">
      {measures.map(([label, has]) => {
        const done = items.filter(has).length
        const missing = items.length - done
        return (
          <li key={label}>
            <span>{label}</span>
            <span className="numeric muted">{missing ? `${missing} missing` : 'All done'}</span>
            <span className="meter">
              <span style={{ width: `${(done / Math.max(1, items.length)) * 100}%` }} />
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export default function Stats() {
  const [stats, setStats] = useState<StatsData | null>(null)
  const [failed, setFailed] = useState(false)
  const [dimension, setDimension] = useState<Dimension>('Shop')
  const [measure, setMeasure] = useState<Measure>('money')
  const [picked, setPicked] = useState<string | null>(null)
  const wide = useWide()

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch(() => setFailed(true))
  }, [])

  const items = useMemo(() => stats?.items ?? [], [stats])
  const groups = useMemo(() => {
    const all = groupItems(items, DIMENSIONS[dimension])
    return all.sort(
      (a, b) =>
        valueOf(b, measure) - valueOf(a, measure) ||
        Object.keys(b.foreign).length - Object.keys(a.foreign).length ||
        a.label.localeCompare(b.label),
    )
  }, [items, dimension, measure])

  if (failed) return <p className="muted">The figures could not be loaded. Try reloading the page.</p>

  if (!stats) {
    return (
      <div className="centred">
        <span className="spinner" />
      </div>
    )
  }

  const gap = groups.find((group) => GAPS.has(group.label))
  const selected = groups.find((group) => group.label === picked) ?? groups[0] ?? null
  const abroad = foreignText(
    Object.fromEntries(Object.entries(stats.totals).filter(([currency]) => currency !== HOME)),
  )
  const home = stats.totals[HOME] ?? 0
  const secondHand = stats.second_hand_totals[HOME] ?? 0
  const placed = (key: (item: StatItem) => string, gap: string) =>
    groupItems(items, key)
      .filter((group) => group.label !== gap)
      .sort((a, b) => b.kronor - a.kronor)[0]
  const topShop = placed(DIMENSIONS.Shop, 'Not recorded')
  const topRoom = placed(DIMENSIONS.Room, 'No room')
  const gallery = items
    .filter((item) => item.currency === HOME && item.minor)
    .sort((a, b) => b.minor! - a.minor!)
    .slice(0, GALLERY)
  const giftsLargest = Math.max(1, ...stats.gifts.map((gift) => gift.entries))

  const measureControl = (
    <Segmented
      label="Measure"
      value={measure}
      onChange={setMeasure}
      options={[
        { value: 'money', label: 'Kronor' },
        { value: 'count', label: 'Things' },
      ]}
    />
  )

  return (
    <TipLayer>
      <div className="page-head">
        <h1>Stats</h1>
        <span className="muted numeric">
          {stats.entries} entries · {stats.units} things · <Link to="/gifts">Gifts</Link>
        </span>
      </div>

      <div className="stat-heroes">
        <div>
          <span className="eyebrow">Replacement value</span>
          <p className="stat-hero numeric">{formatPrice(home, HOME)}</p>
          <p className="muted">
            At least this. It adds up what you paid, and {stats.unpriced} entries with no price
            count as nothing.
            {abroad && ` Paid abroad and not included: ${abroad}.`}
          </p>
        </div>
        <div>
          <span className="eyebrow">Bought second-hand</span>
          <p className="stat-hero numeric">{formatPrice(secondHand, HOME)}</p>
          <p className="muted">
            {stats.second_hand_entries} entries, {home ? Math.round((secondHand / home) * 100) : 0}%
            of the value.
          </p>
        </div>
        {topShop && (
          <div>
            <span className="eyebrow">Biggest shop</span>
            <p className="stat-hero">{topShop.label}</p>
            <p className="muted numeric">
              {formatPrice(topShop.kronor, HOME)} · {topShop.units} things
            </p>
          </div>
        )}
        {topRoom && (
          <div>
            <span className="eyebrow">Most valuable room</span>
            <p className="stat-hero">{topRoom.label}</p>
            <p className="muted numeric">
              {formatPrice(topRoom.kronor, HOME)} · {topRoom.units} things
            </p>
          </div>
        )}
      </div>

      <section className="stat-section">
        <div className="viz-head">
          <h2>Where it all is</h2>
          <div className="viz-controls">
            <Segmented
              label="Group by"
              value={dimension}
              onChange={(next) => {
                setDimension(next)
                setPicked(null)
              }}
              options={(Object.keys(DIMENSIONS) as Dimension[]).map((d) => ({ value: d, label: d }))}
            />
            {measureControl}
          </div>
        </div>
        <Treemap
          groups={groups.filter((group) => !GAPS.has(group.label))}
          measure={measure}
          selected={selected?.label ?? null}
          onSelect={setPicked}
          wide={wide}
        />
        <p className="muted viz-note">
          {gap && `${gap.label} is left out of the picture (${fullValue(valueOf(gap, measure), measure)}). `}
          {measure === 'money' &&
            abroad &&
            `Only kronor are drawn. ${abroad} paid in other currencies is in the list below, and counts under Things.`}
        </p>
        <Explorer
          groups={groups}
          dimension={dimension}
          measure={measure}
          selected={selected}
          onSelect={setPicked}
        />
      </section>

      <section className="stat-section">
        <h2>Shops by room</h2>
        <p className="muted viz-note">
          {measure === 'money' ? 'Kronor spent' : 'Number of things'}, stronger colour where there
          is more. Hover a square for the exact figure.
        </p>
        <ShopRoomGrid items={items} measure={measure} />
      </section>

      <section className="stat-section">
        <h2>The most valuable things</h2>
        <ol className="value-gallery">
          {gallery.map((item, index) => (
            <li key={item.id}>
              <Link to={`/items/${item.id}`}>
                <span className="photo-mat">
                  <Thumb url={item.thumb_url} />
                  <span className="value-gallery-rank numeric">{index + 1}</span>
                </span>
                <span className="value-gallery-name">{title(item)}</span>
                <span className="numeric">{formatPrice(item.minor, item.currency)}</span>
                <span className="muted value-gallery-shop">{item.shop}</span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <section className="stat-section">
        <h2>Year by year</h2>
        <p className="muted viz-note">
          {measure === 'money' ? 'Kronor spent' : 'Things bought'} on what you still have. Things
          with no date are left out.
        </p>
        <YearColumns items={items} measure={measure} />
      </section>

      <section className="stat-section">
        <h2>Every purchase</h2>
        <p className="muted viz-note">One dot each, in kronor. Each line up is ten times the price.</p>
        <EveryPurchase items={items} />
      </section>

      <div className="stat-grid">
        <section className="stat-section">
          <h2>Still to fill in</h2>
          <Completeness items={items} />
        </section>
        <section className="stat-section">
          <h2>Gifts given</h2>
          <ul className="meters">
            {stats.gifts.map((gift) => (
              <li key={gift.label}>
                <span>{gift.label}</span>
                <span className="numeric muted">
                  {gift.entries} ·{' '}
                  {Object.entries(gift.spent)
                    .map(([currency, minor]) => formatPrice(minor, currency))
                    .join(' + ')}
                </span>
                <span className="meter">
                  <span style={{ width: `${(gift.entries / giftsLargest) * 100}%` }} />
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </TipLayer>
  )
}
