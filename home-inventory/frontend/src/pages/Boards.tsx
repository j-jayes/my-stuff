import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { type BoardSummary, api } from '../api'
import { BoardsIcon } from '../components/Icons'

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
      <p className="muted" style={{ marginTop: 'var(--s-2)' }}>
        Put things side by side — an outfit, a room, a plan.
      </p>

      <form onSubmit={create} className="row" style={{ marginTop: 'var(--s-5)' }}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="New board name"
          aria-label="New board name"
          className="search-wide"
        />
        <button className="primary shrink" disabled={!name.trim() || busy}>
          Create
        </button>
      </form>

      {boards.length === 0 ? (
        <p className="muted" style={{ marginTop: 'var(--s-6)' }}>
          No boards yet.
        </p>
      ) : (
        <div className="board-list" style={{ marginTop: 'var(--s-6)' }}>
          {boards.map((board) => (
            <Link className="board-card" key={board.id} to={`/boards/${board.id}`}>
              {board.cover_thumb_url ? (
                <img src={board.cover_thumb_url} alt="" />
              ) : (
                <span className="board-empty">
                  <BoardsIcon size={22} />
                </span>
              )}
              <span>
                <strong>{board.name}</strong>
                <br />
                <span className="muted numeric">
                  {board.item_count} item{board.item_count === 1 ? '' : 's'}
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
