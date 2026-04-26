'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { getValidToken } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Stałe / mapy wartości ──────────────────────────────────────────────────

const CEL_MAP: Record<string, string> = {
  masa: 'Budowa masy', redukcja: 'Redukcja', sila: 'Siła', kondycja: 'Kondycja i zdrowie',
}
const PLEC_MAP: Record<string, string> = {
  mezczyzna: 'Mężczyzna', kobieta: 'Kobieta',
}
const POZIOM_MAP: Record<string, string> = {
  poczatkujacy: 'Początkujący', srednio: 'Średniozaawansowany', zaawansowany: 'Zaawansowany',
}
const CZAS_MAP: Record<string, string> = {
  '30-45': '30–45 min', '45-60': '45–60 min', '60-90': '60–90 min', '90+': 'Ponad 90 min',
}
const MIEJSCE_MAP: Record<string, string> = {
  silownia: 'Siłownia', dom: 'Dom / siłownia domowa', mieszanko: 'Mieszanko',
}
const SEN_MAP: Record<string, string> = {
  swietnie: 'Świetnie (8+ h)', dobrze: 'Dobrze (7–8 h)', srednio: 'Średnio (5–7 h)', slabo: 'Słabo',
}
const AKTYWNOSC_MAP: Record<string, string> = {
  siedzaca: 'Siedząca', umiarkowana: 'Umiarkowana', aktywna: 'Aktywna',
}
const STRES_MAP: Record<string, string> = {
  niski: 'Niski', umiarkowany: 'Umiarkowany', wysoki: 'Wysoki', bardzo_wysoki: 'Bardzo wysoki',
}
const DIETA_MAP: Record<string, string> = {
  nie_pilnuje: 'Nie pilnuję', staram_sie: 'Staram się', pilnuje: 'Pilnuję', specjalna: 'Dieta specjalna',
}
const SPRZET_MAP: Record<string, string> = {
  sztanga: 'Sztanga + obciążenia', hantle: 'Hantle',
  lawka_pozioma: 'Ławka pozioma', lawka_skosna: 'Ławka skośna',
  maszyny: 'Maszyny', wyciag: 'Wyciąg (kablowy)',
  kettlebell: 'Kettlebell', drazek: 'Drążek', gumy: 'Gumy oporowe', brak: 'Własna masa ciała',
}

const SPRZET_OPTIONS = Object.entries(SPRZET_MAP).map(([value, label]) => ({ value, label }))

// ── Typy ──────────────────────────────────────────────────────────────────

interface Profile {
  imie?: string; nazwisko?: string; email?: string
  wiek?: number; plec?: string; wzrost?: number; waga?: number
  poziom?: string; cel?: string; dni_treningowe?: number
  czas_treningu?: string; miejsce_treningu?: string; dostepny_sprzet?: string[]
  kontuzje?: string | null; ograniczenia?: string | null
  jakosc_snu?: string; aktywnosc_codzienna?: string
  poziom_stresu?: string; dieta?: string
  osiagniecia?: string | null; notatki_quiz?: string | null
}

// ── Pomocnicze komponenty ──────────────────────────────────────────────────

const inputCls = 'w-full bg-[#111111] border border-[#2A2A2A] rounded-xl px-3 py-3 text-[#F2EEE8] text-sm focus:outline-none focus:border-[#00FF88] transition-colors'
const textareaCls = inputCls + ' resize-none h-28'

function CardOption({ value, label, selected, onSelect, sub }: {
  value: string; label: string; selected: boolean
  onSelect: (v: string) => void; sub?: string
}) {
  return (
    <button type="button" onClick={() => onSelect(value)}
      className={`w-full text-left px-4 py-3.5 rounded-xl border transition-all active:scale-[0.98] ${
        selected
          ? 'border-[#00FF88] bg-[#00FF88]/10 text-white'
          : 'border-[#2A2A2A] bg-[#111111] text-zinc-300 hover:border-zinc-500'
      }`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <span className="font-medium text-sm block">{label}</span>
          {sub && <span className="text-xs text-zinc-500 mt-0.5 block">{sub}</span>}
        </div>
        {selected && <span className="text-[#00FF88] text-sm font-bold shrink-0">✓</span>}
      </div>
    </button>
  )
}

function CheckOption({ value, label, checked, onToggle }: {
  value: string; label: string; checked: boolean; onToggle: (v: string) => void
}) {
  return (
    <label onClick={() => onToggle(value)}
      className={`flex items-center gap-3 px-4 py-3.5 rounded-xl border cursor-pointer transition-all active:scale-[0.98] ${
        checked ? 'border-[#00FF88] bg-[#00FF88]/10' : 'border-[#2A2A2A] bg-[#111111] hover:border-zinc-500'
      }`}>
      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
        checked ? 'bg-[#00FF88] border-[#00FF88]' : 'border-zinc-600'
      }`}>
        {checked && (
          <svg className="w-3 h-3 text-black" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
          </svg>
        )}
      </div>
      <span className="text-sm text-zinc-300">{label}</span>
    </label>
  )
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg className={`w-4 h-4 text-zinc-500 shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  )
}

// Wiersz akordeonu — nagłówek + opcjonalna zawartość
function AccordionItem({
  id, label, preview, open, onToggle, children, danger,
}: {
  id: string; label: string; preview?: string; open: boolean
  onToggle: (id: string) => void; children: React.ReactNode; danger?: boolean
}) {
  return (
    <div className={`rounded-xl border ${danger ? 'border-red-900/60' : 'border-[#1A1A1A]'} overflow-hidden`}>
      <button
        type="button"
        onClick={() => onToggle(id)}
        className={`w-full flex items-center justify-between px-4 py-3.5 gap-3 transition-colors ${
          open ? 'bg-[#141414]' : 'bg-[#0F0F0F] hover:bg-[#131313]'
        }`}
      >
        <span className={`text-sm font-medium ${danger ? 'text-red-400' : 'text-white'}`}>{label}</span>
        <div className="flex items-center gap-2 min-w-0">
          {preview && !open && (
            <span className="text-xs text-zinc-500 truncate max-w-[120px]">{preview}</span>
          )}
          <Chevron open={open} />
        </div>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-2 bg-[#0F0F0F] border-t border-[#1A1A1A]">
          {children}
        </div>
      )}
    </div>
  )
}

// Przycisk Zapisz + komunikat statusu
function SaveBar({
  status, msg, onSave, saveLabel = 'Zapisz',
  cancelLabel, onCancel,
}: {
  status: 'idle' | 'saving' | 'ok' | 'error'
  msg?: string; onSave?: () => void; saveLabel?: string
  cancelLabel?: string; onCancel?: () => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 pt-2">
      {onSave && (
        <button
          type="button"
          onClick={onSave}
          disabled={status === 'saving'}
          className="bg-[#00FF88] text-black text-sm font-bold px-5 py-2.5 rounded-xl hover:brightness-110 transition-all disabled:opacity-50 active:scale-[0.97]"
        >
          {status === 'saving' ? 'Zapisuję...' : saveLabel}
        </button>
      )}
      {onCancel && (
        <button type="button" onClick={onCancel}
          className="text-zinc-500 hover:text-zinc-300 text-sm transition-colors px-2 py-2.5">
          {cancelLabel ?? 'Anuluj'}
        </button>
      )}
      {msg && (
        <span className={`text-sm ${status === 'ok' ? 'text-[#00FF88]' : 'text-red-400'}`}>{msg}</span>
      )}
    </div>
  )
}

// ── Główny komponent ───────────────────────────────────────────────────────

export default function SettingsPage() {
  const router = useRouter()

  const [profile, setProfile] = useState<Profile>({})
  const [loading, setLoading] = useState(true)
  const [openId, setOpenId] = useState<string | null>(null)

  // Lokalne stany pól (wypełniane z profilu po załadowaniu)
  const [waga, setWaga] = useState('')
  const [wzrost, setWzrost] = useState('')
  const [wiek, setWiek] = useState('')
  const [plec, setPlec] = useState('')
  const [cel, setCel] = useState('')
  const [poziom, setPoziom] = useState('')
  const [dni, setDni] = useState('')
  const [czas, setCzas] = useState('')
  const [miejsce, setMiejsce] = useState('')
  const [sprzet, setSprzet] = useState<string[]>([])
  const [kontuzje, setKontuzje] = useState('')
  const [hasKontuzje, setHasKontuzje] = useState('')
  const [ograniczenia, setOgraniczenia] = useState('')
  const [hasOgraniczenia, setHasOgraniczenia] = useState('')
  const [sen, setSen] = useState('')
  const [aktywnosc, setAktywnosc] = useState('')
  const [stres, setStres] = useState('')
  const [dieta, setDieta] = useState('')
  const [osiagniecia, setOsiagniecia] = useState('')
  const [notatki, setNotatki] = useState('')

  // Stany konta
  const [emailCurrent, setEmailCurrent] = useState('')
  const [emailNew, setEmailNew] = useState('')
  const [oldPass, setOldPass] = useState('')
  const [newPass, setNewPass] = useState('')
  const [deletePwd, setDeletePwd] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState('')

  // Statusy sekcji
  type S = 'idle' | 'saving' | 'ok' | 'error'
  const [st, setSt] = useState<Record<string, S>>({})
  const [msg, setMsg] = useState<Record<string, string>>({})

  function setStatus(id: string, status: S, message = '') {
    setSt(p => ({ ...p, [id]: status }))
    setMsg(p => ({ ...p, [id]: message }))
  }

  const initFromProfile = useCallback((p: Profile) => {
    setWaga(String(p.waga ?? ''))
    setWzrost(String(p.wzrost ?? ''))
    setWiek(String(p.wiek ?? ''))
    setPlec(p.plec ?? '')
    setCel(p.cel ?? '')
    setPoziom(p.poziom ?? '')
    setDni(String(p.dni_treningowe ?? ''))
    setCzas(p.czas_treningu ?? '')
    setMiejsce(p.miejsce_treningu ?? '')
    setSprzet(p.dostepny_sprzet ?? [])
    const k = p.kontuzje ?? ''
    setHasKontuzje(k ? 'tak' : p.kontuzje === null ? 'nie' : '')
    setKontuzje(k)
    const o = p.ograniczenia ?? ''
    setHasOgraniczenia(o ? 'tak' : p.ograniczenia === null ? 'nie' : '')
    setOgraniczenia(o)
    setSen(p.jakosc_snu ?? '')
    setAktywnosc(p.aktywnosc_codzienna ?? '')
    setStres(p.poziom_stresu ?? '')
    setDieta(p.dieta ?? '')
    setOsiagniecia(p.osiagniecia ?? '')
    setNotatki(p.notatki_quiz ?? '')
  }, [])

  useEffect(() => {
    async function load() {
      const token = await getValidToken()
      if (!token) { router.replace('/'); return }
      try {
        const res = await fetch(`${API_URL}/settings/profile`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const data: Profile = await res.json()
          setProfile(data)
          initFromProfile(data)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [router, initFromProfile])

  function toggle(id: string) {
    setOpenId(prev => prev === id ? null : id)
    // Czyść status po zamknięciu
    if (openId === id) setStatus(id, 'idle')
  }

  async function patchProfile(id: string, body: object) {
    setStatus(id, 'saving')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }
    try {
      const res = await fetch(`${API_URL}/settings/profile`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (res.ok) {
        setStatus(id, 'ok', 'Zapisano')
        // Odśwież profil i zamknij po chwili
        const fresh = await fetch(`${API_URL}/settings/profile`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (fresh.ok) {
          const p: Profile = await fresh.json()
          setProfile(p)
          initFromProfile(p)
        }
        setTimeout(() => setOpenId(null), 900)
      } else {
        setStatus(id, 'error', data.detail ?? 'Błąd zapisu')
      }
    } catch {
      setStatus(id, 'error', 'Błąd połączenia')
    }
  }

  function toggleSprzet(value: string) {
    setSprzet(prev => {
      if (value === 'brak') return prev.includes('brak') ? [] : ['brak']
      const bez = prev.filter(s => s !== 'brak')
      return bez.includes(value) ? bez.filter(s => s !== value) : [...bez, value]
    })
  }

  async function saveEmail() {
    if (!emailNew || !emailCurrent) {
      setStatus('email', 'error', 'Uzupełnij oba pola'); return
    }
    setStatus('email', 'saving')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }
    try {
      const res = await fetch(`${API_URL}/settings/email`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: emailCurrent, email: emailNew }),
      })
      const data = await res.json()
      if (res.ok) {
        setStatus('email', 'ok', data.message ?? 'Email zaktualizowany')
        setEmailNew(''); setEmailCurrent('')
        setTimeout(() => setOpenId(null), 1200)
      } else {
        setStatus('email', 'error', data.detail ?? 'Błąd')
      }
    } catch {
      setStatus('email', 'error', 'Błąd połączenia')
    }
  }

  async function savePassword() {
    if (!oldPass || !newPass) {
      setStatus('password', 'error', 'Uzupełnij oba pola'); return
    }
    if (newPass.length < 8) {
      setStatus('password', 'error', 'Nowe hasło musi mieć min. 8 znaków'); return
    }
    setStatus('password', 'saving')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }
    try {
      const res = await fetch(`${API_URL}/settings/password`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldPass, new_password: newPass }),
      })
      const data = await res.json()
      if (res.ok) {
        setStatus('password', 'ok', 'Hasło zmienione')
        setOldPass(''); setNewPass('')
        setTimeout(() => setOpenId(null), 900)
      } else {
        setStatus('password', 'error', data.detail ?? 'Błąd')
      }
    } catch {
      setStatus('password', 'error', 'Błąd połączenia')
    }
  }

  async function deleteAccount() {
    if (!deletePwd) {
      setStatus('delete', 'error', 'Podaj hasło'); return
    }
    if (deleteConfirm !== 'USUŃ') {
      setStatus('delete', 'error', 'Wpisz USUŃ żeby potwierdzić'); return
    }
    setStatus('delete', 'saving')
    const token = await getValidToken()
    if (!token) { router.replace('/'); return }
    try {
      const res = await fetch(`${API_URL}/settings/account`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: deletePwd }),
      })
      if (res.ok) {
        localStorage.removeItem('bezp_token')
        localStorage.removeItem('bezp_refresh_token')
        router.replace('/')
      } else {
        const data = await res.json()
        setStatus('delete', 'error', data.detail ?? 'Błąd usuwania konta')
      }
    } catch {
      setStatus('delete', 'error', 'Błąd połączenia')
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

  // ── Podglądy wartości w nagłówkach ────────────────────────────────────────

  const previews: Record<string, string> = {
    dane:        `${profile.imie ?? ''}${profile.imie && profile.plec ? ' · ' : ''}${PLEC_MAP[profile.plec ?? ''] ?? ''}`,
    wiek_wzrost: [profile.wiek ? `${profile.wiek} lat` : '', profile.wzrost ? `${profile.wzrost} cm` : ''].filter(Boolean).join(', '),
    waga:        profile.waga ? `${profile.waga} kg` : '—',
    cel:         CEL_MAP[profile.cel ?? ''] ?? '—',
    poziom:      POZIOM_MAP[profile.poziom ?? ''] ?? '—',
    dni:         profile.dni_treningowe ? `${profile.dni_treningowe} dni/tydz.` : '—',
    czas:        CZAS_MAP[profile.czas_treningu ?? ''] ?? '—',
    miejsce:     MIEJSCE_MAP[profile.miejsce_treningu ?? ''] ?? '—',
    sprzet:      profile.dostepny_sprzet?.length
      ? profile.dostepny_sprzet.slice(0, 2).map(s => SPRZET_MAP[s] ?? s).join(', ') +
        (profile.dostepny_sprzet.length > 2 ? ` +${profile.dostepny_sprzet.length - 2}` : '')
      : '—',
    kontuzje:    profile.kontuzje ? (profile.kontuzje.length > 35 ? profile.kontuzje.slice(0, 35) + '…' : profile.kontuzje) : 'Brak',
    ograniczenia:profile.ograniczenia ? (profile.ograniczenia.length > 35 ? profile.ograniczenia.slice(0, 35) + '…' : profile.ograniczenia) : 'Brak',
    sen:         SEN_MAP[profile.jakosc_snu ?? ''] ?? '—',
    aktywnosc:   AKTYWNOSC_MAP[profile.aktywnosc_codzienna ?? ''] ?? '—',
    stres:       STRES_MAP[profile.poziom_stresu ?? ''] ?? '—',
    dieta:       DIETA_MAP[profile.dieta ?? ''] ?? '—',
    osiagniecia: profile.osiagniecia ? (profile.osiagniecia.length > 35 ? profile.osiagniecia.slice(0, 35) + '…' : profile.osiagniecia) : '—',
    notatki:     profile.notatki_quiz ? (profile.notatki_quiz.length > 35 ? profile.notatki_quiz.slice(0, 35) + '…' : profile.notatki_quiz) : '—',
  }

  const o = openId

  return (
    <div className="h-[100dvh] bg-[#0D0D0D] flex flex-col overflow-hidden">

      {/* Header */}
      <header className="border-b border-[#1A1A1A] px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-[#00FF88] flex items-center justify-center font-bold text-black text-sm shrink-0">P</div>
          <div>
            <p className="text-white font-semibold text-sm leading-none mb-1">Pitbul</p>
            <p className="text-[#00FF88] text-xs">● online 24/7</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <nav className="flex gap-1 bg-[#111111] border border-[#2A2A2A] rounded-lg p-1">
            <Link href="/chat" className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors">Chat</Link>
            <Link href="/plan" className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors">Plan</Link>
            <span className="px-3 py-1.5 text-xs rounded-md bg-[#00FF88] text-black font-bold">Ustawienia</span>
          </nav>
          <button onClick={handleLogout} className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors">Wyloguj</button>
        </div>
      </header>

      {/* Scrollowalny content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-lg mx-auto w-full px-4 py-5 space-y-6 pb-12">

          {/* ─── Informacje o Tobie ─────────────────────────────────── */}
          <section>
            <div className="mb-1">
              <h2 className="text-white font-bold text-base">Informacje o Tobie</h2>
              <p className="text-zinc-600 text-xs mt-0.5">Dane które Pitbul zna — kliknij żeby edytować</p>
            </div>

            {/* Statyczna pigułka z imieniem i emailem */}
            <div className="flex items-center gap-3 py-3.5 px-4 bg-[#0F0F0F] border border-[#1A1A1A] rounded-xl mb-2 mt-3">
              <div className="w-9 h-9 rounded-full bg-[#1A1A1A] flex items-center justify-center text-sm font-bold text-[#00FF88] shrink-0">
                {(profile.imie ?? '?')[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-white text-sm font-medium truncate">
                  {profile.imie} {profile.nazwisko}
                </p>
                <p className="text-zinc-500 text-xs truncate">{profile.email ?? '—'}</p>
              </div>
            </div>

            <div className="space-y-1.5">

              {/* Wiek i płeć */}
              <AccordionItem id="wiek_wzrost" label="Wiek, wzrost i płeć"
                preview={previews.wiek_wzrost + (previews.wiek_wzrost && PLEC_MAP[profile.plec ?? ''] ? ' · ' + PLEC_MAP[profile.plec ?? ''] : '')}
                open={o === 'wiek_wzrost'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-zinc-500 text-xs mb-1.5">Wiek</label>
                      <input type="number" min={12} max={100} value={wiek}
                        onChange={e => setWiek(e.target.value)} className={inputCls} placeholder="np. 25" />
                    </div>
                    <div>
                      <label className="block text-zinc-500 text-xs mb-1.5">Wzrost (cm)</label>
                      <input type="number" min={100} max={250} value={wzrost}
                        onChange={e => setWzrost(e.target.value)} className={inputCls} placeholder="np. 178" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-zinc-500 text-xs mb-1.5">Płeć</label>
                    <div className="flex gap-2">
                      {[{ v: 'mezczyzna', l: 'Mężczyzna' }, { v: 'kobieta', l: 'Kobieta' }].map(({ v, l }) => (
                        <button key={v} type="button" onClick={() => setPlec(v)}
                          className={`flex-1 py-3 rounded-xl border text-sm font-medium transition-all active:scale-[0.98] ${
                            plec === v ? 'border-[#00FF88] bg-[#00FF88]/10 text-white' : 'border-[#2A2A2A] bg-[#111111] text-zinc-400'
                          }`}>{l}</button>
                      ))}
                    </div>
                  </div>
                  <SaveBar status={st['wiek_wzrost'] ?? 'idle'} msg={msg['wiek_wzrost']}
                    onSave={() => patchProfile('wiek_wzrost', {
                      wiek: wiek ? parseInt(wiek) : undefined,
                      wzrost: wzrost ? parseInt(wzrost) : undefined,
                      plec: plec || undefined,
                    })} />
                </div>
              </AccordionItem>

              {/* Waga */}
              <AccordionItem id="waga" label="Aktualna waga" preview={previews.waga}
                open={o === 'waga'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <input type="number" min={30} max={300} step={0.1} value={waga}
                    onChange={e => setWaga(e.target.value)} className={inputCls} placeholder="np. 82.5 kg" />
                  <p className="text-zinc-600 text-xs">Pitbul może też zaktualizować wagę automatycznie gdy wspomnisz o niej w rozmowie.</p>
                  <SaveBar status={st['waga'] ?? 'idle'} msg={msg['waga']}
                    onSave={() => patchProfile('waga', { waga: parseFloat(waga) })} />
                </div>
              </AccordionItem>

              {/* Cel */}
              <AccordionItem id="cel" label="Cel treningowy" preview={previews.cel}
                open={o === 'cel'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: 'masa',     l: 'Budowa masy',       s: 'Większy, mocniejszy, przybrać na wadze' },
                    { v: 'redukcja', l: 'Redukcja',           s: 'Schudnąć, zachowując mięśnie' },
                    { v: 'sila',     l: 'Siła',               s: 'Podnosić coraz więcej' },
                    { v: 'kondycja', l: 'Kondycja i zdrowie', s: 'Sprawność, energia, zdrowie' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={cel === v} onSelect={setCel} />
                  ))}
                  <SaveBar status={st['cel'] ?? 'idle'} msg={msg['cel']}
                    onSave={() => patchProfile('cel', { cel })} />
                </div>
              </AccordionItem>

              {/* Poziom */}
              <AccordionItem id="poziom" label="Poziom zaawansowania" preview={previews.poziom}
                open={o === 'poziom'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: 'poczatkujacy', l: 'Początkujący',        s: 'Mniej niż rok treningu' },
                    { v: 'srednio',      l: 'Średniozaawansowany', s: '1–3 lata regularnego treningu' },
                    { v: 'zaawansowany', l: 'Zaawansowany',         s: 'Ponad 3 lata, świadoma progresja' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={poziom === v} onSelect={setPoziom} />
                  ))}
                  <SaveBar status={st['poziom'] ?? 'idle'} msg={msg['poziom']}
                    onSave={() => patchProfile('poziom', { poziom })} />
                </div>
              </AccordionItem>

              {/* Dni treningowe */}
              <AccordionItem id="dni" label="Ile dni trenujesz?" preview={previews.dni}
                open={o === 'dni'} onToggle={toggle}>
                <div className="pt-1 space-y-3">
                  <div className="grid grid-cols-5 gap-2">
                    {[2, 3, 4, 5, 6].map(n => (
                      <button key={n} type="button" onClick={() => setDni(String(n))}
                        className={`py-4 rounded-xl border text-base font-bold transition-all active:scale-[0.96] ${
                          dni === String(n)
                            ? 'border-[#00FF88] bg-[#00FF88]/10 text-[#00FF88]'
                            : 'border-[#2A2A2A] bg-[#111111] text-zinc-400 hover:border-zinc-500'
                        }`}>{n}</button>
                    ))}
                  </div>
                  <SaveBar status={st['dni'] ?? 'idle'} msg={msg['dni']}
                    onSave={() => patchProfile('dni', { dni_treningowe: parseInt(dni) })} />
                </div>
              </AccordionItem>

              {/* Czas treningu */}
              <AccordionItem id="czas" label="Czas na jeden trening" preview={previews.czas}
                open={o === 'czas'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: '30-45', l: '30–45 min',     s: 'Szybki i skupiony' },
                    { v: '45-60', l: '45–60 min',     s: 'Standardowy trening' },
                    { v: '60-90', l: '60–90 min',     s: 'Spokojniejsze tempo' },
                    { v: '90+',   l: 'Ponad 90 min',  s: 'Lubię długie treningi' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={czas === v} onSelect={setCzas} />
                  ))}
                  <SaveBar status={st['czas'] ?? 'idle'} msg={msg['czas']}
                    onSave={() => patchProfile('czas', { czas_treningu: czas })} />
                </div>
              </AccordionItem>

              {/* Miejsce */}
              <AccordionItem id="miejsce" label="Gdzie trenujesz?" preview={previews.miejsce}
                open={o === 'miejsce'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: 'silownia',  l: 'Siłownia',          s: 'Pełne wyposażenie' },
                    { v: 'dom',       l: 'Dom / siłownia dom.',s: 'Ograniczony sprzęt' },
                    { v: 'mieszanko', l: 'Mieszanko',          s: 'Część na siłowni, część w domu' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={miejsce === v} onSelect={setMiejsce} />
                  ))}
                  <SaveBar status={st['miejsce'] ?? 'idle'} msg={msg['miejsce']}
                    onSave={() => patchProfile('miejsce', { miejsce_treningu: miejsce })} />
                </div>
              </AccordionItem>

              {/* Sprzęt */}
              <AccordionItem id="sprzet" label="Dostępny sprzęt" preview={previews.sprzet}
                open={o === 'sprzet'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {SPRZET_OPTIONS.map(opt => (
                    <CheckOption key={opt.value} value={opt.value} label={opt.label}
                      checked={sprzet.includes(opt.value)} onToggle={toggleSprzet} />
                  ))}
                  <SaveBar status={st['sprzet'] ?? 'idle'} msg={msg['sprzet']}
                    onSave={() => patchProfile('sprzet', { dostepny_sprzet: sprzet })} />
                </div>
              </AccordionItem>

              {/* Kontuzje */}
              <AccordionItem id="kontuzje" label="Kontuzje i bóle" preview={previews.kontuzje}
                open={o === 'kontuzje'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <div className="flex gap-2">
                    {[{ v: 'nie', l: 'Nie mam' }, { v: 'tak', l: 'Mam kontuzje / bóle' }].map(({ v, l }) => (
                      <button key={v} type="button" onClick={() => setHasKontuzje(v)}
                        className={`flex-1 py-3 rounded-xl border text-sm font-medium transition-all active:scale-[0.98] ${
                          hasKontuzje === v ? 'border-[#00FF88] bg-[#00FF88]/10 text-white' : 'border-[#2A2A2A] bg-[#111111] text-zinc-400'
                        }`}>{l}</button>
                    ))}
                  </div>
                  {hasKontuzje === 'tak' && (
                    <div>
                      <label className="block text-zinc-500 text-xs mb-1.5">Co i gdzie? Im dokładniej, tym bezpieczniejszy plan</label>
                      <textarea value={kontuzje} onChange={e => setKontuzje(e.target.value)}
                        className={textareaCls} placeholder="np. ból lewego kolana przy przysiadach, bark prawy..." />
                    </div>
                  )}
                  <SaveBar status={st['kontuzje'] ?? 'idle'} msg={msg['kontuzje']}
                    onSave={() => {
                      if (hasKontuzje === 'tak' && !kontuzje.trim()) {
                        setStatus('kontuzje', 'error', 'Opisz kontuzję'); return
                      }
                      patchProfile('kontuzje', { kontuzje: hasKontuzje === 'tak' ? kontuzje.trim() : null })
                    }} />
                </div>
              </AccordionItem>

              {/* Ograniczenia */}
              <AccordionItem id="ograniczenia" label="Ograniczenia zdrowotne" preview={previews.ograniczenia}
                open={o === 'ograniczenia'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <p className="text-zinc-600 text-xs">Nadciśnienie, dyskopatia, praca fizyczna — cokolwiek co powinno wpłynąć na plan.</p>
                  <div className="flex gap-2">
                    {[{ v: 'nie', l: 'Brak ograniczeń' }, { v: 'tak', l: 'Mam ograniczenia' }].map(({ v, l }) => (
                      <button key={v} type="button" onClick={() => setHasOgraniczenia(v)}
                        className={`flex-1 py-3 rounded-xl border text-sm font-medium transition-all active:scale-[0.98] ${
                          hasOgraniczenia === v ? 'border-[#00FF88] bg-[#00FF88]/10 text-white' : 'border-[#2A2A2A] bg-[#111111] text-zinc-400'
                        }`}>{l}</button>
                    ))}
                  </div>
                  {hasOgraniczenia === 'tak' && (
                    <div>
                      <label className="block text-zinc-500 text-xs mb-1.5">Opisz — im dokładniej, tym bezpieczniejszy plan</label>
                      <textarea value={ograniczenia} onChange={e => setOgraniczenia(e.target.value)}
                        className={textareaCls} placeholder="np. dyskopatia L4/L5, nadciśnienie..." />
                    </div>
                  )}
                  <SaveBar status={st['ograniczenia'] ?? 'idle'} msg={msg['ograniczenia']}
                    onSave={() => {
                      if (hasOgraniczenia === 'tak' && !ograniczenia.trim()) {
                        setStatus('ograniczenia', 'error', 'Opisz ograniczenia'); return
                      }
                      patchProfile('ograniczenia', { ograniczenia: hasOgraniczenia === 'tak' ? ograniczenia.trim() : null })
                    }} />
                </div>
              </AccordionItem>

              {/* Sen */}
              <AccordionItem id="sen" label="Jakość snu" preview={previews.sen}
                open={o === 'sen'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: 'swietnie', l: 'Świetnie',  s: '8+ godz., budzę się wypoczęty' },
                    { v: 'dobrze',   l: 'Dobrze',    s: '7–8 godz., bez większych problemów' },
                    { v: 'srednio',  l: 'Średnio',   s: '5–7 godz., bywa różnie' },
                    { v: 'slabo',    l: 'Słabo',     s: 'Mało snu, wyraźnie odczuwam niedobór' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={sen === v} onSelect={setSen} />
                  ))}
                  <SaveBar status={st['sen'] ?? 'idle'} msg={msg['sen']}
                    onSave={() => patchProfile('sen', { jakosc_snu: sen })} />
                </div>
              </AccordionItem>

              {/* Aktywność */}
              <AccordionItem id="aktywnosc" label="Aktywność poza treningiem" preview={previews.aktywnosc}
                open={o === 'aktywnosc'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: 'siedzaca',    l: 'Siedząca',    s: 'Biuro, komputer, mało ruchu przez dzień' },
                    { v: 'umiarkowana', l: 'Umiarkowana', s: 'Sporo chodzę, mieszana praca' },
                    { v: 'aktywna',     l: 'Aktywna',     s: 'Praca fizyczna lub bardzo dużo ruchu' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={aktywnosc === v} onSelect={setAktywnosc} />
                  ))}
                  <SaveBar status={st['aktywnosc'] ?? 'idle'} msg={msg['aktywnosc']}
                    onSave={() => patchProfile('aktywnosc', { aktywnosc_codzienna: aktywnosc })} />
                </div>
              </AccordionItem>

              {/* Stres */}
              <AccordionItem id="stres" label="Poziom stresu" preview={previews.stres}
                open={o === 'stres'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: 'niski',        l: 'Niski',         s: 'Spokojnie, nic mnie nie gniecie' },
                    { v: 'umiarkowany',  l: 'Umiarkowany',   s: 'Bywa stresująco, ale daję radę' },
                    { v: 'wysoki',       l: 'Wysoki',        s: 'Dużo na głowie, trudno wyłączyć głowę' },
                    { v: 'bardzo_wysoki',l: 'Bardzo wysoki', s: 'Chroniczny stres, słabo się regeneruję' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={stres === v} onSelect={setStres} />
                  ))}
                  <SaveBar status={st['stres'] ?? 'idle'} msg={msg['stres']}
                    onSave={() => patchProfile('stres', { poziom_stresu: stres })} />
                </div>
              </AccordionItem>

              {/* Dieta */}
              <AccordionItem id="dieta" label="Odżywianie" preview={previews.dieta}
                open={o === 'dieta'} onToggle={toggle}>
                <div className="space-y-2 pt-1">
                  {[
                    { v: 'nie_pilnuje', l: 'Nie pilnuję',     s: 'Jem co popadnie' },
                    { v: 'staram_sie',  l: 'Staram się',      s: 'Staram się jeść zdrowo, nie liczę kalorii' },
                    { v: 'pilnuje',     l: 'Pilnuję',         s: 'Liczę kalorie lub makro' },
                    { v: 'specjalna',   l: 'Dieta specjalna', s: 'Weganizm, keto, IF lub inna' },
                  ].map(({ v, l, s }) => (
                    <CardOption key={v} value={v} label={l} sub={s} selected={dieta === v} onSelect={setDieta} />
                  ))}
                  <SaveBar status={st['dieta'] ?? 'idle'} msg={msg['dieta']}
                    onSave={() => patchProfile('dieta', { dieta })} />
                </div>
              </AccordionItem>

              {/* Osiągnięcia */}
              <AccordionItem id="osiagniecia" label="Wyniki i osiągnięcia" preview={previews.osiagniecia}
                open={o === 'osiagniecia'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <p className="text-zinc-600 text-xs">Opcjonalnie — pomaga Pitbulowi dobrać ciężary startowe i ocenić siłę bazową.</p>
                  <textarea value={osiagniecia} onChange={e => setOsiagniecia(e.target.value)}
                    className={textareaCls}
                    placeholder="np. Ławka: 80 kg × 5 powt., Przysiad: 100 kg, Martwy ciąg: 120 kg..." />
                  <SaveBar status={st['osiagniecia'] ?? 'idle'} msg={msg['osiagniecia']}
                    onSave={() => patchProfile('osiagniecia', { osiagniecia: osiagniecia.trim() || null })} />
                </div>
              </AccordionItem>

              {/* Notatki */}
              <AccordionItem id="notatki" label="Notatki" preview={previews.notatki}
                open={o === 'notatki'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <p className="text-zinc-600 text-xs">Cokolwiek co może mieć znaczenie — tryb życia, preferencje, plany.</p>
                  <textarea value={notatki} onChange={e => setNotatki(e.target.value)}
                    className={textareaCls}
                    placeholder="np. Pracuję na nocki, nie znoszę biegania, chcę startować w zawodach za rok..." />
                  <SaveBar status={st['notatki'] ?? 'idle'} msg={msg['notatki']}
                    onSave={() => patchProfile('notatki', { notatki_quiz: notatki.trim() || null })} />
                </div>
              </AccordionItem>

            </div>
          </section>

          {/* ─── Konto ─────────────────────────────────────────────── */}
          <section>
            <div className="mb-3">
              <h2 className="text-white font-bold text-base">Konto</h2>
            </div>

            <div className="space-y-1.5">

              {/* Zmiana emaila */}
              <AccordionItem id="email" label="Zmień adres email" open={o === 'email'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <p className="text-zinc-600 text-xs">Aby zmienić email musisz potwierdzić tożsamość aktualnym hasłem.</p>
                  <div>
                    <label className="block text-zinc-500 text-xs mb-1.5">Aktualne hasło</label>
                    <input type="password" value={emailCurrent} onChange={e => setEmailCurrent(e.target.value)}
                      className={inputCls} placeholder="••••••••" autoComplete="current-password" />
                  </div>
                  <div>
                    <label className="block text-zinc-500 text-xs mb-1.5">Nowy adres email</label>
                    <input type="email" value={emailNew} onChange={e => setEmailNew(e.target.value)}
                      className={inputCls} placeholder="nowy@email.com" autoComplete="email" />
                  </div>
                  <SaveBar status={st['email'] ?? 'idle'} msg={msg['email']}
                    saveLabel="Zmień email" onSave={saveEmail} />
                </div>
              </AccordionItem>

              {/* Zmiana hasła */}
              <AccordionItem id="password" label="Zmień hasło" open={o === 'password'} onToggle={toggle}>
                <div className="space-y-3 pt-1">
                  <div>
                    <label className="block text-zinc-500 text-xs mb-1.5">Obecne hasło</label>
                    <input type="password" value={oldPass} onChange={e => setOldPass(e.target.value)}
                      className={inputCls} placeholder="••••••••" autoComplete="current-password" />
                  </div>
                  <div>
                    <label className="block text-zinc-500 text-xs mb-1.5">Nowe hasło</label>
                    <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)}
                      className={inputCls} placeholder="min. 8 znaków" autoComplete="new-password" />
                  </div>
                  <SaveBar status={st['password'] ?? 'idle'} msg={msg['password']}
                    saveLabel="Zmień hasło" onSave={savePassword} />
                </div>
              </AccordionItem>

              {/* Usuń konto */}
              <AccordionItem id="delete" label="Usuń konto" open={o === 'delete'} onToggle={toggle} danger>
                <div className="space-y-3 pt-1">
                  <div className="bg-red-950/30 border border-red-900/40 rounded-xl px-4 py-3 space-y-1.5">
                    <p className="text-red-400 text-sm font-medium">Operacja nieodwracalna</p>
                    <p className="text-zinc-500 text-xs leading-relaxed">
                      Zostaną trwale usunięte: konto, profil, historia rozmów, wygenerowane plany
                      i wszystkie powiązane dane. Realizuje prawo do bycia zapomnianym (RODO art. 17).
                    </p>
                  </div>
                  <div>
                    <label className="block text-zinc-500 text-xs mb-1.5">Hasło do konta</label>
                    <input type="password" value={deletePwd} onChange={e => setDeletePwd(e.target.value)}
                      className={inputCls} placeholder="••••••••" autoComplete="current-password" />
                  </div>
                  <div>
                    <label className="block text-zinc-500 text-xs mb-1.5">
                      Wpisz <span className="font-mono text-white">USUŃ</span> żeby potwierdzić
                    </label>
                    <input type="text" value={deleteConfirm} onChange={e => setDeleteConfirm(e.target.value)}
                      className={inputCls} placeholder="USUŃ" />
                  </div>
                  <div className="flex flex-wrap items-center gap-3 pt-1">
                    <button
                      type="button"
                      onClick={deleteAccount}
                      disabled={st['delete'] === 'saving' || deleteConfirm !== 'USUŃ' || !deletePwd}
                      className="bg-red-600 text-white text-sm font-bold px-5 py-2.5 rounded-xl hover:bg-red-500 transition-colors disabled:opacity-40 active:scale-[0.97]"
                    >
                      {st['delete'] === 'saving' ? 'Usuwam...' : 'Tak, usuń moje konto'}
                    </button>
                    {msg['delete'] && (
                      <span className="text-red-400 text-sm">{msg['delete']}</span>
                    )}
                  </div>
                </div>
              </AccordionItem>

            </div>
          </section>

          {/* ─── RODO nota ─────────────────────────────────────────── */}
          <p className="text-zinc-700 text-xs text-center leading-relaxed pb-2">
            Administratorem Twoich danych jest właściciel serwisu. Szczegóły w{' '}
            <Link href="/privacy" className="text-zinc-500 hover:text-zinc-300 underline">polityce prywatności</Link>.
            Masz prawo do dostępu, sprostowania i usunięcia danych (art. 15–17 RODO).
          </p>

        </div>
      </div>
    </div>
  )
}
