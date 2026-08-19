import { type ChangeEvent, type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { CameraIcon } from '../components/Icons'
import ItemForm, {
  FIELD_FOR_SUGGESTION,
  type FormValues,
  emptyValues,
  toPayload,
} from '../components/ItemForm'

type Mode = 'choose' | 'form'

export default function AddItem() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('choose')
  const [values, setValues] = useState<FormValues>(emptyValues)
  const [suggested, setSuggested] = useState<string[]>([])
  const [image, setImage] = useState<Blob | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [sourceImageUrl, setSourceImageUrl] = useState<string | null>(null)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<Blob | null>(null)
  const [link, setLink] = useState('')
  const [note, setNote] = useState('')
  const [thinking, setThinking] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  /** One call for every way in. The note travels with the photo and the link alike, because
   *  "bought from IKEA in June 2025, in the lounge" is worth more than either on its own. */
  async function ask(input: { image?: Blob | null; url?: string }) {
    setThinking(true)
    setNotice(null)
    try {
      const suggestion = await api.suggest({ ...input, note: note.trim() || undefined })
      if (suggestion.source_url) setSourceUrl(suggestion.source_url)
      if (suggestion.image_url) {
        setSourceImageUrl(suggestion.image_url)
        if (!input.image) setPreviewUrl(suggestion.image_url)
      }
      setValues((current) => ({
        ...current,
        name: suggestion.name || current.name,
        brand: suggestion.brand ?? current.brand,
        descriptor_notes: suggestion.descriptor_notes ?? current.descriptor_notes,
        category_id: suggestion.category_id ?? current.category_id,
        room_id: suggestion.room_id ?? current.room_id,
        purchase_date: suggestion.purchase_date ?? current.purchase_date,
        quantity: String(suggestion.quantity),
        price:
          suggestion.purchase_price_minor === null
            ? current.price
            : String(suggestion.purchase_price_minor / 100),
        currency: suggestion.currency ?? current.currency,
      }))
      setSuggested(suggestion.suggested_fields)
      if (input.url && !suggestion.image_url) setNotice('No product image was found on that page.')
      setMode('form')
    } catch (error) {
      // Failing here is a designed outcome, not an error: the form is still usable.
      setNotice(
        error instanceof Error ? error.message : 'Could not work that out — fill it in yourself.',
      )
      setMode('form')
    } finally {
      setThinking(false)
    }
  }

  async function onPhotoChosen(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setImage(file)
    setPreviewUrl(URL.createObjectURL(file))
    setMode('form')
    await ask({ image: file })
  }

  async function fetchLink(event: FormEvent) {
    event.preventDefault()
    await ask({ url: link })
  }

  async function fromNoteAlone(event: FormEvent) {
    event.preventDefault()
    await ask({})
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setNotice(null)
    try {
      const payload = toPayload(values, suggested)
      if (sourceUrl) payload.source_url = sourceUrl
      if (!image && sourceImageUrl) payload.source_image_url = sourceImageUrl
      const item = await api.createItem(payload, image, receipt)
      navigate(`/items/${item.id}`, { replace: true })
    } catch (error) {
      // Everything typed is still on screen, so the owner can just press save again.
      setNotice(error instanceof Error ? error.message : 'Could not save that.')
      setSaving(false)
    }
  }

  if (mode === 'choose') {
    return (
      <>
        <h1>Add something</h1>

        <div className="capture" style={{ marginTop: 'var(--s-5)' }}>
          <span className="capture-mark">
            <CameraIcon size={32} />
          </span>
          <label className="button primary">
            Take a photo
            {/* accept="image/*" without image/heic is what makes iOS Safari hand over JPEG.
                Adding heic here would flip it to HEIC — see research.md D5. */}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              onChange={onPhotoChosen}
              hidden
            />
          </label>
          <label className="button">
            Choose from library
            <input type="file" accept="image/*" onChange={onPhotoChosen} hidden />
          </label>
        </div>

        <h2 className="section-head">Or paste a product link</h2>
        <form onSubmit={fetchLink} className="row">
          <input
            type="url"
            value={link}
            onChange={(event) => setLink(event.target.value)}
            placeholder="https://…"
            inputMode="url"
            aria-label="Product page address"
          />
          <button className="shrink" disabled={!link || thinking}>
            {thinking ? <span className="spinner" /> : 'Fetch'}
          </button>
        </form>

        <h2 className="section-head">Anything you already know</h2>
        <form onSubmit={fromNoteAlone}>
          <label>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              placeholder="Ikea Tertial lamp, white, bought from Ikea June 2025, smart bulb fitted, in the lounge"
              aria-label="What you know about it"
            />
          </label>
          <p className="muted">
            Sent along with the photo or the link, whichever you use — or on its own.
          </p>
          <button className="shrink" disabled={!note.trim() || thinking}>
            {thinking ? <span className="spinner" /> : 'Sort it out'}
          </button>
        </form>

        {notice && <p className="error">{notice}</p>}

        <p className="muted" style={{ marginTop: 'var(--s-5)' }}>
          Or{' '}
          <button className="quiet" onClick={() => setMode('form')}>
            add it by hand
          </button>{' '}
          with nothing filled in.
        </p>
      </>
    )
  }

  return (
    <>
      <h1>New item</h1>

      <div className="compose" style={{ marginTop: 'var(--s-5)' }}>
        <div className="stack">
          {previewUrl && <img src={previewUrl} alt="" className="preview" />}
          <label>
            <span>Receipt or invoice photo (optional)</span>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setReceipt(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        <div>
          {thinking && (
            <p className="thinking">
              <span className="spinner" /> Working out what this is…
            </p>
          )}
          {notice && <p className="error">{notice}</p>}

          <ItemForm
            values={values}
            onChange={(next) => {
              // Once the owner edits a field it stops being a suggestion.
              const touched = (Object.keys(next) as (keyof FormValues)[]).filter(
                (key) => next[key] !== values[key],
              )
              setSuggested(
                suggested.filter((field) => {
                  const backing = FIELD_FOR_SUGGESTION[field] ?? (field as keyof FormValues)
                  return !touched.includes(backing)
                }),
              )
              setValues(next)
            }}
            suggested={suggested}
            onSubmit={save}
            submitLabel="Save item"
            busy={saving}
          />
        </div>
      </div>
    </>
  )
}
