import { type PointerEvent, type ReactNode, useState } from 'react'
import { Link } from 'react-router-dom'

import { type StatItem, formatPrice } from '../api'

export const HOME = 'SEK'

export type Measure = 'money' | 'count'

export type Group = {
  label: string
  items: StatItem[]
  kronor: number
  foreign: Record<string, number>
  units: number
}

export function groupItems(items: StatItem[], key: (item: StatItem) => string): Group[] {
  const groups = new Map<string, Group>()
  for (const item of items) {
    const label = key(item)
    const group = groups.get(label) ?? { label, items: [], kronor: 0, foreign: {}, units: 0 }
    group.items.push(item)
    group.units += item.quantity
    if (item.minor !== null && item.currency === HOME) group.kronor += item.minor
    else if (item.minor !== null && item.currency) {
      group.foreign[item.currency] = (group.foreign[item.currency] ?? 0) + item.minor
    }
    groups.set(label, group)
  }
  return [...groups.values()]
}

export const valueOf = (group: Group, measure: Measure) =>
  measure === 'money' ? group.kronor : group.units

export function foreignText(foreign: Record<string, number>): string {
  return Object.entries(foreign)
    .map(([currency, minor]) => formatPrice(minor, currency))
    .join(' · ')
}

const compactNumber = new Intl.NumberFormat(undefined, {
  notation: 'compact',
  maximumFractionDigits: 1,
})

export function shortValue(value: number, measure: Measure): string {
  return measure === 'money' ? compactNumber.format(value / 100) : String(value)
}

export function fullValue(value: number, measure: Measure): string {
  if (measure === 'money') return formatPrice(value, HOME) ?? ''
  return `${value} ${value === 1 ? 'thing' : 'things'}`
}

/** Five shades, spaced by square root so one huge shop does not wash every other cell out. */
const shade = (value: number, largest: number) =>
  value <= 0 ? 0 : Math.min(5, Math.max(1, Math.ceil(Math.sqrt(value / largest) * 5)))

/** One tooltip for the whole page: anything with a data-tip attribute gets it. */
export function TipLayer({ children }: { children: ReactNode }) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)

  function track(event: PointerEvent) {
    const text = (event.target as Element).closest('[data-tip]')?.getAttribute('data-tip')
    setTip(text ? { x: event.clientX, y: event.clientY, text } : null)
  }

  return (
    <div onPointerMove={track} onPointerLeave={() => setTip(null)}>
      {children}
      {tip && (
        <div
          className="viz-tip"
          role="status"
          style={{
            left: Math.max(8, Math.min(tip.x + 14, window.innerWidth - 268)),
            top: Math.max(8, tip.y - 12),
          }}
        >
          {tip.text}
        </div>
      )}
    </div>
  )
}

type Rect = { x: number; y: number; w: number; h: number }

/** Lays values (largest first) into a W by H box, keeping each rectangle as square as it can. */
export function squarify(values: number[], W: number, H: number): Rect[] {
  const total = values.reduce((sum, value) => sum + value, 0)
  const areas = values.map((value) => (value / total) * W * H)
  const worst = (row: number[], side: number) => {
    const sum = row.reduce((a, b) => a + b, 0)
    return Math.max(
      (side * side * Math.max(...row)) / (sum * sum),
      (sum * sum) / (side * side * Math.min(...row)),
    )
  }

  const rects: Rect[] = []
  let [x, y, w, h, next] = [0, 0, W, H, 0]
  while (next < areas.length) {
    const side = Math.min(w, h)
    const row = [areas[next]]
    let end = next + 1
    while (end < areas.length && worst([...row, areas[end]], side) <= worst(row, side)) {
      row.push(areas[end])
      end += 1
    }
    const depth = row.reduce((a, b) => a + b, 0) / side
    let along = 0
    for (const area of row) {
      const length = area / depth
      rects.push(
        w >= h ? { x, y: y + along, w: depth, h: length } : { x: x + along, y, w: length, h: depth },
      )
      along += length
    }
    if (w >= h) {
      x += depth
      w -= depth
    } else {
      y += depth
      h -= depth
    }
    next = end
  }
  return rects
}

const TREEMAP_CELLS = 24

export function Treemap({
  groups,
  measure,
  selected,
  onSelect,
  wide,
}: {
  groups: Group[]
  measure: Measure
  selected: string | null
  onSelect: (label: string) => void
  wide: boolean
}) {
  const ranked = groups
    .filter((group) => valueOf(group, measure) > 0)
    .sort((a, b) => valueOf(b, measure) - valueOf(a, measure))
  const shown = ranked.slice(0, TREEMAP_CELLS)
  const rest = ranked.slice(TREEMAP_CELLS)
  const restValue = rest.reduce((sum, group) => sum + valueOf(group, measure), 0)
  const cells = [
    ...shown.map((group) => ({ label: group.label, value: valueOf(group, measure), other: false })),
    ...(restValue > 0 ? [{ label: `${rest.length} more`, value: restValue, other: true }] : []),
  ].sort((a, b) => b.value - a.value)
  if (cells.length === 0) return <p className="muted">Nothing to show here.</p>

  const [W, H] = wide ? [100, 50] : [100, 125]
  const rects = squarify(
    cells.map((cell) => cell.value),
    W,
    H,
  )
  const largest = cells[0].value
  const total = cells.reduce((sum, cell) => sum + cell.value, 0)

  return (
    <div className="treemap" style={{ aspectRatio: `${W} / ${H}` }}>
      {cells.map((cell, index) => {
        const r = rects[index]
        const share = Math.round((cell.value / total) * 100)
        const roomy = r.w > 9 && r.h > (wide ? 7 : 5)
        return (
          <button
            key={cell.label}
            type="button"
            className={`treemap-cell seq-${cell.other ? 0 : shade(cell.value, largest)}`}
            aria-pressed={selected === cell.label}
            disabled={cell.other}
            data-tip={`${cell.label}\n${fullValue(cell.value, measure)} (${share}%)`}
            aria-label={`${cell.label}, ${fullValue(cell.value, measure)}`}
            style={{
              left: `${(r.x / W) * 100}%`,
              top: `${(r.y / H) * 100}%`,
              width: `${(r.w / W) * 100}%`,
              height: `${(r.h / H) * 100}%`,
            }}
            onClick={() => onSelect(cell.label)}
          >
            {roomy && (
              <>
                <span className="treemap-name">{cell.label}</span>
                <span className="treemap-value numeric">{shortValue(cell.value, measure)}</span>
              </>
            )}
          </button>
        )
      })}
    </div>
  )
}

const HEAT_SHOPS = 14
const roomOf = (item: StatItem) => item.room ?? 'No room'

export function ShopRoomGrid({ items, measure }: { items: StatItem[]; measure: Measure }) {
  const amount = (item: StatItem) =>
    measure === 'count' ? item.quantity : item.currency === HOME ? (item.minor ?? 0) : 0

  const sum = (list: StatItem[]) => list.reduce((total, item) => total + amount(item), 0)
  const rooms = groupItems(items, roomOf)
    .map((room) => ({ label: room.label, value: sum(room.items) }))
    .filter((room) => room.value > 0)
    // "No room" is a gap in the records rather than a place, so it goes last whatever its size.
    .sort((a, b) => Number(a.label === 'No room') - Number(b.label === 'No room') || b.value - a.value)

  const shops = groupItems(items, (item) => item.shop)
    .map((shop) => ({ label: shop.label, items: shop.items, value: sum(shop.items) }))
    .filter((shop) => shop.value > 0)
    .sort((a, b) => b.value - a.value)
  const known = shops.filter((shop) => shop.label !== 'Not recorded')
  const rest = known.slice(HEAT_SHOPS)
  const rows = [
    ...known.slice(0, HEAT_SHOPS),
    ...(rest.length
      ? [{ label: `${rest.length} other shops`, items: rest.flatMap((s) => s.items), value: 0 }]
      : []),
    ...shops.filter((shop) => shop.label === 'Not recorded'),
  ].map((row) => ({ ...row, value: sum(row.items) }))

  const cell = (row: (typeof rows)[number], room: string) =>
    sum(row.items.filter((item) => roomOf(item) === room))
  const largest = Math.max(1, ...rows.flatMap((row) => rooms.map((room) => cell(row, room.label))))

  return (
    <div className="heat-scroll" tabIndex={0} role="group" aria-label="Shops against rooms">
      <table className="heat">
        <thead>
          <tr>
            <th scope="col" className="heat-corner">
              <span className="sr-only">Shop</span>
            </th>
            {rooms.map((room) => (
              <th scope="col" key={room.label}>
                {room.label}
              </th>
            ))}
            <th scope="col">All</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              {rooms.map((room) => {
                const value = cell(row, room.label)
                return (
                  <td
                    key={room.label}
                    className={`numeric seq-${shade(value, largest)}`}
                    data-tip={value ? `${row.label} in ${room.label}\n${fullValue(value, measure)}` : undefined}
                  >
                    {value ? shortValue(value, measure) : ''}
                  </td>
                )
              })}
              <td className="numeric heat-total">{shortValue(row.value, measure)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">All</th>
            {rooms.map((room) => (
              <td className="numeric heat-total" key={room.label}>
                {shortValue(room.value, measure)}
              </td>
            ))}
            <td className="numeric heat-total">
              {shortValue(
                rooms.reduce((total, room) => total + room.value, 0),
                measure,
              )}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

export function YearColumns({ items, measure }: { items: StatItem[]; measure: Measure }) {
  const groups = groupItems(
    items.filter((item) => item.date),
    (item) => item.date!.slice(0, 4),
  )
  const byYear = new Map(groups.map((group) => [Number(group.label), valueOf(group, measure)]))
  const years = [...byYear.keys()]
  if (years.length === 0) return <p className="muted">No dated purchases yet.</p>
  const first = Math.min(...years)
  const last = Math.max(...years)
  // Years with nothing still get a slot, or a gap in the buying would be invisible.
  const span = Array.from({ length: last - first + 1 }, (_, i) => first + i)
  const largest = Math.max(1, ...byYear.values())

  return (
    <div className="columns" role="img" aria-label="Purchases per year">
      {span.map((year) => {
        const value = byYear.get(year) ?? 0
        return (
          <div
            className="column"
            key={year}
            data-tip={`${year}\n${fullValue(value, measure)}`}
          >
            <span className="column-value numeric">{value ? shortValue(value, measure) : ''}</span>
            <span className="column-bar" style={{ height: `${(value / largest) * 100}%` }} />
            <span className="column-year numeric">{String(year).slice(2)}</span>
          </div>
        )
      })}
    </div>
  )
}

const MS_IN_YEAR = 365.25 * 24 * 3600 * 1000

export function EveryPurchase({ items }: { items: StatItem[] }) {
  const dots = items.filter(
    // Under a krona is a bundled freebie rather than a price, and would stretch the whole axis.
    (item) => item.date && item.currency === HOME && item.minor !== null && item.minor >= 100,
  )
  if (dots.length === 0) return <p className="muted">No dated purchases in kronor yet.</p>

  const times = dots.map((item) => Date.parse(item.date!))
  const startYear = new Date(Math.min(...times)).getFullYear()
  const endYear = new Date(Math.max(...times)).getFullYear() + 1
  const start = Date.UTC(startYear, 0, 1)
  const span = (endYear - startYear) * MS_IN_YEAR
  const logs = dots.map((item) => Math.log10(item.minor! / 100))
  const bottom = Math.floor(Math.min(...logs))
  const top = Math.ceil(Math.max(...logs))
  const decades = Array.from({ length: top - bottom + 1 }, (_, i) => bottom + i)
  const yearTicks = Array.from({ length: endYear - startYear }, (_, i) => startYear + i)

  return (
    <>
      <div className="legend">
        <span>
          <i className="dot-key new" /> Bought new
        </span>
        <span>
          <i className="dot-key used" /> Second-hand
        </span>
      </div>
      <div className="scatter">
        <div className="scatter-plot">
          {decades.map((decade) => (
            <div
              className="scatter-line"
              key={decade}
              style={{ bottom: `${((decade - bottom) / (top - bottom)) * 100}%` }}
            >
              <span className="numeric">{compactNumber.format(10 ** decade)} kr</span>
            </div>
          ))}
          {dots.map((item, index) => (
            <Link
              key={item.id}
              to={`/items/${item.id}`}
              className={`scatter-dot ${item.second_hand ? 'used' : 'new'}`}
              aria-label={[item.brand, item.name].filter(Boolean).join(' ')}
              data-tip={`${[item.brand, item.name].filter(Boolean).join(' ')}\n${formatPrice(item.minor, item.currency)} · ${item.date} · ${item.shop}`}
              style={{
                left: `${((times[index] - start) / span) * 100}%`,
                bottom: `${((logs[index] - bottom) / (top - bottom)) * 100}%`,
              }}
            />
          ))}
        </div>
        <div className="scatter-years numeric">
          {yearTicks.map((year) => (
            <span key={year}>{year}</span>
          ))}
        </div>
      </div>
    </>
  )
}
