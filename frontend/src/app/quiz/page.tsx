'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getValidToken } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const SPRZET_OPTIONS = [
  { value: 'sztanga',       label: 'Sztanga + obciążenia' },
  { value: 'hantle',        label: 'Hantle' },
  { value: 'lawka_pozioma', label: 'Ławka pozioma' },
  { value: 'lawka_skosna',  label: 'Ławka skośna' },
  { value: 'maszyny',       label: 'Maszyny' },
  { value: 'wyciag',        label: 'Wyciąg (kablowy)' },
  { value: 'kettlebell',    label: 'Kettlebell' },
  { value: 'drazek',        label: 'Drążek' },
  { value: 'gumy',          label: 'Gumy oporowe' },
  { value: 'brak',          label: 'Własna masa ciała' },
]

// Stałe ID kroków — kolejność wyznacza getStepList()
const STEP_IDS = [
  'wiek_plec', 'wzrost_waga', 'doswiadczenie', 'cel', 'cel_wagowy',
  'dni', 'czas', 'miejsce', 'sprzet',
  'kontuzje', 'ograniczenia',
  'sen', 'aktywnosc', 'stres', 'dieta',
  'osiagniecia', 'notatki',
] as const
type StepId = typeof STEP_IDS[number]

// cel_wagowy pokazuje się tylko przy masa/redukcja
function getStepList(cel: string): StepId[] {
  const steps: StepId[] = ['wiek_plec', 'wzrost_waga', 'doswiadczenie', 'cel']
  if (cel === 'masa' || cel === 'redukcja') steps.push('cel_wagowy')
  steps.push('dni', 'czas', 'miejsce', 'sprzet', 'kontuzje', 'ograniczenia',
             'sen', 'aktywnosc', 'stres', 'dieta', 'osiagniecia', 'notatki')
  return steps
}

const STEP_META: Record<StepId, { title: string; sub: string }> = {
  wiek_plec:     { title: 'Zacznijmy od podstaw',     sub: 'Wiek i płeć — podstawa do personalizacji planu' },
  wzrost_waga:   { title: 'Twoje parametry',          sub: 'Wzrost i waga — potrzebne do dobrania obciążeń i intensywności' },
  doswiadczenie: { title: 'Twoje doświadczenie',      sub: 'Od tego zależy poziom trudności i dobór ćwiczeń' },
  cel:           { title: 'Co chcesz osiągnąć?',      sub: 'Jeden główny cel — możesz go zmienić w każdej chwili' },
  cel_wagowy:    { title: 'Twój cel wagowy',          sub: 'Konkretna liczba pomaga dobrać kaloryczność i tempo' },
  dni:           { title: 'Ile dni trenujesz?',       sub: 'Realna liczba — nie idealna. Plan ma działać, nie leżeć w szufladzie' },
  czas:          { title: 'Czas na jeden trening',    sub: 'Od tego zależy ile ćwiczeń i serii zmieści się w planie' },
  miejsce:       { title: 'Gdzie trenujesz?',         sub: 'Dostosowuję dobór ćwiczeń do dostępnej infrastruktury' },
  sprzet:        { title: 'Dostępny sprzęt',          sub: 'Zaznacz wszystko co masz do dyspozycji' },
  kontuzje:      { title: 'Kontuzje i bóle',          sub: 'Ważne — dobiorę ćwiczenia które nie zaszkodzą i omijają problem' },
  ograniczenia:  { title: 'Ograniczenia zdrowotne',   sub: 'Wszystko co powinienem wiedzieć zanim zaplanuje Twój trening' },
  sen:           { title: 'Jak śpisz?',               sub: 'Regeneracja to połowa efektów — muszę to wziąć pod uwagę przy planie' },
  aktywnosc:     { title: 'Aktywność poza treningiem',sub: 'Ile się ruszasz w ciągu dnia? Wpływa na regenerację i zapotrzebowanie kaloryczne' },
  stres:         { title: 'Poziom stresu',            sub: 'Chroniczny stres podnosi kortyzol i spowalnia postępy — to realna zmienna' },
  dieta:         { title: 'Twoje odżywianie',         sub: 'Nie układam jadłospisu — chcę wiedzieć z czym startujemy' },
  osiagniecia:   { title: 'Twoje wyniki',             sub: 'Opcjonalnie — pomaga mi dobrać ciężary startowe i ocenić siłę bazową' },
  notatki:       { title: 'Coś jeszcze?',             sub: 'Wolne pole — cokolwiek co może mieć znaczenie dla Twojego planu' },
}

// ── Komponenty UI ──────────────────────────────────────────

function CardOption({ value, label, selected, onSelect, sub }: {
  value: string; label: string; selected: boolean; onSelect: (v: string) => void; sub?: string
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

// ── Główny komponent ───────────────────────────────────────

export default function QuizPage() {
  const router = useRouter()
  const [stepIndex, setStepIndex] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [form, setForm] = useState({
    wiek: '', plec: '', wzrost: '', waga: '',
    poziom: '', cel: '', cel_wagowy: '',
    dni_treningowe: '', czas_treningu: '',
    miejsce_treningu: '', dostepny_sprzet: [] as string[],
    has_kontuzje: '', kontuzje: '',
    has_ograniczenia: '', ograniczenia: '',
    jakosc_snu: '', aktywnosc_codzienna: '',
    poziom_stresu: '', dieta: '',
    osiagniecia: '', notatki_quiz: '',
  })

  useEffect(() => {
    async function checkAuth() {
      const token = await getValidToken()
      if (!token) { router.replace('/'); return }
      try {
        const res = await fetch(`${API_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) { router.replace('/'); return }
        const data = await res.json()
        if (data.subscription_status !== 'active') { router.replace('/pricing'); return }
      } catch {
        router.replace('/')
      }
    }
    checkAuth()
  }, [router])

  const stepList = getStepList(form.cel)
  const totalSteps = stepList.length
  const currentId = stepList[stepIndex]
  const progress = (stepIndex / (totalSteps - 1)) * 100

  function set(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  function toggleSprzet(value: string) {
    setForm(prev => {
      if (value === 'brak') {
        return { ...prev, dostepny_sprzet: prev.dostepny_sprzet.includes('brak') ? [] : ['brak'] }
      }
      const bez = prev.dostepny_sprzet.filter(s => s !== 'brak')
      return {
        ...prev,
        dostepny_sprzet: bez.includes(value) ? bez.filter(s => s !== value) : [...bez, value],
      }
    })
  }

  function validate(): string {
    switch (currentId) {
      case 'wiek_plec': {
        const w = parseInt(form.wiek)
        if (!form.wiek || isNaN(w) || w < 12 || w > 100) return 'Wiek musi być między 12 a 100'
        if (!form.plec) return 'Wybierz płeć'
        return ''
      }
      case 'wzrost_waga': {
        const wz = parseInt(form.wzrost), wa = parseFloat(form.waga)
        if (!form.wzrost || isNaN(wz) || wz < 100 || wz > 250) return 'Wzrost musi być między 100 a 250 cm'
        if (!form.waga || isNaN(wa) || wa < 30 || wa > 300) return 'Waga musi być między 30 a 300 kg'
        return ''
      }
      case 'doswiadczenie': return form.poziom ? '' : 'Wybierz poziom zaawansowania'
      case 'cel':           return form.cel ? '' : 'Wybierz cel treningowy'
      case 'cel_wagowy': {
        const cw = parseFloat(form.cel_wagowy)
        if (!form.cel_wagowy || isNaN(cw) || cw < 30 || cw > 300) return 'Podaj docelową wagę (30–300 kg)'
        const biezaca = parseFloat(form.waga)
        if (form.cel === 'redukcja' && cw >= biezaca) return `Cel redukcji musi być poniżej Twojej obecnej wagi (${form.waga} kg)`
        if (form.cel === 'masa' && cw <= biezaca) return `Cel budowy masy musi być powyżej Twojej obecnej wagi (${form.waga} kg)`
        return ''
      }
      case 'dni': {
        const d = parseInt(form.dni_treningowe)
        if (!form.dni_treningowe || isNaN(d) || d < 2 || d > 6) return 'Wybierz liczbę dni'
        return ''
      }
      case 'czas':      return form.czas_treningu ? '' : 'Wybierz czas treningu'
      case 'miejsce':   return form.miejsce_treningu ? '' : 'Wybierz miejsce treningu'
      case 'sprzet':    return form.dostepny_sprzet.length > 0 ? '' : 'Zaznacz co najmniej jeden sprzęt'
      case 'kontuzje': {
        if (!form.has_kontuzje) return 'Odpowiedz na pytanie'
        if (form.has_kontuzje === 'tak' && !form.kontuzje.trim()) return 'Opisz kontuzję — to ważne dla bezpieczeństwa planu'
        return ''
      }
      case 'ograniczenia': {
        if (!form.has_ograniczenia) return 'Odpowiedz na pytanie'
        if (form.has_ograniczenia === 'tak' && !form.ograniczenia.trim()) return 'Opisz ograniczenia — to ważne dla bezpieczeństwa planu'
        return ''
      }
      case 'sen':      return form.jakosc_snu ? '' : 'Wybierz jak śpisz'
      case 'aktywnosc':return form.aktywnosc_codzienna ? '' : 'Wybierz poziom aktywności'
      case 'stres':    return form.poziom_stresu ? '' : 'Określ poziom stresu'
      case 'dieta':    return form.dieta ? '' : 'Określ swoje podejście do diety'
      default:         return ''
    }
  }

  function next() {
    setError('')
    const err = validate()
    if (err) { setError(err); return }
    // Jeśli user zmienił cel z masa/redukcja na sila/kondycja, krok cel_wagowy
    // zniknie z listy — stepIndex może wskazywać poza zakres, ale getStepList
    // liczy aktualną listę, więc jest bezpieczny
    if (stepIndex < totalSteps - 1) setStepIndex(i => i + 1)
  }

  function prev() {
    setError('')
    if (stepIndex > 0) setStepIndex(i => i - 1)
  }

  async function handleSubmit() {
    setError('')
    setLoading(true)
    const token = await getValidToken()

    const notatki_parts: string[] = []
    if (form.cel_wagowy && (form.cel === 'masa' || form.cel === 'redukcja')) {
      const kierunek = form.cel === 'masa' ? 'Cel masy' : 'Cel redukcji'
      notatki_parts.push(`${kierunek}: ${form.cel_wagowy} kg`)
    }
    if (form.notatki_quiz.trim()) notatki_parts.push(form.notatki_quiz.trim())

    try {
      const res = await fetch(`${API_URL}/quiz/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          wiek: parseInt(form.wiek),
          plec: form.plec,
          wzrost: parseInt(form.wzrost),
          waga: parseFloat(form.waga),
          poziom: form.poziom,
          cel: form.cel,
          dni_treningowe: parseInt(form.dni_treningowe),
          czas_treningu: form.czas_treningu,
          miejsce_treningu: form.miejsce_treningu,
          dostepny_sprzet: form.dostepny_sprzet,
          kontuzje: form.has_kontuzje === 'tak' ? form.kontuzje.trim() : null,
          ograniczenia: form.has_ograniczenia === 'tak' ? form.ograniczenia.trim() : null,
          jakosc_snu: form.jakosc_snu || null,
          aktywnosc_codzienna: form.aktywnosc_codzienna || null,
          poziom_stresu: form.poziom_stresu || null,
          dieta: form.dieta || null,
          osiagniecia: form.osiagniecia.trim() || null,
          notatki_quiz: notatki_parts.length > 0 ? notatki_parts.join(' | ') : null,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Błąd wysyłania quizu')
      router.push('/chat')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd wysyłania quizu')
    } finally {
      setLoading(false)
    }
  }

  const inputClass = 'w-full bg-[#111111] border border-[#2A2A2A] text-white rounded-xl px-4 py-3 focus:outline-none focus:border-[#00FF88] transition-colors placeholder-zinc-600 text-sm'
  const textareaClass = inputClass + ' resize-none h-28'
  const yesNoClass = (active: boolean) =>
    `flex-1 py-3.5 rounded-xl border text-sm font-medium transition-all active:scale-[0.98] ${
      active
        ? 'border-[#00FF88] bg-[#00FF88]/10 text-white'
        : 'border-[#2A2A2A] bg-[#111111] text-zinc-400 hover:border-zinc-500'
    }`

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Progress */}
        <div className="mb-7">
          <div className="flex items-center justify-between mb-2">
            <span className="text-zinc-500 text-xs">{stepIndex + 1} / {totalSteps}</span>
            <span className="text-[#00FF88] text-xs font-medium">{Math.round(progress)}%</span>
          </div>
          <div className="h-1 bg-[#1A1A1A] rounded-full overflow-hidden">
            <div className="h-full bg-[#00FF88] rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }} />
          </div>
        </div>

        {/* Title */}
        <div className="mb-6">
          <h1 className="text-white text-xl font-bold">{STEP_META[currentId].title}</h1>
          <p className="text-zinc-500 text-sm mt-1">{STEP_META[currentId].sub}</p>
        </div>

        {/* ── wiek_plec ── */}
        {currentId === 'wiek_plec' && (
          <div className="space-y-4">
            <div>
              <label className="block text-zinc-400 text-xs mb-2">Wiek</label>
              <input type="number" className={inputClass} value={form.wiek}
                onChange={e => set('wiek', e.target.value)} placeholder="np. 25" min={12} max={100} />
            </div>
            <div>
              <label className="block text-zinc-400 text-xs mb-2">Płeć</label>
              <div className="flex gap-3">
                {[{ v: 'mezczyzna', l: 'Mężczyzna' }, { v: 'kobieta', l: 'Kobieta' }].map(({ v, l }) => (
                  <button key={v} type="button" onClick={() => set('plec', v)} className={yesNoClass(form.plec === v)}>{l}</button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── wzrost_waga ── */}
        {currentId === 'wzrost_waga' && (
          <div className="space-y-4">
            <div>
              <label className="block text-zinc-400 text-xs mb-2">Wzrost (cm)</label>
              <input type="number" className={inputClass} value={form.wzrost}
                onChange={e => set('wzrost', e.target.value)} placeholder="np. 175" min={100} max={250} />
            </div>
            <div>
              <label className="block text-zinc-400 text-xs mb-2">Aktualna waga (kg)</label>
              <input type="number" className={inputClass} value={form.waga}
                onChange={e => set('waga', e.target.value)} placeholder="np. 80" min={30} max={300} />
            </div>
          </div>
        )}

        {/* ── doswiadczenie ── */}
        {currentId === 'doswiadczenie' && (
          <div className="space-y-2">
            {[
              { v: 'poczatkujacy', l: 'Początkujący',       s: 'Mniej niż rok treningu lub dopiero zaczynam' },
              { v: 'srednio',      l: 'Średniozaawansowany', s: '1–3 lata regularnego treningu siłowego' },
              { v: 'zaawansowany', l: 'Zaawansowany',        s: 'Ponad 3 lata, znam technikę, świadomie progresuje' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.poziom === v} onSelect={v => set('poziom', v)} />
            ))}
          </div>
        )}

        {/* ── cel ── */}
        {currentId === 'cel' && (
          <div className="space-y-2">
            {[
              { v: 'masa',     l: 'Budowa masy mięśniowej', s: 'Chcę być większy, mocniejszy, przybrać na wadze' },
              { v: 'redukcja', l: 'Redukcja tkanki tłuszczowej', s: 'Chcę schudnąć, zachowując lub budując mięśnie' },
              { v: 'sila',     l: 'Siła',                   s: 'Chcę podnosić coraz więcej — wyniki na wadze mnie nie interesują' },
              { v: 'kondycja', l: 'Kondycja i zdrowie',      s: 'Chcę być sprawniejszy, zdrowszy, mieć więcej energii' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.cel === v} onSelect={v => set('cel', v)} />
            ))}
          </div>
        )}

        {/* ── cel_wagowy (warunkowy) ── */}
        {currentId === 'cel_wagowy' && (
          <div className="space-y-3">
            {form.waga && (
              <p className="text-zinc-500 text-xs">
                Twoja aktualna waga: <span className="text-zinc-300 font-medium">{form.waga} kg</span>
              </p>
            )}
            <div>
              <label className="block text-zinc-400 text-xs mb-2">
                {form.cel === 'masa' ? 'Do jakiej wagi chcesz dojść? (kg)' : 'Do jakiej wagi chcesz zejść? (kg)'}
              </label>
              <input type="number" className={inputClass} value={form.cel_wagowy}
                onChange={e => set('cel_wagowy', e.target.value)}
                placeholder={form.cel === 'masa' ? 'np. 90' : 'np. 75'}
                min={30} max={300} />
            </div>
            <p className="text-zinc-600 text-xs">Nie musisz być precyzyjny — orientacyjna wartość wystarczy. Zmienisz to w każdej chwili.</p>
          </div>
        )}

        {/* ── dni ── */}
        {currentId === 'dni' && (
          <div>
            <div className="grid grid-cols-5 gap-2">
              {[2, 3, 4, 5, 6].map(n => (
                <button key={n} type="button" onClick={() => set('dni_treningowe', String(n))}
                  className={`py-4 rounded-xl border text-base font-bold transition-all active:scale-[0.96] ${
                    form.dni_treningowe === String(n)
                      ? 'border-[#00FF88] bg-[#00FF88]/10 text-[#00FF88]'
                      : 'border-[#2A2A2A] bg-[#111111] text-zinc-400 hover:border-zinc-500'
                  }`}>{n}</button>
              ))}
            </div>
            <p className="text-zinc-600 text-xs mt-3">Minimum 2 dni — poniżej tej liczby plan nie ma sensu. Lepiej 3 solidne niż 5 połowicznych.</p>
          </div>
        )}

        {/* ── czas ── */}
        {currentId === 'czas' && (
          <div className="space-y-2">
            {[
              { v: '30-45', l: '30–45 minut',  s: 'Szybki i skupiony — tylko to co najważniejsze' },
              { v: '45-60', l: '45–60 minut',  s: 'Standardowy trening' },
              { v: '60-90', l: '60–90 minut',  s: 'Spokojniejsze tempo, więcej ćwiczeń' },
              { v: '90+',   l: 'Ponad 90 minut', s: 'Dużo czasu, lubię długie treningi' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.czas_treningu === v} onSelect={v => set('czas_treningu', v)} />
            ))}
          </div>
        )}

        {/* ── miejsce ── */}
        {currentId === 'miejsce' && (
          <div className="space-y-2">
            {[
              { v: 'silownia',  l: 'Siłownia komercyjna',    s: 'Pełne wyposażenie — maszyny, wolne ciężary, wyciągi' },
              { v: 'dom',       l: 'Dom / siłownia domowa',  s: 'Ograniczony sprzęt, trenuję we własnych warunkach' },
              { v: 'mieszanko', l: 'Mieszanko',              s: 'Część treningów na siłowni, część w domu' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.miejsce_treningu === v} onSelect={v => set('miejsce_treningu', v)} />
            ))}
          </div>
        )}

        {/* ── sprzet ── */}
        {currentId === 'sprzet' && (
          <div className="space-y-2">
            {SPRZET_OPTIONS.map(opt => (
              <CheckOption key={opt.value} value={opt.value} label={opt.label}
                checked={form.dostepny_sprzet.includes(opt.value)} onToggle={toggleSprzet} />
            ))}
          </div>
        )}

        {/* ── kontuzje ── */}
        {currentId === 'kontuzje' && (
          <div className="space-y-3">
            <div className="flex gap-3">
              <button type="button" onClick={() => set('has_kontuzje', 'nie')} className={yesNoClass(form.has_kontuzje === 'nie')}>Nie mam</button>
              <button type="button" onClick={() => set('has_kontuzje', 'tak')} className={yesNoClass(form.has_kontuzje === 'tak')}>Mam kontuzje / bóle</button>
            </div>
            {form.has_kontuzje === 'tak' && (
              <div>
                <label className="block text-zinc-400 text-xs mb-2">Co i gdzie? Im dokładniej, tym lepiej</label>
                <textarea className={textareaClass} value={form.kontuzje}
                  onChange={e => set('kontuzje', e.target.value)}
                  placeholder="np. ból lewego kolana przy przysiadach poniżej równoległej, bark prawy — dyskomfort przy OHP, lędźwie przy martwym ciągu..." />
              </div>
            )}
          </div>
        )}

        {/* ── ograniczenia ── */}
        {currentId === 'ograniczenia' && (
          <div className="space-y-3">
            <p className="text-zinc-500 text-xs">Nadciśnienie, choroby serca, dyskopatia, praca fizyczna, praca zmianowa — cokolwiek co powinno wpłynąć na plan.</p>
            <div className="flex gap-3">
              <button type="button" onClick={() => set('has_ograniczenia', 'nie')} className={yesNoClass(form.has_ograniczenia === 'nie')}>Brak ograniczeń</button>
              <button type="button" onClick={() => set('has_ograniczenia', 'tak')} className={yesNoClass(form.has_ograniczenia === 'tak')}>Mam ograniczenia</button>
            </div>
            {form.has_ograniczenia === 'tak' && (
              <div>
                <label className="block text-zinc-400 text-xs mb-2">Opisz — im dokładniej, tym bezpieczniejszy plan</label>
                <textarea className={textareaClass} value={form.ograniczenia}
                  onChange={e => set('ograniczenia', e.target.value)}
                  placeholder="np. dyskopatia L4/L5 — nie mogę robić ciężkich martwych ciągów, nadciśnienie, nie mogę podnosić rąk powyżej głowy..." />
              </div>
            )}
          </div>
        )}

        {/* ── sen ── */}
        {currentId === 'sen' && (
          <div className="space-y-2">
            {[
              { v: 'swietnie', l: 'Świetnie',  s: '8+ godzin, regularnie, budzę się wypoczęty' },
              { v: 'dobrze',   l: 'Dobrze',    s: '7–8 godzin, bez większych problemów' },
              { v: 'srednio',  l: 'Średnio',   s: '5–7 godzin, bywa różnie, zdarzają się złe noce' },
              { v: 'slabo',    l: 'Słabo',     s: 'Mało snu na co dzień, wyraźnie odczuwam niedobór' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.jakosc_snu === v} onSelect={v => set('jakosc_snu', v)} />
            ))}
          </div>
        )}

        {/* ── aktywnosc ── */}
        {currentId === 'aktywnosc' && (
          <div className="space-y-2">
            {[
              { v: 'siedzaca',    l: 'Siedząca',    s: 'Biuro, komputer, mało ruchu przez większość dnia' },
              { v: 'umiarkowana', l: 'Umiarkowana', s: 'Sporo chodzę, stojąca lub mieszana praca' },
              { v: 'aktywna',     l: 'Aktywna',     s: 'Praca fizyczna lub bardzo dużo ruchu poza treningiem' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.aktywnosc_codzienna === v} onSelect={v => set('aktywnosc_codzienna', v)} />
            ))}
          </div>
        )}

        {/* ── stres ── */}
        {currentId === 'stres' && (
          <div className="space-y-2">
            {[
              { v: 'niski',        l: 'Niski',         s: 'Spokojnie, nic mnie szczególnie nie gniecie' },
              { v: 'umiarkowany',  l: 'Umiarkowany',   s: 'Bywa stresująco, ale generalnie daję radę' },
              { v: 'wysoki',       l: 'Wysoki',        s: 'Dużo na głowie, często pod presją, trudno wyłączyć głowę' },
              { v: 'bardzo_wysoki',l: 'Bardzo wysoki', s: 'Chroniczny stres, ciągłe napięcie, słabo się regeneruję' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.poziom_stresu === v} onSelect={v => set('poziom_stresu', v)} />
            ))}
          </div>
        )}

        {/* ── dieta ── */}
        {currentId === 'dieta' && (
          <div className="space-y-2">
            {[
              { v: 'nie_pilnuje', l: 'Nie pilnuję',     s: 'Jem co popadnie, nie zwracam uwagi na skład' },
              { v: 'staram_sie',  l: 'Staram się',      s: 'Staram się jeść zdrowo, ale nie liczę kalorii ani makro' },
              { v: 'pilnuje',     l: 'Pilnuję',         s: 'Liczę kalorie lub makro, wiem co jem' },
              { v: 'specjalna',   l: 'Dieta specjalna', s: 'Weganizm, wegetarianizm, keto, IF lub inna specyficzna' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.dieta === v} onSelect={v => set('dieta', v)} />
            ))}
          </div>
        )}

        {/* ── osiagniecia ── */}
        {currentId === 'osiagniecia' && (
          <div className="space-y-3">
            <p className="text-zinc-500 text-xs">Opcjonalnie. Jeśli dopiero zaczynasz — zostaw puste i przejdź dalej.</p>
            <textarea className={`${inputClass} resize-none h-32`} value={form.osiagniecia}
              onChange={e => set('osiagniecia', e.target.value)}
              placeholder="np. Ławka: 80 kg × 5 powt., Przysiad: 100 kg, Martwy ciąg: 120 kg, 10 podciągnięć na drążku..." />
          </div>
        )}

        {/* ── notatki ── */}
        {currentId === 'notatki' && (
          <div className="space-y-3">
            <p className="text-zinc-500 text-xs">Opcjonalnie. Tryb życia, preferencje, rzeczy których nie chcesz robić, plany na przyszłość — cokolwiek co może mieć znaczenie.</p>
            <textarea className={`${inputClass} resize-none h-32`} value={form.notatki_quiz}
              onChange={e => set('notatki_quiz', e.target.value)}
              placeholder="np. Pracuję na nocki i śpię do południa, nie znoszę biegania, chcę zacząć startować w zawodach za rok..." />
          </div>
        )}

        {error && <p className="text-red-400 text-sm mt-4">&#9888; {error}</p>}

        <div className="flex gap-3 mt-8">
          {stepIndex > 0 && (
            <button onClick={prev}
              className="px-6 py-3.5 border border-[#2A2A2A] text-zinc-400 rounded-xl hover:border-zinc-500 hover:text-white transition-all text-sm active:scale-[0.98]">
              Wstecz
            </button>
          )}
          {stepIndex < totalSteps - 1 ? (
            <button onClick={next}
              className="flex-1 bg-[#00FF88] text-black font-bold py-3.5 rounded-xl hover:brightness-110 transition-all text-sm active:scale-[0.98]">
              Dalej
            </button>
          ) : (
            <button onClick={handleSubmit} disabled={loading}
              className="flex-1 bg-[#00FF88] text-black font-bold py-3.5 rounded-xl hover:brightness-110 transition-all disabled:opacity-50 text-sm active:scale-[0.98]">
              {loading ? 'Zapisuję...' : 'Zacznij trening'}
            </button>
          )}
        </div>

      </div>
    </div>
  )
}
