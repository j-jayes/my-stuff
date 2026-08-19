import { type FormEvent, useEffect, useState } from 'react'

import { type ItemDetail, type TaxonomyEntry, api } from '../api'

export type FormValues = {
  name: string
  brand: string
  descriptor_notes: string
  price: string
  currency: string
  purchase_date: string
  serial_number: string
  room_id: string
  category_id: string
}

export const emptyValues: FormValues = {
  name: '',
  brand: '',
  descriptor_notes: '',
  price: '',
  currency: 'SEK',
  purchase_date: '',
  serial_number: '',
  room_id: '',
  category_id: '',
}

export function valuesFromItem(item: ItemDetail): FormValues {
  return {
    name: item.name,
    brand: item.brand ?? '',
    descriptor_notes: item.descriptor_notes ?? '',
    price: item.purchase_price_minor === null ? '' : String(item.purchase_price_minor / 100),
    currency: item.currency ?? 'SEK',
    purchase_date: item.purchase_date ?? '',
    serial_number: item.serial_number ?? '',
    room_id: item.room?.id ?? '',
    category_id: item.category?.id ?? '',
  }
}

/** Turn form strings into the API payload, omitting anything the owner left blank. */
export function toPayload(values: FormValues, suggested: string[]): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    name: values.name.trim(),
    brand: values.brand.trim() || null,
    descriptor_notes: values.descriptor_notes.trim() || null,
    serial_number: values.serial_number.trim() || null,
    room_id: values.room_id || null,
    category_id: values.category_id || null,
    purchase_date: values.purchase_date || null,
    ai_suggested_fields: suggested,
  }
  const price = values.price.trim()
  if (price !== '') {
    payload.purchase_price_minor = Math.round(Number(price) * 100)
    payload.currency = values.currency
  } else {
    payload.purchase_price_minor = null
    payload.currency = null
  }
  return payload
}

type Props = {
  values: FormValues
  onChange: (values: FormValues) => void
  /** Fields the model filled that the owner has not edited, so they can be marked as guesses. */
  suggested: string[]
  onSubmit: (event: FormEvent) => void
  submitLabel: string
  busy?: boolean
}

export default function ItemForm({ values, onChange, suggested, onSubmit, submitLabel, busy }: Props) {
  const [rooms, setRooms] = useState<TaxonomyEntry[]>([])
  const [categories, setCategories] = useState<TaxonomyEntry[]>([])

  useEffect(() => {
    api.rooms().then(setRooms).catch(() => setRooms([]))
    api.categories().then(setCategories).catch(() => setCategories([]))
  }, [])

  const set = (field: keyof FormValues) => (event: { target: { value: string } }) =>
    onChange({ ...values, [field]: event.target.value })

  const mark = (field: string) => (suggested.includes(field) ? 'suggested' : undefined)
  const badge = (field: string) =>
    suggested.includes(field) ? <span className="badge">suggested</span> : null

  return (
    <form onSubmit={onSubmit}>
      <label>
        <span>Name{badge('name')}</span>
        <input value={values.name} onChange={set('name')} className={mark('name')} required />
      </label>

      <div className="row">
        <label>
          <span>Room</span>
          <select value={values.room_id} onChange={set('room_id')}>
            <option value="">Unassigned</option>
            {rooms.map((room) => (
              <option key={room.id} value={room.id}>
                {room.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Category{badge('category')}</span>
          <select value={values.category_id} onChange={set('category_id')} className={mark('category')}>
            <option value="">Unassigned</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label>
        <span>Brand{badge('brand')}</span>
        <input value={values.brand} onChange={set('brand')} className={mark('brand')} />
      </label>

      <label>
        <span>Notes{badge('descriptor_notes')}</span>
        <textarea
          value={values.descriptor_notes}
          onChange={set('descriptor_notes')}
          className={mark('descriptor_notes')}
        />
      </label>

      <div className="row">
        <label>
          <span>Price</span>
          <input
            value={values.price}
            onChange={set('price')}
            inputMode="decimal"
            placeholder="0.00"
          />
        </label>
        <label style={{ maxWidth: 110 }}>
          <span>Currency</span>
          <input value={values.currency} onChange={set('currency')} maxLength={3} />
        </label>
      </div>

      <div className="row">
        <label>
          <span>Purchased</span>
          <input type="date" value={values.purchase_date} onChange={set('purchase_date')} />
        </label>
        <label>
          <span>Serial number</span>
          <input value={values.serial_number} onChange={set('serial_number')} />
        </label>
      </div>

      <button className="primary" style={{ width: '100%' }} disabled={busy || !values.name.trim()}>
        {busy ? <span className="spinner" /> : submitLabel}
      </button>
    </form>
  )
}
