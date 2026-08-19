import { type PointerEvent as ReactPointerEvent, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { type ItemSummary, api } from '../api'
import { BackIcon } from '../components/Icons'

/** Placements are stored in a fixed 1000x1000 unit space, so a board arranged on a laptop
 *  reopens correctly on a phone. The canvas element scales those units to whatever size it is. */
const CANVAS_UNITS = 1000

type Placed = {
  item: ItemSummary
  position_x: number
  position_y: number
  scale: number
  z_index: number
}

export default function BoardCanvas() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const canvasRef = useRef<HTMLDivElement>(null)
  const dragOffset = useRef<{ x: number; y: number } | null>(null)

  const [name, setName] = useState('')
  const [placed, setPlaced] = useState<Placed[]>([])
  const [inventory, setInventory] = useState<ItemSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!id) return
    api.board(id).then((board) => {
      setName(board.name)
      setPlaced(
        board.placements.map((p) => ({
          item: p.item,
          position_x: p.position_x,
          position_y: p.position_y,
          scale: p.scale,
          z_index: p.z_index,
        })),
      )
    })
    api.items({ limit: 200 }).then((page) => setInventory(page.items.filter((i) => i.thumb_url)))
  }, [id])

  function toCanvasUnits(clientX: number, clientY: number) {
    const box = canvasRef.current!.getBoundingClientRect()
    return {
      x: ((clientX - box.left) / box.width) * CANVAS_UNITS,
      y: ((clientY - box.top) / box.height) * CANVAS_UNITS,
    }
  }

  function startDrag(event: ReactPointerEvent<HTMLImageElement>, itemId: string) {
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = toCanvasUnits(event.clientX, event.clientY)
    const target = placed.find((p) => p.item.id === itemId)!
    dragOffset.current = { x: point.x - target.position_x, y: point.y - target.position_y }
    setSelected(itemId)
  }

  function onDrag(event: ReactPointerEvent<HTMLImageElement>, itemId: string) {
    const offset = dragOffset.current
    if (!offset || !event.currentTarget.hasPointerCapture(event.pointerId)) return
    const point = toCanvasUnits(event.clientX, event.clientY)
    // Read the offset into a local before the updater: React runs the updater later, and by then
    // pointerup may have cleared the ref, which would throw mid-drag.
    setPlaced((current) =>
      current.map((p) =>
        p.item.id === itemId
          ? {
              ...p,
              position_x: clamp(point.x - offset.x),
              position_y: clamp(point.y - offset.y),
            }
          : p,
      ),
    )
    setDirty(true)
  }

  const clamp = (value: number) => Math.max(0, Math.min(CANVAS_UNITS, value))

  function addToBoard(item: ItemSummary) {
    if (placed.some((p) => p.item.id === item.id)) return
    const top = placed.reduce((max, p) => Math.max(max, p.z_index), 0)
    setPlaced((current) => [
      ...current,
      { item, position_x: 400, position_y: 400, scale: 1, z_index: top + 1 },
    ])
    setSelected(item.id)
    setDirty(true)
  }

  function update(itemId: string, changes: Partial<Placed>) {
    setPlaced((current) => current.map((p) => (p.item.id === itemId ? { ...p, ...changes } : p)))
    setDirty(true)
  }

  function removeFromBoard(itemId: string) {
    setPlaced((current) => current.filter((p) => p.item.id !== itemId))
    setSelected(null)
    setDirty(true)
  }

  async function save() {
    if (!id) return
    setSaving(true)
    try {
      await api.savePlacements(
        id,
        placed.map((p) => ({
          item_id: p.item.id,
          position_x: p.position_x,
          position_y: p.position_y,
          scale: p.scale,
          z_index: p.z_index,
        })),
      )
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }

  async function removeBoard() {
    if (!id || !confirm('Delete this board? The items on it are not affected.')) return
    await api.deleteBoard(id)
    navigate('/boards', { replace: true })
  }

  const current = placed.find((p) => p.item.id === selected)


  return (
    <>
      <Link className="back-link" to="/boards">
        <BackIcon /> All boards
      </Link>
      <h1>{name}</h1>

      <div className="canvas-layout" style={{ marginTop: 'var(--s-5)' }}>
        <div>
          <div className="canvas" ref={canvasRef} onPointerDown={() => setSelected(null)}>
            {placed.map((p) => (
              <img
                key={p.item.id}
                src={p.item.thumb_url!}
                alt={p.item.name}
                className={selected === p.item.id ? 'selected' : undefined}
                style={{
                  left: `${(p.position_x / CANVAS_UNITS) * 100}%`,
                  top: `${(p.position_y / CANVAS_UNITS) * 100}%`,
                  zIndex: p.z_index,
                  transform: `translate(-50%, -50%) scale(${p.scale})`,
                }}
                onPointerDown={(event) => {
                  event.stopPropagation()
                  startDrag(event, p.item.id)
                }}
                onPointerMove={(event) => onDrag(event, p.item.id)}
                onPointerUp={() => (dragOffset.current = null)}
              />
            ))}
          </div>

          {current && (
            <div style={{ marginTop: 'var(--s-4)' }}>
              <label>
                <span>Size — {current.item.name}</span>
                <input
                  type="range"
                  min={0.3}
                  max={3}
                  step={0.05}
                  value={current.scale}
                  onChange={(event) =>
                    update(current.item.id, { scale: Number(event.target.value) })
                  }
                />
              </label>
              <div className="row">
                <button
                  onClick={() =>
                    update(current.item.id, {
                      z_index: placed.reduce((max, p) => Math.max(max, p.z_index), 0) + 1,
                    })
                  }
                >
                  Bring to front
                </button>
                <button className="danger" onClick={() => removeFromBoard(current.item.id)}>
                  Take off board
                </button>
              </div>
            </div>
          )}

          <div className="row" style={{ marginTop: 'var(--s-5)' }}>
            <button className="primary" onClick={save} disabled={!dirty || saving}>
              {saving ? <span className="spinner" /> : dirty ? 'Save layout' : 'Saved'}
            </button>
            <button className="danger shrink" onClick={removeBoard}>
              Delete board
            </button>
          </div>
        </div>

        <div>
          <span className="eyebrow">Your things</span>
          <div className="tray">
            {inventory.map((item) => (
              <img
                key={item.id}
                src={item.thumb_url!}
                alt={item.name}
                title={item.name}
                onClick={() => addToBoard(item)}
                className={placed.some((p) => p.item.id === item.id) ? 'placed' : undefined}
              />
            ))}
          </div>
          {inventory.length === 0 && (
            <p className="muted">Photograph some things first and they will appear here.</p>
          )}
        </div>
      </div>
    </>
  )
}
