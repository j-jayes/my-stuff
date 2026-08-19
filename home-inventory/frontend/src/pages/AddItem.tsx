import { type ChangeEvent, type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { CameraIcon } from '../components/Icons'
import ItemForm, { type FormValues, emptyValues, toPayload } from '../components/ItemForm'

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
  const [thinking, setThinking] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function onPhotoChosen(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setImage(file)
    setPreviewUrl(URL.createObjectURL(file))
    setMode('form')
    setThinking(true)
    setNotice(null)
    try {
      const suggestion = await api.extract(file)
      const categories = await api.categories()
      const category = categories.find((c) => c.name === suggestion.category)
      setValues((current) => ({
        ...current,
        name: suggestion.name,
        brand: suggestion.brand ?? '',
        descriptor_notes: suggestion.descriptor_notes ?? '',
        category_id: category?.id ?? '',
      }))
      setSuggested(
        [
          'name',
          suggestion.brand && 'brand',
          suggestion.descriptor_notes && 'descriptor_notes',
          category && 'category',
        ].filter(Boolean) as string[],
      )
    } catch {
      // Suggestion failing is a designed outcome, not an error: the form is still usable.
      setNotice('Could not read the photo automatically — fill it in yourself.')
    } finally {
      setThinking(false)
    }
  }

  async function fetchLink(event: FormEvent) {
    event.preventDefault()
    setThinking(true)
    setNotice(null)
    try {
      const page = await api.scrape(link)
      setSourceUrl(page.source_url)
      setSourceImageUrl(page.image_url)
      setPreviewUrl(page.image_url)
      setValues((current) => ({ ...current, name: page.title ?? '' }))
      setSuggested(page.title ? ['name'] : [])
      if (!page.image_url) setNotice('No product image was found on that page.')
      setMode('form')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not read that page.')
    } finally {
      setThinking(false)
    }
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

        {notice && <p className="error">{notice}</p>}

        <p className="muted" style={{ marginTop: 'var(--s-5)' }}>
          Or{' '}
          <button className="quiet" onClick={() => setMode('form')}>
            add it by hand
          </button>{' '}
          with no photo.
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
                suggested.filter(
                  (field) =>
                    !touched.includes(field as keyof FormValues) &&
                    !(field === 'category' && touched.includes('category_id')),
                ),
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
