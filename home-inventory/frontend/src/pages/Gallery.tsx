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

  if (loading) return <p className="muted"><span className="spinner" /></p>

  return (
    <>
      <h1>Gallery</h1>
      {items.length === 0 ? (
        <p className="muted">Photograph a few things and they will show up here.</p>
      ) : (
        <div className="gallery">
          {items.map((item) => (
            <Link key={item.id} to={`/items/${item.id}`}>
              <img src={item.thumb_url!} alt={item.name} loading="lazy" />
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
