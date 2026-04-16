'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin() {
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Błąd logowania')

      localStorage.setItem('bezp_token', data.access_token)

      const meRes = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })
      const meData = await meRes.json()

      router.push(meData.has_profile ? '/chat' : '/quiz')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd logowania')
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister() {
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Błąd rejestracji')
      setMessage(data.message || 'Zarejestrowano pomyślnie.')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd rejestracji')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-white mb-1 text-center">BEZ PIERDOLENIA</h1>
        <p className="text-zinc-500 text-sm text-center mb-8">AI trener personalny</p>

        <div className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500"
          />
          <input
            type="password"
            placeholder="Hasło"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            className="w-full bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500"
          />

          {error && <p className="text-red-400 text-sm">{error}</p>}
          {message && <p className="text-green-400 text-sm">{message}</p>}

          <div className="flex gap-3 pt-1">
            <button
              onClick={handleLogin}
              disabled={loading}
              className="flex-1 bg-white text-black font-medium py-3 rounded hover:bg-zinc-200 disabled:opacity-50 transition-colors"
            >
              Zaloguj się
            </button>
            <button
              onClick={handleRegister}
              disabled={loading}
              className="flex-1 border border-zinc-600 text-white font-medium py-3 rounded hover:bg-zinc-800 disabled:opacity-50 transition-colors"
            >
              Zarejestruj się
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
