import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { api } from './api'
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
      <div className="app" style={{ paddingTop: 40, textAlign: 'center' }}>
        <span className="spinner" />
      </div>
    )
  }

  if (!authed) return <Login onSignedIn={() => setAuthed(true)} />

  return (
    <>
      <div className="app">
        <Routes>
          <Route path="/" element={<Inventory />} />
          <Route path="/add" element={<AddItem />} />
          <Route path="/items/:id" element={<ItemDetail />} />
          <Route path="/gallery" element={<Gallery />} />
          <Route path="/boards" element={<Boards />} />
          <Route path="/boards/:id" element={<BoardCanvas />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <nav className="nav">
        <NavLink to="/" end>
          <span className="glyph">☰</span>Items
        </NavLink>
        <NavLink to="/gallery">
          <span className="glyph">▦</span>Gallery
        </NavLink>
        <NavLink to="/add">
          <span className="glyph">＋</span>Add
        </NavLink>
        <NavLink to="/boards">
          <span className="glyph">◫</span>Boards
        </NavLink>
      </nav>
    </>
  )
}
