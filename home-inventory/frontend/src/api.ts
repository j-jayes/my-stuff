export type NamedRef = { id: string; name: string }

export type TaxonomyEntry = NamedRef & { item_count: number }

export type ItemSummary = {
  id: string
  name: string
  brand: string | null
  thumb_url: string | null
  room: NamedRef | null
  category: NamedRef | null
  created_at: string
}

export type ItemDetail = ItemSummary & {
  descriptor_notes: string | null
  purchase_price_minor: number | null
  currency: string | null
  purchase_date: string | null
  serial_number: string | null
  source_url: string | null
  image_url: string | null
  receipt_url: string | null
  ai_suggested_fields: string[]
  updated_at: string
}

export type Suggestion = {
  name: string
  category: string | null
  brand: string | null
  descriptor_notes: string | null
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

export const api = {
  login: (password: string) => request<void>('/api/auth/login', json({ password })),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  me: () => request<{ authenticated: boolean }>('/api/auth/me'),

  rooms: () => request<TaxonomyEntry[]>('/api/rooms'),
  categories: () => request<TaxonomyEntry[]>('/api/categories'),
  addRoom: (name: string) => request<TaxonomyEntry>('/api/rooms', json({ name })),
  addCategory: (name: string) => request<TaxonomyEntry>('/api/categories', json({ name })),

  items: (params: { q?: string; room_id?: string; category_id?: string; limit?: number }) => {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value) query.set(key, String(value))
    }
    return request<{ items: ItemSummary[]; total: number }>(`/api/items?${query}`)
  },
  item: (id: string) => request<ItemDetail>(`/api/items/${id}`),

  extract: (image: Blob) => {
    const form = new FormData()
    form.append('image', image, 'photo.jpg')
    return request<Suggestion>('/api/items/extract', { method: 'POST', body: form })
  },
  scrape: (url: string) =>
    request<{ title: string | null; image_url: string | null; source_url: string }>(
      '/api/items/scrape',
      json({ url }),
    ),

  createItem: (payload: Record<string, unknown>, image?: Blob | null, receipt?: Blob | null) => {
    const form = new FormData()
    form.append('payload', JSON.stringify(payload))
    if (image) form.append('image', image, 'photo.jpg')
    if (receipt) form.append('receipt', receipt, 'receipt.jpg')
    return request<ItemDetail>('/api/items', { method: 'POST', body: form })
  },
  updateItem: (id: string, payload: Record<string, unknown>, image?: Blob | null, receipt?: Blob | null) => {
    const form = new FormData()
    form.append('payload', JSON.stringify(payload))
    if (image) form.append('image', image, 'photo.jpg')
    if (receipt) form.append('receipt', receipt, 'receipt.jpg')
    return request<ItemDetail>(`/api/items/${id}`, { method: 'PATCH', body: form })
  },
  deleteItem: (id: string) => request<void>(`/api/items/${id}`, { method: 'DELETE' }),

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

export function formatPrice(minor: number | null, currency: string | null): string | null {
  if (minor === null || !currency) return null
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(minor / 100)
}
