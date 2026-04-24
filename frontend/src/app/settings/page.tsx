'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { getValidToken } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const CEL_OPTIONS = [
  { value: 'masa', label: 'Budowa masy' },
  { value: 'redukcja', label: 'Redukcja' },
  { value: 'sila', label: 'Siła' },
  { value: 'kondycja', label: 'Kondycja' },
]

const inputCls = 'w-full bg-[#111111] border border-[#2A2A2A] rounded-xl px-3 py-2.5 text-[#F2EEE8] text-sm focus:outline-none focus:border-[#00FF88] transition-colors'

export default function SettingsPage() {
  const router = useRouter()

  const [waga, setWaga] = useState('')
  const [cel, setCel] = useState('')
  const [profileStatus, setProfileStatus] = useState<'idle' | 'saving' | 'ok' | 'error'>('idle')
  const [profileMsg, setProfileMsg] = useState('')

  const [email, setEmail] = useState('')
  const [emailStatus, setEmailStatus] = useState<'idle' | 'saving' | 'ok' | 'error'>('idle')
  const [emailMsg, setEmailMsg] = useState('')

  const [password, setPassword] = useState('')
  const [passwordStatus, setPasswordStatus] = useState<'idle' | 'saving' | 'ok' | 'error'>('idle')
  const [passwordMsg, setPasswordMsg] = useState('')

  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleteStatus, setDeleteStatus] = useState<'idle' | 'saving' | 'error'>('idle')
  const [deleteMsg, setDeleteMsg] = useState('')

  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const token = await getValidToken()
      if (!token) {
        router.replace('/')
        return
      }
      try {
        const res = await fetch(`${API_URL}/settings/profile`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const data = await res.json()
          setWaga(String(data.waga ?? ''))
          setCel(data.cel ?? '')
        }
      } catch {
        // ignoruj
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [router])

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault()
    setProfileStatus('saving')
    setProfileMsg('')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }

    const body: { waga?: number; cel?: string } = {}
    if (waga) body.waga = parseFloat(waga)
    if (cel) body.cel = cel

    try {
      const res = await fetch(`${API_URL}/settings/profile`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (res.ok) {
        setProfileStatus('ok')
        setProfileMsg('Zapisano.')
      } else {
        setProfileStatus('error')
        setProfileMsg(data.detail ?? 'Błąd zapisu')
      }
    } catch {
      setProfileStatus('error')
      setProfileMsg('Błąd połączenia')
    }
  }

  async function saveEmail(e: React.FormEvent) {
    e.preventDefault()
    setEmailStatus('saving')
    setEmailMsg('')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }

    try {
      const res = await fetch(`${API_URL}/settings/email`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const data = await res.json()
      if (res.ok) {
        setEmailStatus('ok')
        setEmailMsg('Email zaktualizowany.')
        setEmail('')
      } else {
        setEmailStatus('error')
        setEmailMsg(data.detail ?? 'Błąd zmiany emaila')
      }
    } catch {
      setEmailStatus('error')
      setEmailMsg('Błąd połączenia')
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault()
    setPasswordStatus('saving')
    setPasswordMsg('')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }

    try {
      const res = await fetch(`${API_URL}/settings/password`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      const data = await res.json()
      if (res.ok) {
        setPasswordStatus('ok')
        setPasswordMsg('Hasło zmienione.')
        setPassword('')
      } else {
        setPasswordStatus('error')
        setPasswordMsg(data.detail ?? 'Błąd zmiany hasła')
      }
    } catch {
      setPasswordStatus('error')
      setPasswordMsg('Błąd połączenia')
    }
  }

  async function deleteAccount() {
    setDeleteStatus('saving')
    setDeleteMsg('')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }

    try {
      const res = await fetch(`${API_URL}/settings/account`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        localStorage.removeItem('bezp_token')
        localStorage.removeItem('bezp_refresh_token')
        router.replace('/')
      } else {
        const data = await res.json()
        setDeleteStatus('error')
        setDeleteMsg(data.detail ?? 'Błąd usuwania konta')
      }
    } catch {
      setDeleteStatus('error')
      setDeleteMsg('Błąd połączenia')
    }
  }

  function handleLogout() {
    const token = localStorage.getItem('bezp_token')
    if (token) {
      navigator.sendBeacon(
        `${API_URL}/chat/session-end`,
        new Blob([JSON.stringify({ token })], { type: 'application/json' })
      )
    }
    localStorage.removeItem('bezp_token')
    localStorage.removeItem('bezp_refresh_token')
    router.replace('/')
  }

  if (loading) {
    return (
      <div className="h-[100dvh] bg-[#0D0D0D] flex items-center justify-center">
        <p className="text-zinc-500 text-sm">Ładuję ustawienia...</p>
      </div>
    )
  }

  return (
    <div className="h-[100dvh] bg-[#0D0D0D] flex flex-col overflow-hidden">

      {/* Header */}
      <header className="border-b border-[#1A1A1A] px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-[#00FF88] flex items-center justify-center font-bold text-black text-sm shrink-0">
            P
          </div>
          <div>
            <p className="text-white font-semibold text-sm leading-none mb-1">Pitbul</p>
            <p className="text-[#00FF88] text-xs">● online 24/7</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <nav className="flex gap-1 bg-[#111111] border border-[#2A2A2A] rounded-lg p-1">
            <Link href="/chat" className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors">
              Chat
            </Link>
            <Link href="/plan" className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors">
              Plan
            </Link>
            <span className="px-3 py-1.5 text-xs rounded-md bg-[#00FF88] text-black font-bold">
              Ustawienia
            </span>
          </nav>
          <button
            onClick={handleLogout}
            className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors"
          >
            Wyloguj
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 max-w-lg mx-auto w-full space-y-8">

        {/* Profil treningowy */}
        <section>
          <h2 className="text-[#00FF88] font-semibold mb-4 text-sm uppercase tracking-wide">Profil treningowy</h2>
          <form onSubmit={saveProfile} className="space-y-3">
            <div>
              <label className="block text-zinc-400 text-xs mb-1.5">Waga (kg)</label>
              <input
                type="number"
                min={30}
                max={300}
                step={0.1}
                value={waga}
                onChange={e => setWaga(e.target.value)}
                className={inputCls}
                placeholder="np. 82.5"
              />
            </div>
            <div>
              <label className="block text-zinc-400 text-xs mb-1.5">Cel treningowy</label>
              <select
                value={cel}
                onChange={e => setCel(e.target.value)}
                className={inputCls}
              >
                {CEL_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={profileStatus === 'saving'}
                className="bg-[#00FF88] text-black text-sm font-bold px-5 py-2.5 rounded-xl hover:brightness-110 transition-all disabled:opacity-50 active:scale-[0.97]"
              >
                {profileStatus === 'saving' ? 'Zapisuję...' : 'Zapisz'}
              </button>
              {profileMsg && (
                <span className={`text-sm ${profileStatus === 'ok' ? 'text-[#00FF88]' : 'text-red-400'}`}>
                  {profileMsg}
                </span>
              )}
            </div>
          </form>
        </section>

        <div className="border-t border-[#1A1A1A]" />

        {/* Email */}
        <section>
          <h2 className="text-[#00FF88] font-semibold mb-4 text-sm uppercase tracking-wide">Zmiana emaila</h2>
          <form onSubmit={saveEmail} className="space-y-3">
            <div>
              <label className="block text-zinc-400 text-xs mb-1.5">Nowy email</label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                className={inputCls}
                placeholder="nowy@email.com"
              />
            </div>
            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={emailStatus === 'saving'}
                className="bg-[#00FF88] text-black text-sm font-bold px-5 py-2.5 rounded-xl hover:brightness-110 transition-all disabled:opacity-50 active:scale-[0.97]"
              >
                {emailStatus === 'saving' ? 'Zmieniam...' : 'Zmień email'}
              </button>
              {emailMsg && (
                <span className={`text-sm ${emailStatus === 'ok' ? 'text-[#00FF88]' : 'text-red-400'}`}>
                  {emailMsg}
                </span>
              )}
            </div>
          </form>
        </section>

        <div className="border-t border-[#1A1A1A]" />

        {/* Hasło */}
        <section>
          <h2 className="text-[#00FF88] font-semibold mb-4 text-sm uppercase tracking-wide">Zmiana hasła</h2>
          <form onSubmit={savePassword} className="space-y-3">
            <div>
              <label className="block text-zinc-400 text-xs mb-1.5">Nowe hasło</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className={inputCls}
                placeholder="min. 8 znaków"
              />
            </div>
            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={passwordStatus === 'saving'}
                className="bg-[#00FF88] text-black text-sm font-bold px-5 py-2.5 rounded-xl hover:brightness-110 transition-all disabled:opacity-50 active:scale-[0.97]"
              >
                {passwordStatus === 'saving' ? 'Zmieniam...' : 'Zmień hasło'}
              </button>
              {passwordMsg && (
                <span className={`text-sm ${passwordStatus === 'ok' ? 'text-[#00FF88]' : 'text-red-400'}`}>
                  {passwordMsg}
                </span>
              )}
            </div>
          </form>
        </section>

        <div className="border-t border-[#1A1A1A]" />

        {/* Usuń konto */}
        <section className="pb-8">
          <h2 className="text-red-500 font-semibold mb-2 text-sm uppercase tracking-wide">Usuń konto</h2>
          <p className="text-zinc-500 text-sm mb-4">
            Spowoduje trwałe usunięcie konta i wszystkich danych. Operacja jest nieodwracalna.
          </p>
          {deleteConfirm !== 'USUŃ' ? (
            <div className="space-y-3">
              <p className="text-zinc-400 text-sm">Wpisz <span className="text-white font-mono">USUŃ</span> żeby potwierdzić:</p>
              <input
                type="text"
                value={deleteConfirm}
                onChange={e => setDeleteConfirm(e.target.value)}
                className={inputCls}
                placeholder="USUŃ"
              />
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-red-400 text-sm">Jesteś pewny? Tej operacji nie można cofnąć.</p>
              <div className="flex gap-3">
                <button
                  onClick={deleteAccount}
                  disabled={deleteStatus === 'saving'}
                  className="bg-red-600 text-white text-sm font-bold px-4 py-2.5 rounded-xl hover:bg-red-500 transition-colors disabled:opacity-50"
                >
                  {deleteStatus === 'saving' ? 'Usuwam...' : 'Tak, usuń konto'}
                </button>
                <button
                  onClick={() => setDeleteConfirm('')}
                  className="text-zinc-400 text-sm hover:text-white transition-colors px-4 py-2"
                >
                  Anuluj
                </button>
              </div>
              {deleteMsg && <p className="text-red-400 text-sm">{deleteMsg}</p>}
            </div>
          )}
        </section>

      </div>
    </div>
  )
}
