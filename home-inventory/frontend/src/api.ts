export type NamedRef = { id: string; name: string }

/** parent_id is always null for rooms; for a category it names the category it sits under. */
export type TaxonomyEntry = NamedRef & { item_count: number; parent_id: string | null }

export type ItemSummary = {
  id: string
  name: string
  brand: string | null
  thumb_url: string | null
  room: NamedRef | null
  category: NamedRef | null
  purchase_price_minor: number | null
  currency: string | null
  quantity: number
  created_at: string
}

export type ItemDetail = ItemSummary & {
  descriptor_notes: string | null
  second_hand: boolean
  purchase_date: string | null
  serial_number: string | null
  source_url: string | null
  image_url: string | null
  receipt_url: string | null
  source_photo_url: string | null
  ai_suggested_fields: string[]
  updated_at: string
}

export type BrandEntry = { name: string; item_count: number }

export type Suggestion = {
  name: string
  brand: string | null
  descriptor_notes: string | null
  category_id: string | null
  room_id: string | null
  purchase_price_minor: number | null
  currency: string | null
  purchase_date: string | null
  quantity: number
  /** Null when nothing said either way, which is not the same as "bought new". */
  second_hand: boolean | null
  source_url: string | null
  image_url: string | null
  /** Every photograph the page offered; image_url is the first of them. */
  image_urls: string[]
  suggested_fields: string[]
}

export type Placement = {
  id: string
  item: ItemSummary
  position_x: number
  position_y: number
  scale: number
  z_index: number
}

export type PlacementWrite = {
  item_id: string
  position_x: number
  position_y: number
  scale: number
  z_index: number
}

export type BoardDetail = { id: string; name: string; created_at: string; placements: Placement[] }
export type BoardSummary = { id: string; name: string; item_count: number; cover_thumb_url: string | null }

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', ...init })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // A non-JSON error body is not worth failing over; the status carries the meaning.
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

let roomsCache: Promise<TaxonomyEntry[]> | null = null
let categoriesCache: Promise<TaxonomyEntry[]> | null = null

/** Drop the cached room and category lists. Called after any write to either, and after item
 *  writes, because both carry item counts. */
export function invalidateTaxonomy(): void {
  roomsCache = null
  categoriesCache = null
}

export const api = {
  login: (password: string) => request<void>('/api/auth/login', json({ password })),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  me: () => request<{ authenticated: boolean }>('/api/auth/me'),

  // Rooms and categories are wanted by both the sidebar and the inventory page, and they change
  // about once a year. Cache the in-flight promise so navigating does not refetch them, and
  // drop the cache whenever something writes to either list.
  rooms: () => (roomsCache ??= request<TaxonomyEntry[]>('/api/rooms')),
  categories: () => (categoriesCache ??= request<TaxonomyEntry[]>('/api/categories')),
  addRoom: (name: string) =>
    request<TaxonomyEntry>('/api/rooms', json({ name })).finally(invalidateTaxonomy),
  addCategory: (name: string, parent_id?: string | null) =>
    request<TaxonomyEntry>('/api/categories', json({ name, parent_id: parent_id ?? null })).finally(
      invalidateTaxonomy,
    ),
  renameRoom: (id: string, name: string) =>
    request<TaxonomyEntry>(`/api/rooms/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }).finally(invalidateTaxonomy),
  renameCategory: (id: string, name: string) =>
    request<TaxonomyEntry>(`/api/categories/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }).finally(invalidateTaxonomy),
  deleteRoom: (id: string) =>
    request<void>(`/api/rooms/${id}`, { method: 'DELETE' }).finally(invalidateTaxonomy),
  deleteCategory: (id: string) =>
    request<void>(`/api/categories/${id}`, { method: 'DELETE' }).finally(invalidateTaxonomy),

  items: (params: { q?: string; room_id?: string; category_id?: string; limit?: number }) => {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value) query.set(key, String(value))
    }
    return request<{ items: ItemSummary[]; total: number }>(`/api/items?${query}`)
  },
  item: (id: string) => request<ItemDetail>(`/api/items/${id}`),
  brands: () => request<BrandEntry[]>('/api/items/brands'),
  similar: (name: string) =>
    request<ItemSummary[]>(`/api/items/similar?name=${encodeURIComponent(name)}`),

  /** One question — "what is this?" — asked with whatever evidence there is. Any combination
   *  of a photo, a product link, and whatever the owner typed. */
  suggest: (input: { image?: Blob | null; url?: string; note?: string }) => {
    const form = new FormData()
    if (input.image) form.append('image', input.image, 'photo.jpg')
    if (input.url) form.append('url', input.url)
    if (input.note) form.append('note', input.note)
    return request<Suggestion>('/api/items/suggest', { method: 'POST', body: form })
  },

  createItem: (payload: Record<string, unknown>, image?: Blob | null, receipt?: Blob | null) => {
    const form = new FormData()
    form.append('payload', JSON.stringify(payload))
    if (image) form.append('image', image, 'photo.jpg')
    if (receipt) form.append('receipt', receipt, 'receipt.jpg')
    return request<ItemDetail>('/api/items', { method: 'POST', body: form }).finally(
      invalidateTaxonomy,
    )
  },
  updateItem: (id: string, payload: Record<string, unknown>, image?: Blob | null, receipt?: Blob | null) => {
    const form = new FormData()
    form.append('payload', JSON.stringify(payload))
    if (image) form.append('image', image, 'photo.jpg')
    if (receipt) form.append('receipt', receipt, 'receipt.jpg')
    return request<ItemDetail>(`/api/items/${id}`, { method: 'PATCH', body: form }).finally(
      invalidateTaxonomy,
    )
  },
  deleteItem: (id: string) =>
    request<void>(`/api/items/${id}`, { method: 'DELETE' }).finally(invalidateTaxonomy),

  /** Offers a product photo made from the item's own photograph. Changes nothing until
   *  accepted, so a preview can be thrown away by ignoring it. */
  makeProductPhoto: (id: string) =>
    request<{ preview_url: string }>(`/api/items/${id}/product-photo`, { method: 'POST' }),
  acceptProductPhoto: (id: string) =>
    request<ItemDetail>(`/api/items/${id}/product-photo/accept`, { method: 'POST' }),

  boards: () => request<BoardSummary[]>('/api/boards'),
  board: (id: string) => request<BoardDetail>(`/api/boards/${id}`),
  createBoard: (name: string) => request<BoardDetail>('/api/boards', json({ name })),
  deleteBoard: (id: string) => request<void>(`/api/boards/${id}`, { method: 'DELETE' }),
  savePlacements: (id: string, placements: PlacementWrite[]) =>
    request<BoardDetail>(`/api/boards/${id}/placements`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ placements }),
    }),
}

/** What the line is worth: the unit price times how many there are. */
export function lineTotal(item: {
  purchase_price_minor: number | null
  quantity: number
}): number | null {
  return item.purchase_price_minor === null ? null : item.purchase_price_minor * item.quantity
}

export function formatPrice(minor: number | null, currency: string | null): string | null {
  if (minor === null || !currency) return null
  // Whole amounts lose the ".00" — most things are bought at round prices and the decimals are
  // just noise in a grid.
  const whole = minor % 100 === 0
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    minimumFractionDigits: whole ? 0 : 2,
  }).format(minor / 100)
}
