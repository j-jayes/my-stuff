import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { type ItemDetail as Item, api, formatPrice } from '../api'
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
  if (!item || !values) return <p className="muted"><span className="spinner" /></p>

  const price = formatPrice(item.purchase_price_minor, item.currency)

  return (
    <>
      <p className="muted">
        <Link to="/">← All items</Link>
      </p>

      {item.image_url && <img src={item.image_url} alt={item.name} className="preview" />}

      {editing ? (
        <>
          <h1>Edit</h1>
          {error && <p className="error">{error}</p>}
          <ItemForm
            values={values}
            onChange={setValues}
            suggested={[]}
            onSubmit={save}
            submitLabel="Save changes"
            busy={busy}
          />
          <button style={{ width: '100%', marginTop: 8 }} onClick={() => setEditing(false)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <h1>{item.name}</h1>
          <dl>
            {[
              ['Room', item.room?.name],
              ['Category', item.category?.name],
              ['Brand', item.brand],
              ['Price', price],
              ['Purchased', item.purchase_date],
              ['Serial number', item.serial_number],
              ['Notes', item.descriptor_notes],
            ]
              .filter(([, value]) => value)
              .map(([label, value]) => (
                <div key={label} style={{ marginBottom: 8 }}>
                  <span className="muted">{label}</span>
                  <br />
                  {value}
                </div>
              ))}
          </dl>

          {item.source_url && (
            <p>
              <a className="muted" href={item.source_url} target="_blank" rel="noreferrer">
                Product page ↗
              </a>
            </p>
          )}

          {item.receipt_url && (
            <>
              <h2>Receipt</h2>
              <img src={item.receipt_url} alt="Receipt" className="preview" />
            </>
          )}

          <div className="row" style={{ marginTop: 20 }}>
            <button onClick={() => setEditing(true)}>Edit</button>
            <button className="danger" onClick={remove}>
              Delete
            </button>
          </div>
        </>
      )}
    </>
  )
}
