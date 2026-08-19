import { type FormEvent, useState } from 'react'

import { api } from '../api'

export default function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.login(password)
      onSignedIn()
    } catch {
      setError('That password was not right.')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <div className="login-card">
        <h1>My Stuff</h1>
        <p className="login-lede">Everything in the house, catalogued.</p>
        <form onSubmit={submit}>
          <label>
            <span>Password</span>
            <input
              type="password"
              value={password}
              autoFocus
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="primary full" disabled={busy || !password}>
            {busy ? <span className="spinner" /> : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
