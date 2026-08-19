import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { type BoardSummary, api } from '../api'

export default function Boards() {
  const navigate = useNavigate()
  const [boards, setBoards] = useState<BoardSummary[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.boards().then(setBoards).catch(() => {})
  }, [])

  async function create(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      const board = await api.createBoard(name.trim())
      navigate(`/boards/${board.id}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1>Boards</h1>
      <p className="muted">Put things side by side — an outfit, a room, a plan.</p>

      <form onSubmit={create} className="row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New board name" />
        <button className="primary" style={{ flex: 'none' }} disabled={!name.trim() || busy}>
          Create
        </button>
      </form>

      <div className="item-list" style={{ marginTop: 16 }}>
        {boards.map((board) => (
          <Link className="item-row" key={board.id} to={`/boards/${board.id}`}>
            {board.cover_thumb_url ? (
              <img src={board.cover_thumb_url} alt="" />
            ) : (
              <span className="placeholder">◫</span>
            )}
            <span>
              <strong>{board.name}</strong>
              <br />
              <span className="muted">
                {board.item_count} item{board.item_count === 1 ? '' : 's'}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </>
  )
}
