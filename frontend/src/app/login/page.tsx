'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const inputCls = 'w-full bg-[#111111] border border-[#2A2A2A] text-[#F2EEE8] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#00FF88] transition-colors placeholder:text-zinc-600'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const planParam = searchParams.get('plan') ?? ''
  const modeParam = searchParams.get('mode') === 'register' ? 'register' : 'login'

  const [mode, setMode] = useState<'login' | 'register'>(modeParam)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [imie, setImie] = useState('')
  const [nazwisko, setNazwisko] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [gdprConsent, setGdprConsent] = useState(false)

  // Gdy URL zmieni się (np. user cofa z /login?mode=register na /login), sync state
  useEffect(() => {
    setMode(modeParam)
  }, [modeParam])

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

  function routeAfterLogin(subscriptionStatus: string | null, hasProfile: boolean) {
    if (subscriptionStatus === 'active') {
      router.push(hasProfile ? '/chat' : '/quiz')
    } else {
      router.push('/pricing')
    }
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
      if (data.refresh_token) localStorage.setItem('bezp_refresh_token', data.refresh_token)

      const meRes = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })
      const meData = await meRes.json()
      routeAfterLogin(meData.subscription_status, meData.has_profile)
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
      // 1. Zarejestruj konto
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

      // 2. Cichy auto-login — zapisz token żeby /pricing mogło od razu iść do Stripe
      const loginRes = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (loginRes.ok) {
        const loginData = await loginRes.json()
        localStorage.setItem('bezp_token', loginData.access_token)
        if (loginData.refresh_token) localStorage.setItem('bezp_refresh_token', loginData.refresh_token)
      }
      // Niezależnie czy auto-login się udał — zawsze idź do /pricing
      router.push('/pricing')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd rejestracji')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-full bg-[#00FF88] flex items-center justify-center font-bold text-black text-2xl mb-3"
            style={{ boxShadow: '0 0 30px rgba(0,255,136,0.3)' }}
          >
            P
          </div>
          <h1 className="text-xl font-bold text-white">PITBUL</h1>
          <p className="text-[#00FF88] text-xs mt-1">Twój trener AI</p>
        </div>

        {/* Przełącznik trybu */}
        <div className="flex mb-6 bg-[#111111] border border-[#2A2A2A] rounded-xl p-1">
          <button
            onClick={() => switchMode('login')}
            className={`flex-1 py-2 text-sm rounded-lg transition-colors font-medium ${
              mode === 'login' ? 'bg-[#00FF88] text-black' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Logowanie
          </button>
          <button
            onClick={() => switchMode('register')}
            className={`flex-1 py-2 text-sm rounded-lg transition-colors font-medium ${
              mode === 'register' ? 'bg-[#00FF88] text-black' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Rejestracja
          </button>
        </div>

        <div className="space-y-3">
          {mode === 'register' && (
            <>
              <input type="text" placeholder="Imię" value={imie} onChange={e => setImie(e.target.value)} className={inputCls} />
              <input type="text" placeholder="Nazwisko" value={nazwisko} onChange={e => setNazwisko(e.target.value)} className={inputCls} />
            </>
          )}

          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} className={inputCls} />
          <input
            type="password"
            placeholder="Hasło"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && mode === 'login' && handleLogin()}
            className={inputCls}
          />

          {mode === 'register' && (
            <>
              <input type="password" placeholder="Powtórz hasło" value={passwordConfirm} onChange={e => setPasswordConfirm(e.target.value)} className={inputCls} />
              <label className="flex items-start gap-3 cursor-pointer" onClick={() => setGdprConsent(v => !v)}>
                <div className={`mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${gdprConsent ? 'bg-[#00FF88] border-[#00FF88]' : 'border-[#2A2A2A]'}`}>
                  {gdprConsent && (
                    <svg className="w-3 h-3 text-black" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
                    </svg>
                  )}
                </div>
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
          {message && <p className="text-[#00FF88] text-sm">{message}</p>}

          <button
            onClick={mode === 'login' ? handleLogin : handleRegister}
            disabled={loading}
            className="w-full bg-[#00FF88] text-black font-bold py-3.5 rounded-xl hover:brightness-110 disabled:opacity-50 transition-all active:scale-[0.97]"
            style={{ boxShadow: '0 0 20px rgba(0,255,136,0.2)' }}
          >
            {loading ? '...' : mode === 'login' ? 'Zaloguj się' : 'Zarejestruj się'}
          </button>
        </div>

        <p className="text-zinc-600 text-xs text-center mt-6">
          <Link href="/" className="hover:text-zinc-400 transition-colors">← Wróć na stronę główną</Link>
        </p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
