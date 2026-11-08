import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { type ItemDetail as Item, api, formatPrice, lineTotal } from '../api'
import { BackIcon } from '../components/Icons'
import ItemForm, { type FormValues, toPayload, valuesFromItem } from '../components/ItemForm'
import PriceToggle from '../components/PriceToggle'
import { usePricesVisible } from '../prices'

export default function ItemDetail() {
  const showPrices = usePricesVisible()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [item, setItem] = useState<Item | null>(null)
  const [values, setValues] = useState<FormValues | null>(null)
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)

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

  async function makeProductPhoto() {
    if (!id) return
    setGenerating(true)
    setError(null)
    try {
      setPreview((await api.makeProductPhoto(id)).preview_url)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not make a photo of that.')
    } finally {
      setGenerating(false)
    }
  }

  async function acceptProductPhoto() {
    if (!id) return
    setBusy(true)
    setError(null)
    try {
      const updated = await api.acceptProductPhoto(id)
      setItem(updated)
      setValues(valuesFromItem(updated))
      setPreview(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not use that photo.')
    } finally {
      setBusy(false)
    }
  }

  async function giveAway() {
    if (!id) return
    const to = prompt('Who was it for? You can leave this blank.')
    if (to === null) return
    try {
      await api.giftItem(id, to)
      navigate('/gifts', { replace: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not mark that as a gift.')
    }
  }

  async function bringBack() {
    if (!id) return
    try {
      const updated = await api.takeGiftBack(id)
      setItem(updated)
      setValues(valuesFromItem(updated))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not bring that back.')
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
    ['How many', item.quantity > 1 ? String(item.quantity) : null],
    ['Purchased', item.purchase_date],
    ['Second hand', item.second_hand ? 'Yes' : null],
    ['Serial number', item.serial_number],
  ]
  // With more than one, the headline figure is what the set is worth and the unit price is
  // spelled out underneath; with one they are the same number and only one is shown.
  const price = formatPrice(lineTotal(item), item.currency)
  const each =
    item.quantity > 1 ? formatPrice(item.purchase_price_minor, item.currency) : null
  const numeric = new Set(['Purchased', 'Serial number', 'How many'])

  return (
    <>
      <Link className="back-link" to="/">
        <BackIcon /> All items
      </Link>

      <div className="detail">
        <div className="detail-media stack">
          {item.image_url && <img src={item.image_url} alt={item.name} />}

          {item.image_url && !editing && (
            <div>
              {preview ? (
                <>
                  <h2 className="section-head">Product photo</h2>
                  <img src={preview} alt={`Generated product photo of ${item.name}`} />
                  <div className="row" style={{ marginTop: 'var(--s-3)' }}>
                    <button className="primary" onClick={acceptProductPhoto} disabled={busy}>
                      {busy ? <span className="spinner" /> : 'Use this photo'}
                    </button>
                    <button onClick={() => setPreview(null)} disabled={busy}>
                      Discard
                    </button>
                  </div>
                </>
              ) : (
                <button className="full" onClick={makeProductPhoto} disabled={generating}>
                  {generating ? <span className="spinner" /> : 'Make product photo'}
                </button>
              )}
            </div>
          )}

          {item.source_photo_url && (
            <p className="muted">
              <a href={item.source_photo_url} target="_blank" rel="noreferrer">
                The photograph this was made from ↗
              </a>
            </p>
          )}

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
              {item.gifted_at && (
                <p className="muted" style={{ marginTop: 'var(--s-2)' }}>
                  {item.gifted_to ? `Given to ${item.gifted_to}` : 'Given away'}, and kept here as a
                  record.
                </p>
              )}
              {price && (
                <div className="price-line">
                  <PriceToggle />
                  {showPrices && (
                    <p className="numeric">
                      {price}
                      {each && <span className="muted"> ({each} each)</span>}
                    </p>
                  )}
                </div>
              )}

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
                {item.gifted_at ? (
                  <button onClick={bringBack}>Bring back</button>
                ) : (
                  <button onClick={giveAway}>Mark as gift</button>
                )}
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
