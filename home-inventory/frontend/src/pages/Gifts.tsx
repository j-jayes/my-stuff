import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { type ItemSummary, api } from '../api'
import { BoxIcon } from '../components/Icons'

export default function Gifts() {
  const [items, setItems] = useState<ItemSummary[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    api
      .allItems({ gifted: true })
      .then((page) => setItems(page.items))
      .catch(() => setFailed(true))
  }, [])

  if (failed) return <p className="muted">The gifts could not be loaded. Try reloading the page.</p>

  if (!items) {
    return (
      <div className="centred">
        <span className="spinner" />
      </div>
    )
  }

  return (
    <>
      <div className="page-head">
        <h1>Gifts</h1>
        <span className="muted numeric">
          {items.length} given away
        </span>
      </div>

      {items.length === 0 ? (
        <p className="muted">Mark something as a gift from its page and it will move here.</p>
      ) : (
        <div className="item-grid">
          {items.map((item) => (
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
              <span className="tile-name">{item.name}</span>
              <span className="tile-meta">
                {item.gifted_to ? `For ${item.gifted_to}` : 'Given away'}
              </span>
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
