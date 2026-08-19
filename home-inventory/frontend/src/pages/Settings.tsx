import { type FormEvent, useEffect, useState } from 'react'

import { type TaxonomyEntry, api, invalidateTaxonomy } from '../api'

type Kind = 'rooms' | 'categories'

/** Rooms and categories were only editable by hand against the API — api.addRoom and
 *  api.addCategory existed but nothing called them (FR-015). With twelve shelves under
 *  Kitchenware that stopped being tolerable. Deliberately plain: a list, a rename, a delete. */
export default function Settings() {
  const [rooms, setRooms] = useState<TaxonomyEntry[]>([])
  const [categories, setCategories] = useState<TaxonomyEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function reload() {
    invalidateTaxonomy()
    const [r, c] = await Promise.all([api.rooms(), api.categories()])
    setRooms(r)
    setCategories(c)
  }

  useEffect(() => {
    reload().catch(() => setError('Could not load rooms and categories.'))
  }, [])

  /** Every write goes through here so one message surface reports them all. The server is
   *  the authority on what is allowed — an in-use category, a parent with children — and it
   *  says why in the error, so there is nothing to duplicate in the client. */
  async function attempt(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      await reload()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That did not work.')
    } finally {
      setBusy(false)
    }
  }

  const rename = (kind: Kind, entry: TaxonomyEntry) => {
    const name = window.prompt(`Rename "${entry.name}" to`, entry.name)
    if (!name || name === entry.name) return
    void attempt(() =>
      kind === 'rooms' ? api.renameRoom(entry.id, name) : api.renameCategory(entry.id, name),
    )
  }

  const remove = (kind: Kind, entry: TaxonomyEntry) => {
    if (!window.confirm(`Delete "${entry.name}"?`)) return
    void attempt(() => (kind === 'rooms' ? api.deleteRoom(entry.id) : api.deleteCategory(entry.id)))
  }

  const list = (kind: Kind, entries: TaxonomyEntry[], nested: boolean) =>
    entries.map((entry) => (
      <li key={entry.id} className={nested ? 'nested' : undefined}>
        <span>
          {entry.name}
          {entry.item_count > 0 && <span className="count numeric"> {entry.item_count}</span>}
        </span>
        <span className="row shrink">
          <button className="quiet" disabled={busy} onClick={() => rename(kind, entry)}>
            Rename
          </button>
          <button className="quiet" disabled={busy} onClick={() => remove(kind, entry)}>
            Delete
          </button>
        </span>
      </li>
    ))

  return (
    <>
      <h1>Rooms and categories</h1>
      {error && <p className="error">{error}</p>}

      <h2 className="section-head">Rooms</h2>
      <ul className="taxonomy-list">{list('rooms', rooms, false)}</ul>
      <AddForm
        label="Add a room"
        busy={busy}
        onAdd={(name) => attempt(() => api.addRoom(name))}
      />

      <h2 className="section-head">Categories</h2>
      <ul className="taxonomy-list">
        {categories
          .filter((category) => !category.parent_id)
          .flatMap((parent) => [
            ...list('categories', [parent], false),
            ...list(
              'categories',
              categories.filter((child) => child.parent_id === parent.id),
              true,
            ),
          ])}
      </ul>
      <AddForm
        label="Add a category"
        busy={busy}
        parents={categories.filter((category) => !category.parent_id)}
        onAdd={(name, parentId) => attempt(() => api.addCategory(name, parentId))}
      />
    </>
  )
}

function AddForm({
  label,
  busy,
  parents,
  onAdd,
}: {
  label: string
  busy: boolean
  parents?: TaxonomyEntry[]
  onAdd: (name: string, parentId: string | null) => void
}) {
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    onAdd(name.trim(), parentId || null)
    setName('')
  }

  return (
    <form onSubmit={submit} className="row">
      <input value={name} onChange={(event) => setName(event.target.value)} aria-label={label} />
      {parents && (
        <select
          value={parentId}
          onChange={(event) => setParentId(event.target.value)}
          aria-label="Inside"
        >
          <option value="">Top level</option>
          {parents.map((parent) => (
            <option key={parent.id} value={parent.id}>
              Inside {parent.name}
            </option>
          ))}
        </select>
      )}
      <button className="shrink" disabled={busy || !name.trim()}>
        {label}
      </button>
    </form>
  )
}
