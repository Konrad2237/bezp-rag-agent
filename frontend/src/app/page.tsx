'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function LoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [imie, setImie] = useState('')
  const [nazwisko, setNazwisko] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [gdprConsent, setGdprConsent] = useState(false)

  function reset() {
    setError('')
    setMessage('')
    setPassword('')
    setPasswordConfirm('')
    setGdprConsent(false)
  }

  function switchMode(next: 'login' | 'register') {
    reset()
    setMode(next)
  }

  async function handleLogin() {
    setError('')
    setMessage('')
    if (!email.trim() || !password) {
      setError('Podaj email i hasło')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = typeof data.detail === 'string'
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((e: { msg: string }) => e.msg).join(', ')
            : 'Błąd logowania'
        const msg = detail
          .replace('Invalid login credentials', 'Błędny email lub hasło')
          .replace('Email not confirmed', 'Email nie został potwierdzony — sprawdź skrzynkę')
          .replace('User already registered', 'Konto z tym emailem już istnieje')
        throw new Error(msg)
      }

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

    if (!imie.trim() || !nazwisko.trim()) {
      setError('Podaj imię i nazwisko')
      return
    }
    if (password !== passwordConfirm) {
      setError('Hasła nie są identyczne')
      return
    }
    if (password.length < 6) {
      setError('Hasło musi mieć minimum 6 znaków')
      return
    }
    if (!gdprConsent) {
      setError('Musisz zaakceptować politykę prywatności')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, imie: imie.trim(), nazwisko: nazwisko.trim() }),
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((e: { msg: string }) => e.msg).join(', ')
          : data.detail
        throw new Error(detail || 'Błąd rejestracji')
      }
      setError('')
      setPassword('')
      setPasswordConfirm('')
      setMessage(data.message || 'Zarejestrowano! Sprawdź skrzynkę i potwierdź email przed logowaniem.')
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

        {/* Przełącznik trybu */}
        <div className="flex mb-6 bg-zinc-900 rounded p-1">
          <button
            onClick={() => switchMode('login')}
            className={`flex-1 py-2 text-sm rounded transition-colors ${
              mode === 'login' ? 'bg-white text-black font-medium' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Logowanie
          </button>
          <button
            onClick={() => switchMode('register')}
            className={`flex-1 py-2 text-sm rounded transition-colors ${
              mode === 'register' ? 'bg-white text-black font-medium' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Rejestracja
          </button>
        </div>

        <div className="space-y-4">
          {mode === 'register' && (
            <>
              <input
                type="text"
                placeholder="Imię"
                value={imie}
                onChange={e => setImie(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500"
              />
              <input
                type="text"
                placeholder="Nazwisko"
                value={nazwisko}
                onChange={e => setNazwisko(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500"
              />
            </>
          )}

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
            onKeyDown={e => e.key === 'Enter' && mode === 'login' && handleLogin()}
            className="w-full bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500"
          />

          {mode === 'register' && (
            <>
              <input
                type="password"
                placeholder="Powtórz hasło"
                value={passwordConfirm}
                onChange={e => setPasswordConfirm(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500"
              />
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={gdprConsent}
                  onChange={e => setGdprConsent(e.target.checked)}
                  className="mt-0.5 accent-white w-4 h-4 shrink-0"
                />
                <span className="text-zinc-400 text-xs leading-snug">
                  Akceptuję{' '}
                  <Link href="/privacy" target="_blank" className="underline text-zinc-300 hover:text-white">
                    politykę prywatności
                  </Link>{' '}
                  i wyrażam zgodę na przetwarzanie danych osobowych, w tym danych zdrowotnych
                  (waga, kontuzje), w celu korzystania z usługi AI trenera personalnego.
                </span>
              </label>
            </>
          )}

          {error && <p className="text-red-400 text-sm">{error}</p>}
          {message && <p className="text-green-400 text-sm">{message}</p>}

          <button
            onClick={mode === 'login' ? handleLogin : handleRegister}
            disabled={loading}
            className="w-full bg-white text-black font-medium py-3 rounded hover:bg-zinc-200 disabled:opacity-50 transition-colors"
          >
            {loading ? '...' : mode === 'login' ? 'Zaloguj się' : 'Zarejestruj się'}
          </button>
        </div>
      </div>
    </div>
  )
}
