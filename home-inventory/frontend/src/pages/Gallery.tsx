import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { type ItemSummary, api } from '../api'

export default function Gallery() {
  const [items, setItems] = useState<ItemSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .items({ limit: 200 })
      .then((page) => setItems(page.items.filter((item) => item.thumb_url)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="centred">
        <span className="spinner" />
      </div>
    )
  }

  return (
    <>
      <div className="page-head">
        <h1>Gallery</h1>
        <span className="muted numeric">
          {items.length} photograph{items.length === 1 ? '' : 's'}
        </span>
      </div>

      {items.length === 0 ? (
        <p className="muted">Photograph a few things and they will show up here.</p>
      ) : (
        <div className="gallery">
          {items.map((item) => (
            <Link key={item.id} to={`/items/${item.id}`} title={item.name}>
              <img src={item.thumb_url!} alt={item.name} loading="lazy" />
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
