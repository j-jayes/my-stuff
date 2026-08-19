import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { api } from './api'
import { AddIcon, BoardsIcon, GalleryIcon, ItemsIcon } from './components/Icons'
import Sidebar from './components/Sidebar'
import AddItem from './pages/AddItem'
import BoardCanvas from './pages/BoardCanvas'
import Boards from './pages/Boards'
import Gallery from './pages/Gallery'
import Inventory from './pages/Inventory'
import ItemDetail from './pages/ItemDetail'
import Login from './pages/Login'

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null)

  useEffect(() => {
    api
      .me()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false))
  }, [])

  if (authed === null) {
    return (
      <div className="centred">
        <span className="spinner" />
      </div>
    )
  }

  if (!authed) return <Login onSignedIn={() => setAuthed(true)} />

  return (
    <div className="shell">
      {/* Both navigations are always rendered and CSS shows one. Because the hidden one is
          display:none it leaves the accessibility tree entirely, so a screen reader never meets
          two sets of the same links. */}
      <Sidebar />

      <main className="main">
        <Routes>
          <Route path="/" element={<Inventory />} />
          <Route path="/add" element={<AddItem />} />
          <Route path="/items/:id" element={<ItemDetail />} />
          <Route path="/gallery" element={<Gallery />} />
          <Route path="/boards" element={<Boards />} />
          <Route path="/boards/:id" element={<BoardCanvas />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <nav className="tabbar" aria-label="Sections">
        <NavLink to="/" end>
          <ItemsIcon />
          Items
        </NavLink>
        <NavLink to="/gallery">
          <GalleryIcon />
          Gallery
        </NavLink>
        <NavLink to="/add">
          <AddIcon />
          Add
        </NavLink>
        <NavLink to="/boards">
          <BoardsIcon />
          Boards
        </NavLink>
      </nav>
    </div>
  )
}
