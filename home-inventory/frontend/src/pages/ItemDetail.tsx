import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { type ItemDetail as Item, api, formatPrice } from '../api'
import { BackIcon } from '../components/Icons'
import ItemForm, { type FormValues, toPayload, valuesFromItem } from '../components/ItemForm'

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [item, setItem] = useState<Item | null>(null)
  const [values, setValues] = useState<FormValues | null>(null)
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api
      .item(id)
      .then((loaded) => {
        setItem(loaded)
        setValues(valuesFromItem(loaded))
      })
      .catch(() => setError('That item could not be found.'))
  }, [id])

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!id || !values) return
    setBusy(true)
    setError(null)
    try {
      const updated = await api.updateItem(id, toPayload(values, item?.ai_suggested_fields ?? []))
      setItem(updated)
      setValues(valuesFromItem(updated))
      setEditing(false)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save that.')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!id || !confirm('Delete this item for good?')) return
    await api.deleteItem(id)
    navigate('/', { replace: true })
  }

  if (error && !item) return <p className="error">{error}</p>
  if (!item || !values) {
    return (
      <div className="centred">
        <span className="spinner" />
      </div>
    )
  }

  const specs: [string, string | null][] = [
    ['Room', item.room?.name ?? null],
    ['Category', item.category?.name ?? null],
    ['Brand', item.brand],
    ['Purchased', item.purchase_date],
    ['Serial number', item.serial_number],
  ]
  const price = formatPrice(item.purchase_price_minor, item.currency)
  const numeric = new Set(['Purchased', 'Serial number'])

  return (
    <>
      <Link className="back-link" to="/">
        <BackIcon /> All items
      </Link>

      <div className="detail">
        <div className="detail-media stack">
          {item.image_url && <img src={item.image_url} alt={item.name} />}
          {item.receipt_url && (
            <div>
              <h2 className="section-head">Receipt</h2>
              <img src={item.receipt_url} alt="Receipt for this item" />
            </div>
          )}
        </div>

        <div>
          {editing ? (
            <>
              <h1>Edit</h1>
              {error && <p className="error">{error}</p>}
              <div style={{ marginTop: 'var(--s-5)' }}>
                <ItemForm
                  values={values}
                  onChange={setValues}
                  suggested={[]}
                  onSubmit={save}
                  submitLabel="Save changes"
                  busy={busy}
                />
              </div>
              <button className="full" style={{ marginTop: 'var(--s-2)' }} onClick={() => setEditing(false)}>
                Cancel
              </button>
            </>
          ) : (
            <>
              <h1>{item.name}</h1>
              {price && <p className="numeric" style={{ marginTop: 'var(--s-2)' }}>{price}</p>}

              {item.descriptor_notes && (
                <p className="muted" style={{ marginTop: 'var(--s-4)' }}>
                  {item.descriptor_notes}
                </p>
              )}

              <dl className="spec">
                {specs
                  .filter(([, value]) => value)
                  .map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd className={numeric.has(label) ? 'numeric' : undefined}>{value}</dd>
                    </div>
                  ))}
              </dl>

              {item.source_url && (
                <p style={{ marginTop: 'var(--s-4)' }}>
                  <a className="muted" href={item.source_url} target="_blank" rel="noreferrer">
                    Product page ↗
                  </a>
                </p>
              )}

              <div className="actions" style={{ marginTop: 'var(--s-6)' }}>
                <button onClick={() => setEditing(true)}>Edit</button>
                <button className="danger" onClick={remove}>
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
