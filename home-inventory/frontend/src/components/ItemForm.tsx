import { type FormEvent, useEffect, useState } from 'react'

import { type ItemDetail, type TaxonomyEntry, api, formatPrice } from '../api'

export type FormValues = {
  name: string
  brand: string
  descriptor_notes: string
  price: string
  currency: string
  quantity: string
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
  quantity: '1',
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
    quantity: String(item.quantity),
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
    quantity: Math.max(1, Math.round(Number(values.quantity) || 1)),
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

  const quantity = Math.max(1, Math.round(Number(values.quantity) || 1))
  const unitPrice = values.price.trim() === '' ? null : Math.round(Number(values.price) * 100)
  const total = unitPrice === null || Number.isNaN(unitPrice) ? null : unitPrice * quantity

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
            {categories
              .filter((category) => !category.parent_id)
              .map((parent) => {
                const children = categories.filter((c) => c.parent_id === parent.id)
                // A parent with shelves is still selectable — "somewhere in the kitchen" is a
                // legitimate answer — so it heads its own group rather than becoming a label.
                return children.length === 0 ? (
                  <option key={parent.id} value={parent.id}>
                    {parent.name}
                  </option>
                ) : (
                  <optgroup key={parent.id} label={parent.name}>
                    <option value={parent.id}>{parent.name} (unsorted)</option>
                    {children.map((child) => (
                      <option key={child.id} value={child.id}>
                        {child.name}
                      </option>
                    ))}
                  </optgroup>
                )
              })}
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
          <span>Price{quantity > 1 ? ' each' : ''}</span>
          <input
            value={values.price}
            onChange={set('price')}
            inputMode="decimal"
            placeholder="0.00"
          />
        </label>
        <label className="currency-field">
          <span>Currency</span>
          <input value={values.currency} onChange={set('currency')} maxLength={3} />
        </label>
        <label className="currency-field">
          <span>How many{badge('quantity')}</span>
          <input
            value={values.quantity}
            onChange={set('quantity')}
            className={mark('quantity')}
            inputMode="numeric"
            min={1}
            type="number"
          />
        </label>
      </div>

      {total !== null && quantity > 1 && (
        <p className="muted numeric" style={{ marginTop: 'calc(-1 * var(--s-2))', marginBottom: 'var(--s-4)' }}>
          {quantity} x {formatPrice(unitPrice, values.currency)} = {formatPrice(total, values.currency)}
        </p>
      )}

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

      <button className="primary full" disabled={busy || !values.name.trim()}>
        {busy ? <span className="spinner" /> : submitLabel}
      </button>
    </form>
  )
}
