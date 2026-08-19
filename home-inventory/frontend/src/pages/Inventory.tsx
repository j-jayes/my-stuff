import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { type ItemSummary, type TaxonomyEntry, api, formatPrice, lineTotal } from '../api'
import { BoxIcon } from '../components/Icons'

export default function Inventory() {
  const [params, setParams] = useSearchParams()
  const [items, setItems] = useState<ItemSummary[]>([])
  const [total, setTotal] = useState(0)
  const [rooms, setRooms] = useState<TaxonomyEntry[]>([])
  const [categories, setCategories] = useState<TaxonomyEntry[]>([])
  const [loading, setLoading] = useState(true)

  const roomId = params.get('room') ?? ''
  const categoryId = params.get('category') ?? ''
  const query = params.get('q') ?? ''

  // The text box keeps its own state so typing stays instant, then syncs to the URL on the
  // debounce. Writing every keystroke straight to the URL would flood browser history, which is
  // why the sync below replaces rather than pushes.
  const [text, setText] = useState(query)

  useEffect(() => {
    setText(query)
  }, [query])

  useEffect(() => {
    if (text === query) return
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params)
      if (text) next.set('q', text)
      else next.delete('q')
      setParams(next, { replace: true })
    }, 250)
    return () => clearTimeout(timer)
  }, [text, query, params, setParams])

  useEffect(() => {
    api.rooms().then(setRooms).catch(() => {})
    api.categories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    api
      .items({ q: query, room_id: roomId, category_id: categoryId, limit: 200 })
      .then((page) => {
        setItems(page.items)
        setTotal(page.total)
      })
      .finally(() => setLoading(false))
  }, [query, roomId, categoryId])

  const toggleFilter = (key: 'room' | 'category', id: string) => {
    const next = new URLSearchParams(params)
    if (next.get(key) === id) next.delete(key)
    else next.set(key, id)
    setParams(next)
  }

  const filtered = Boolean(roomId || categoryId || query)
  // Which branch of the category tree to expose a second chip row for: the selected category
  // if it has shelves, otherwise the parent of the selected shelf.
  const selected = categories.find((c) => c.id === categoryId)
  const openParent = selected?.parent_id ?? (selected && !selected.parent_id ? selected.id : null)
  const shelves = categories.filter((c) => c.parent_id && c.parent_id === openParent)

  // Name the view after whatever is filtering it, so the heading confirms what the sidebar or
  // chips just did rather than repeating the brand.
  const heading =
    rooms.find((r) => r.id === roomId)?.name ??
    categories.find((c) => c.id === categoryId)?.name ??
    'My Stuff'

  return (
    <>
      <div className="page-head">
        <h1>{heading}</h1>
        <span className="muted numeric">{loading ? '' : `${total} item${total === 1 ? '' : 's'}`}</span>
      </div>

      <input
        type="search"
        className="search-wide"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Search by name, brand, or notes"
        aria-label="Search items"
      />

      {/* Chip rows are the phone and tablet equivalent of the desktop sidebar filters. */}
      <div className="chips" style={{ marginTop: 'var(--s-3)' }}>
        {rooms.map((room) => (
          <button
            key={room.id}
            className={`chip ${roomId === room.id ? 'on' : ''}`}
            onClick={() => toggleFilter('room', room.id)}
          >
            {room.name}
            {room.item_count > 0 && <span className="count numeric">{room.item_count}</span>}
          </button>
        ))}
      </div>
      <div className="chips">
        {categories
          .filter((category) => !category.parent_id)
          .map((category) => (
            <button
              key={category.id}
              className={`chip ${categoryId === category.id || openParent === category.id ? 'on' : ''}`}
              onClick={() => toggleFilter('category', category.id)}
            >
              {category.name}
            </button>
          ))}
      </div>
      {shelves.length > 0 && (
        <div className="chips chips-nested">
          {shelves.map((shelf) => (
            <button
              key={shelf.id}
              className={`chip ${categoryId === shelf.id ? 'on' : ''}`}
              onClick={() => toggleFilter('category', shelf.id)}
            >
              {shelf.name}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="centred">
          <span className="spinner" />
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className="capture" style={{ marginTop: 'var(--s-5)' }}>
          <p>{filtered ? 'Nothing matches that.' : 'Nothing here yet.'}</p>
          {filtered ? (
            <Link className="button" to="/">
              Clear filters
            </Link>
          ) : (
            <Link className="button primary" to="/add">
              Add the first thing
            </Link>
          )}
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="item-grid">
          {items.map((item) => {
            const price = formatPrice(lineTotal(item), item.currency)
            return (
              <Link className="tile" key={item.id} to={`/items/${item.id}`}>
                <div className="tile-frame">
                  {item.thumb_url ? (
                    <img src={item.thumb_url} alt="" loading="lazy" />
                  ) : (
                    <span className="tile-empty">
                      <BoxIcon size={32} />
                    </span>
                  )}
                </div>
                <span className="tile-name">
                  {item.name}
                  {item.quantity > 1 && <span className="tile-count"> x{item.quantity}</span>}
                </span>
                <span className="tile-meta">
                  {[item.brand, item.room?.name].filter(Boolean).join(' · ') || '—'}
                </span>
                {price && <span className="tile-meta tile-price numeric">{price}</span>}
              </Link>
            )
          })}
        </div>
      )}
    </>
  )
}
