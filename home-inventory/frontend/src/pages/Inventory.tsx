import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { type ItemSummary, type TaxonomyEntry, api } from '../api'

export default function Inventory() {
  const [items, setItems] = useState<ItemSummary[]>([])
  const [total, setTotal] = useState(0)
  const [rooms, setRooms] = useState<TaxonomyEntry[]>([])
  const [categories, setCategories] = useState<TaxonomyEntry[]>([])
  const [q, setQ] = useState('')
  const [roomId, setRoomId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.rooms().then(setRooms).catch(() => {})
    api.categories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    // Debounced so typing in the search box does not fire a request per keystroke.
    const timer = setTimeout(() => {
      setLoading(true)
      api
        .items({ q, room_id: roomId, category_id: categoryId, limit: 200 })
        .then((page) => {
          setItems(page.items)
          setTotal(page.total)
        })
        .finally(() => setLoading(false))
    }, 200)
    return () => clearTimeout(timer)
  }, [q, roomId, categoryId])

  const toggle = (current: string, value: string) => (current === value ? '' : value)

  return (
    <>
      <h1>My Stuff</h1>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search by name, brand, or notes"
      />

      <div className="chips">
        {rooms.map((room) => (
          <button
            key={room.id}
            className={`chip ${roomId === room.id ? 'on' : ''}`}
            onClick={() => setRoomId((current) => toggle(current, room.id))}
          >
            {room.name} {room.item_count > 0 && <span className="muted">{room.item_count}</span>}
          </button>
        ))}
      </div>
      <div className="chips">
        {categories.map((category) => (
          <button
            key={category.id}
            className={`chip ${categoryId === category.id ? 'on' : ''}`}
            onClick={() => setCategoryId((current) => toggle(current, category.id))}
          >
            {category.name}
          </button>
        ))}
      </div>

      <p className="muted">
        {loading ? <span className="spinner" /> : `${total} item${total === 1 ? '' : 's'}`}
      </p>

      {!loading && items.length === 0 && (
        <div className="capture">
          <p style={{ margin: 0 }}>Nothing here yet.</p>
          <Link className="button primary" to="/add">
            Add the first thing
          </Link>
        </div>
      )}

      <div className="item-list">
        {items.map((item) => (
          <Link className="item-row" key={item.id} to={`/items/${item.id}`}>
            {item.thumb_url ? (
              <img src={item.thumb_url} alt="" loading="lazy" />
            ) : (
              <span className="placeholder">📦</span>
            )}
            <span>
              <strong>{item.name}</strong>
              <br />
              <span className="muted">
                {[item.brand, item.room?.name, item.category?.name].filter(Boolean).join(' · ') ||
                  'No details yet'}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </>
  )
}
