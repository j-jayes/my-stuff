import { Fragment, useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useSearchParams } from 'react-router-dom'

import { type TaxonomyEntry, api } from '../api'
import { AddIcon, BoardsIcon, GalleryIcon, ItemsIcon } from './Icons'

/** Desktop-only left rail: sections, then rooms and categories as filters.
 *
 *  The filters work by writing to the URL rather than by talking to Inventory, which is why the
 *  filter state lives in search params. That also makes any filtered view bookmarkable.
 */
export default function Sidebar() {
  const [rooms, setRooms] = useState<TaxonomyEntry[]>([])
  const [categories, setCategories] = useState<TaxonomyEntry[]>([])
  const [params] = useSearchParams()
  const { pathname } = useLocation()

  useEffect(() => {
    api.rooms().then(setRooms).catch(() => {})
    api.categories().then(setCategories).catch(() => {})
    // Counts change as items come and go, so refetch when navigating between pages.
  }, [pathname])

  const activeRoom = params.get('room') ?? ''
  const activeCategory = params.get('category') ?? ''

  // Toggling off returns to the unfiltered list; the search term is deliberately preserved.
  const filterHref = (key: 'room' | 'category', id: string, isActive: boolean) => {
    const next = new URLSearchParams(params)
    if (isActive) next.delete(key)
    else next.set(key, id)
    const query = next.toString()
    return query ? `/?${query}` : '/'
  }

  const group = (
    title: string,
    entries: TaxonomyEntry[],
    key: 'room' | 'category',
    active: string,
  ) => {
    const top = entries.filter((entry) => !entry.parent_id)
    const childrenOf = (id: string) => entries.filter((entry) => entry.parent_id === id)
    // Kitchenware alone has twelve shelves. Listing them all the time would bury the other
    // eight categories, so a parent's children appear only once that branch is selected.
    const activeEntry = entries.find((entry) => entry.id === active)
    const open = activeEntry?.parent_id ?? (childrenOf(active).length ? active : null)

    const link = (entry: TaxonomyEntry, nested: boolean) => {
      const on = active === entry.id
      return (
        <Link
          key={entry.id}
          to={filterHref(key, entry.id, on)}
          className={[on ? 'on' : '', nested ? 'nested' : ''].filter(Boolean).join(' ') || undefined}
          aria-current={on ? 'true' : undefined}
        >
          <span>{entry.name}</span>
          {entry.item_count > 0 && <span className="count numeric">{entry.item_count}</span>}
        </Link>
      )
    }

    return (
      <div className="side-group">
        <span className="eyebrow">{title}</span>
        <div className="filter-list">
          {/* Plain links, not NavLink: every one of these points at the same pathname and differs
              only in the query, so NavLink would mark all of them active and announce each room as
              the current page. */}
          {top.map((entry) => (
            <Fragment key={entry.id}>
              {link(entry, false)}
              {open === entry.id && childrenOf(entry.id).map((child) => link(child, true))}
            </Fragment>
          ))}
        </div>
      </div>
    )
  }

  return (
    <aside className="sidebar">
      <nav aria-label="Sections">
        <div className="brand">My Stuff</div>
        <div className="side-nav">
          <NavLink to="/" end>
            <ItemsIcon /> Items
          </NavLink>
          <NavLink to="/gallery">
            <GalleryIcon /> Gallery
          </NavLink>
          <NavLink to="/boards">
            <BoardsIcon /> Boards
          </NavLink>
          <NavLink to="/add">
            <AddIcon /> Add something
          </NavLink>
        </div>
      </nav>

      {/* The filters navigate too, so they belong in their own labelled landmark rather than
          sitting loose in the complementary region. */}
      <nav aria-label="Filters">
        {rooms.length > 0 && group('Rooms', rooms, 'room', activeRoom)}
        {categories.length > 0 && group('Categories', categories, 'category', activeCategory)}
      </nav>
    </aside>
  )
}
