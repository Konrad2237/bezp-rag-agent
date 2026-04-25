'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getValidToken } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const TOTAL_STEPS = 12

const SPRZET_OPTIONS = [
  { value: 'sztanga', label: 'Sztanga + obciążenia' },
  { value: 'hantle', label: 'Hantle' },
  { value: 'lawka_pozioma', label: 'Ławka pozioma' },
  { value: 'lawka_skosna', label: 'Ławka skośna' },
  { value: 'maszyny', label: 'Maszyny' },
  { value: 'wyciag', label: 'Wyciąg (kablowy)' },
  { value: 'kettlebell', label: 'Kettlebell' },
  { value: 'drazek', label: 'Drążek' },
  { value: 'gumy', label: 'Gumy oporowe' },
  { value: 'brak', label: 'Własna masa ciała' },
]

const STEP_META: Record<number, { title: string; sub: string }> = {
  1:  { title: 'Zacznijmy od podstaw',        sub: 'Kilka danych o Tobie — potrzebne do spersonalizowanego planu' },
  2:  { title: 'Twoje doświadczenie',          sub: 'Dzięki temu dobiorę odpowiedni poziom trudności' },
  3:  { title: 'Co chcesz osiągnąć?',          sub: 'Jeden główny cel — możesz go zmienić w każdej chwili' },
  4:  { title: 'Twój harmonogram',             sub: 'Ile czasu realnie możesz poświęcić na trening?' },
  5:  { title: 'Gdzie trenujesz?',             sub: 'Dostosowuję plan do dostępnej infrastruktury' },
  6:  { title: 'Dostępny sprzęt',              sub: 'Zaznacz wszystko co masz do dyspozycji' },
  7:  { title: 'Kontuzje i bóle',              sub: 'Ważne — dobiorę ćwiczenia które nie zaszkodzą' },
  8:  { title: 'Ograniczenia zdrowotne',       sub: 'Cokolwiek powinienem uwzględnić przy planowaniu' },
  9:  { title: 'Sen i aktywność',              sub: 'Regeneracja to połowa treningu — potrzebuję tego kontekstu' },
  10: { title: 'Stres i odżywianie',           sub: 'Wpływają bezpośrednio na efekty treningowe' },
  11: { title: 'Twoje wyniki',                 sub: 'Opcjonalnie — co już potrafisz? Pomaga dobrać ciężary na start' },
  12: { title: 'Coś jeszcze?',                 sub: 'Wolne pole — wpisz co chcesz żebym wiedział' },
}

function CardOption({
  value, label, selected, onSelect, sub,
}: {
  value: string; label: string; selected: boolean; onSelect: (v: string) => void; sub?: string
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      className={`w-full text-left px-4 py-3 rounded-xl border transition-all ${
        selected
          ? 'border-[#00FF88] bg-[#00FF88]/10 text-white'
          : 'border-[#2A2A2A] bg-[#111111] text-zinc-300 hover:border-zinc-500'
      }`}
    >
      <div className="flex items-center justify-between">
        <div>
          <span className="font-medium text-sm">{label}</span>
          {sub && <span className="block text-xs text-zinc-500 mt-0.5">{sub}</span>}
        </div>
        {selected && (
          <span className="text-[#00FF88] text-sm font-bold shrink-0 ml-2">✓</span>
        )}
      </div>
    </button>
  )
}

function CheckOption({
  value, label, checked, onToggle,
}: {
  value: string; label: string; checked: boolean; onToggle: (v: string) => void
}) {
  return (
    <label
      className={`flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all ${
        checked
          ? 'border-[#00FF88] bg-[#00FF88]/10'
          : 'border-[#2A2A2A] bg-[#111111] hover:border-zinc-500'
      }`}
      onClick={() => onToggle(value)}
    >
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

export default function QuizPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [form, setForm] = useState({
    wiek: '',
    plec: '',
    wzrost: '',
    waga: '',
    poziom: '',
    cel: '',
    dni_treningowe: '',
    czas_treningu: '',
    miejsce_treningu: '',
    dostepny_sprzet: [] as string[],
    has_kontuzje: '',
    kontuzje: '',
    has_ograniczenia: '',
    ograniczenia: '',
    jakosc_snu: '',
    aktywnosc_codzienna: '',
    poziom_stresu: '',
    dieta: '',
    osiagniecia: '',
    notatki_quiz: '',
  })

  useEffect(() => {
    getValidToken().then(token => {
      if (!token) router.push('/')
    })
  }, [router])

  function set(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  function toggleSprzet(value: string) {
    setForm(prev => {
      if (value === 'brak') {
        return { ...prev, dostepny_sprzet: prev.dostepny_sprzet.includes('brak') ? [] : ['brak'] }
      }
      const bez_brak = prev.dostepny_sprzet.filter(s => s !== 'brak')
      return {
        ...prev,
        dostepny_sprzet: bez_brak.includes(value)
          ? bez_brak.filter(s => s !== value)
          : [...bez_brak, value],
      }
    })
  }

  function validateStep(): string {
    switch (step) {
      case 1: {
        const wiek = parseInt(form.wiek)
        const wzrost = parseInt(form.wzrost)
        const waga = parseFloat(form.waga)
        if (!form.wiek || isNaN(wiek) || wiek < 12 || wiek > 100) return 'Wiek musi być między 12 a 100'
        if (!form.plec) return 'Wybierz płeć'
        if (!form.wzrost || isNaN(wzrost) || wzrost < 100 || wzrost > 250) return 'Wzrost musi być między 100 a 250 cm'
        if (!form.waga || isNaN(waga) || waga < 30 || waga > 300) return 'Waga musi być między 30 a 300 kg'
        return ''
      }
      case 2: return form.poziom ? '' : 'Wybierz poziom zaawansowania'
      case 3: return form.cel ? '' : 'Wybierz cel treningowy'
      case 4: {
        const dni = parseInt(form.dni_treningowe)
        if (!form.dni_treningowe || isNaN(dni) || dni < 2 || dni > 6) return 'Wybierz liczbę dni'
        if (!form.czas_treningu) return 'Wybierz czas treningu'
        return ''
      }
      case 5: return form.miejsce_treningu ? '' : 'Wybierz miejsce treningu'
      case 6: return form.dostepny_sprzet.length > 0 ? '' : 'Zaznacz co najmniej jeden sprzęt'
      case 7: return form.has_kontuzje ? '' : 'Odpowiedz na pytanie'
      case 8: return form.has_ograniczenia ? '' : 'Odpowiedz na pytanie'
      case 9: {
        if (!form.jakosc_snu) return 'Określ jakość snu'
        if (!form.aktywnosc_codzienna) return 'Określ aktywność codzienną'
        return ''
      }
      case 10: {
        if (!form.poziom_stresu) return 'Określ poziom stresu'
        if (!form.dieta) return 'Określ swoje podejście do diety'
        return ''
      }
      default: return ''
    }
  }

  function nextStep() {
    setError('')
    const err = validateStep()
    if (err) { setError(err); return }
    if (step < TOTAL_STEPS) setStep(s => s + 1)
  }

  function prevStep() {
    setError('')
    if (step > 1) setStep(s => s - 1)
  }

  async function handleSubmit() {
    setError('')
    setLoading(true)
    const token = await getValidToken()
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
          kontuzje: form.has_kontuzje === 'tak' ? (form.kontuzje || null) : null,
          ograniczenia: form.has_ograniczenia === 'tak' ? (form.ograniczenia || null) : null,
          jakosc_snu: form.jakosc_snu || null,
          aktywnosc_codzienna: form.aktywnosc_codzienna || null,
          poziom_stresu: form.poziom_stresu || null,
          dieta: form.dieta || null,
          osiagniecia: form.osiagniecia || null,
          notatki_quiz: form.notatki_quiz || null,
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

  const progress = ((step - 1) / (TOTAL_STEPS - 1)) * 100
  const inputClass = 'w-full bg-[#111111] border border-[#2A2A2A] text-white rounded-xl px-4 py-3 focus:outline-none focus:border-[#00FF88] transition-colors placeholder-zinc-600 text-sm'
  const textareaClass = inputClass + ' resize-none h-28'

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Progress */}
        <div className="mb-7">
          <div className="flex items-center justify-between mb-2">
            <span className="text-zinc-500 text-xs">Krok {step} z {TOTAL_STEPS}</span>
            <span className="text-[#00FF88] text-xs font-medium">{Math.round(progress)}%</span>
          </div>
          <div className="h-1 bg-[#1A1A1A] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#00FF88] rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Step title */}
        <div className="mb-6">
          <h1 className="text-white text-xl font-bold">{STEP_META[step].title}</h1>
          <p className="text-zinc-500 text-sm mt-1">{STEP_META[step].sub}</p>
        </div>

        {/* ── Krok 1: Dane podstawowe ── */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-zinc-400 text-xs mb-1.5">Wiek</label>
                <input type="number" className={inputClass} value={form.wiek}
                  onChange={e => set('wiek', e.target.value)} placeholder="25" min={12} max={100} />
              </div>
              <div>
                <label className="block text-zinc-400 text-xs mb-1.5">Płeć</label>
                <div className="flex gap-2">
                  {[{ v: 'mezczyzna', l: 'Mężczyzna' }, { v: 'kobieta', l: 'Kobieta' }].map(({ v, l }) => (
                    <button key={v} type="button" onClick={() => set('plec', v)}
                      className={`flex-1 py-3 rounded-xl border text-xs font-medium transition-all ${
                        form.plec === v
                          ? 'border-[#00FF88] bg-[#00FF88]/10 text-white'
                          : 'border-[#2A2A2A] bg-[#111111] text-zinc-400 hover:border-zinc-500'
                      }`}>{l}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-zinc-400 text-xs mb-1.5">Wzrost (cm)</label>
                <input type="number" className={inputClass} value={form.wzrost}
                  onChange={e => set('wzrost', e.target.value)} placeholder="175" min={100} max={250} />
              </div>
              <div>
                <label className="block text-zinc-400 text-xs mb-1.5">Waga (kg)</label>
                <input type="number" className={inputClass} value={form.waga}
                  onChange={e => set('waga', e.target.value)} placeholder="75" min={30} max={300} />
              </div>
            </div>
          </div>
        )}

        {/* ── Krok 2: Doświadczenie ── */}
        {step === 2 && (
          <div className="space-y-2">
            {[
              { v: 'poczatkujacy', l: 'Początkujący', s: 'Mniej niż rok treningu lub dopiero zaczynam' },
              { v: 'srednio',      l: 'Średniozaawansowany', s: '1–3 lata regularnego treningu' },
              { v: 'zaawansowany', l: 'Zaawansowany', s: 'Ponad 3 lata, znam technikę, liczę ciężar' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.poziom === v} onSelect={v => set('poziom', v)} />
            ))}
          </div>
        )}

        {/* ── Krok 3: Cel ── */}
        {step === 3 && (
          <div className="space-y-2">
            {[
              { v: 'masa',     l: 'Budowa masy',   s: 'Chcę być większy i mocniejszy' },
              { v: 'redukcja', l: 'Redukcja',       s: 'Chcę stracić tkankę tłuszczową' },
              { v: 'sila',     l: 'Siła',           s: 'Chcę podnosić coraz więcej' },
              { v: 'kondycja', l: 'Kondycja',       s: 'Chcę być sprawniejszy i zdrowszy' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.cel === v} onSelect={v => set('cel', v)} />
            ))}
          </div>
        )}

        {/* ── Krok 4: Harmonogram ── */}
        {step === 4 && (
          <div className="space-y-6">
            <div>
              <label className="block text-zinc-400 text-xs mb-3">Ile dni w tygodniu możesz trenować?</label>
              <div className="flex gap-2">
                {[2, 3, 4, 5, 6].map(n => (
                  <button key={n} type="button" onClick={() => set('dni_treningowe', String(n))}
                    className={`flex-1 py-3 rounded-xl border text-sm font-bold transition-all ${
                      form.dni_treningowe === String(n)
                        ? 'border-[#00FF88] bg-[#00FF88]/10 text-[#00FF88]'
                        : 'border-[#2A2A2A] bg-[#111111] text-zinc-400 hover:border-zinc-500'
                    }`}>{n}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-zinc-400 text-xs mb-3">Czas jednego treningu</label>
              <div className="space-y-2">
                {[
                  { v: '30-45', l: '30–45 minut',  s: 'Szybki, intensywny' },
                  { v: '45-60', l: '45–60 minut',  s: 'Standardowy' },
                  { v: '60-90', l: '60–90 minut',  s: 'Rozbudowany' },
                  { v: '90+',   l: '90+ minut',    s: 'Mam dużo czasu' },
                ].map(({ v, l, s }) => (
                  <CardOption key={v} value={v} label={l} sub={s} selected={form.czas_treningu === v} onSelect={v => set('czas_treningu', v)} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Krok 5: Miejsce ── */}
        {step === 5 && (
          <div className="space-y-2">
            {[
              { v: 'silownia',   l: 'Siłownia komercyjna', s: 'Pełne wyposażenie, wszystkie maszyny' },
              { v: 'dom',        l: 'Dom / siłownia domowa', s: 'Ograniczony sprzęt, własne warunki' },
              { v: 'mieszanko',  l: 'Mieszanko',           s: 'Siłownia + treningi w domu' },
            ].map(({ v, l, s }) => (
              <CardOption key={v} value={v} label={l} sub={s} selected={form.miejsce_treningu === v} onSelect={v => set('miejsce_treningu', v)} />
            ))}
          </div>
        )}

        {/* ── Krok 6: Sprzęt ── */}
        {step === 6 && (
          <div className="space-y-2">
            {SPRZET_OPTIONS.map(opt => (
              <CheckOption key={opt.value} value={opt.value} label={opt.label}
                checked={form.dostepny_sprzet.includes(opt.value)} onToggle={toggleSprzet} />
            ))}
          </div>
        )}

        {/* ── Krok 7: Kontuzje ── */}
        {step === 7 && (
          <div className="space-y-3">
            <div className="flex gap-2">
              {[{ v: 'nie', l: 'Nie, jestem zdrowy' }, { v: 'tak', l: 'Tak, mam coś' }].map(({ v, l }) => (
                <button key={v} type="button" onClick={() => set('has_kontuzje', v)}
                  className={`flex-1 py-3 rounded-xl border text-sm font-medium transition-all ${
                    form.has_kontuzje === v
                      ? 'border-[#00FF88] bg-[#00FF88]/10 text-white'
                      : 'border-[#2A2A2A] bg-[#111111] text-zinc-400 hover:border-zinc-500'
                  }`}>{l}</button>
              ))}
            </div>
            {form.has_kontuzje === 'tak' && (
              <textarea className={textareaClass} value={form.kontuzje}
                onChange={e => set('kontuzje', e.target.value)}
                placeholder="np. ból kolana przy przysiadach, bark — problem z rotatorami..." />
            )}
          </div>
        )}

        {/* ── Krok 8: Ograniczenia ── */}
        {step === 8 && (
          <div className="space-y-3">
            <p className="text-zinc-500 text-xs">Nadciśnienie, choroby kręgosłupa, praca zmianowa — cokolwiek co powinno wpłynąć na plan.</p>
            <div className="flex gap-2">
              {[{ v: 'nie', l: 'Brak ograniczeń' }, { v: 'tak', l: 'Mam ograniczenia' }].map(({ v, l }) => (
                <button key={v} type="button" onClick={() => set('has_ograniczenia', v)}
                  className={`flex-1 py-3 rounded-xl border text-sm font-medium transition-all ${
                    form.has_ograniczenia === v
                      ? 'border-[#00FF88] bg-[#00FF88]/10 text-white'
                      : 'border-[#2A2A2A] bg-[#111111] text-zinc-400 hover:border-zinc-500'
                  }`}>{l}</button>
              ))}
            </div>
            {form.has_ograniczenia === 'tak' && (
              <textarea className={textareaClass} value={form.ograniczenia}
                onChange={e => set('ograniczenia', e.target.value)}
                placeholder="np. dyskopatia L4/L5, nie mogę podnosić rąk powyżej głowy..." />
            )}
          </div>
        )}

        {/* ── Krok 9: Sen i aktywność ── */}
        {step === 9 && (
          <div className="space-y-6">
            <div>
              <label className="block text-zinc-400 text-xs mb-3">Jak śpisz?</label>
              <div className="space-y-2">
                {[
                  { v: 'swietnie', l: 'Świetnie',  s: '8+ godzin, budzę się wypoczęty' },
                  { v: 'dobrze',   l: 'Dobrze',    s: '7–8 godzin, bez problemów' },
                  { v: 'srednio',  l: 'Średnio',   s: '5–7 godzin, bywa różnie' },
                  { v: 'slabo',    l: 'Słabo',      s: 'Mało snu, chroniczne niedobory' },
                ].map(({ v, l, s }) => (
                  <CardOption key={v} value={v} label={l} sub={s} selected={form.jakosc_snu === v} onSelect={v => set('jakosc_snu', v)} />
                ))}
              </div>
            </div>
            <div>
              <label className="block text-zinc-400 text-xs mb-3">Aktywność w ciągu dnia (poza treningiem)</label>
              <div className="space-y-2">
                {[
                  { v: 'siedzaca',    l: 'Siedząca',    s: 'Biuro, komputer, mało ruchu' },
                  { v: 'umiarkowana', l: 'Umiarkowana', s: 'Chodzę sporo, stojąca praca' },
                  { v: 'aktywna',     l: 'Aktywna',     s: 'Fizyczna praca lub dużo ruchu' },
                ].map(({ v, l, s }) => (
                  <CardOption key={v} value={v} label={l} sub={s} selected={form.aktywnosc_codzienna === v} onSelect={v => set('aktywnosc_codzienna', v)} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Krok 10: Stres i dieta ── */}
        {step === 10 && (
          <div className="space-y-6">
            <div>
              <label className="block text-zinc-400 text-xs mb-3">Poziom stresu w życiu codziennym</label>
              <div className="space-y-2">
                {[
                  { v: 'niski',        l: 'Niski',         s: 'Spokojnie, wszystko gra' },
                  { v: 'umiarkowany',  l: 'Umiarkowany',   s: 'Bywa stresująco, ale daję radę' },
                  { v: 'wysoki',       l: 'Wysoki',        s: 'Dużo na głowie, często pod presją' },
                  { v: 'bardzo_wysoki',l: 'Bardzo wysoki', s: 'Chroniczny stres, trudno się regeneruję' },
                ].map(({ v, l, s }) => (
                  <CardOption key={v} value={v} label={l} sub={s} selected={form.poziom_stresu === v} onSelect={v => set('poziom_stresu', v)} />
                ))}
              </div>
            </div>
            <div>
              <label className="block text-zinc-400 text-xs mb-3">Jak wygląda Twoja dieta?</label>
              <div className="space-y-2">
                {[
                  { v: 'nie_pilnuje', l: 'Nie pilnuję',    s: 'Jem co popadnie, bez kontroli' },
                  { v: 'staram_sie',  l: 'Staram się',     s: 'Staram się jeść zdrowo, ale nie liczę' },
                  { v: 'pilnuje',     l: 'Pilnuję',        s: 'Liczę kalorie lub makro' },
                  { v: 'specjalna',   l: 'Dieta specjalna',s: 'Weganizm, wegetarianizm, keto i inne' },
                ].map(({ v, l, s }) => (
                  <CardOption key={v} value={v} label={l} sub={s} selected={form.dieta === v} onSelect={v => set('dieta', v)} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Krok 11: Osiągnięcia ── */}
        {step === 11 && (
          <div className="space-y-3">
            <p className="text-zinc-500 text-xs">Opcjonalnie. Jeśli dopiero zaczynasz — zostaw puste.</p>
            <textarea className={textareaClass + ' h-32'} value={form.osiagniecia}
              onChange={e => set('osiagniecia', e.target.value)}
              placeholder="np. Ławka 80 kg × 5, Przysiad 100 kg, Martwy 120 kg, 10 podciągnięć..." />
          </div>
        )}

        {/* ── Krok 12: Notatki ── */}
        {step === 12 && (
          <div className="space-y-3">
            <p className="text-zinc-500 text-xs">Opcjonalnie. Preferencje, tryb życia, cele długoterminowe — cokolwiek co może być ważne.</p>
            <textarea className={textareaClass + ' h-32'} value={form.notatki_quiz}
              onChange={e => set('notatki_quiz', e.target.value)}
              placeholder="np. Pracuję na nocki, wolę ćwiczenia złożone, mam małe dziecko i mało śpię..." />
          </div>
        )}

        {error && (
          <p className="text-red-400 text-sm mt-4">&#9888; {error}</p>
        )}

        <div className="flex gap-3 mt-8">
          {step > 1 && (
            <button onClick={prevStep}
              className="px-6 py-3 border border-[#2A2A2A] text-zinc-400 rounded-xl hover:border-zinc-500 hover:text-white transition-all text-sm">
              Wstecz
            </button>
          )}
          {step < TOTAL_STEPS ? (
            <button onClick={nextStep}
              className="flex-1 bg-[#00FF88] text-black font-bold py-3 rounded-xl hover:brightness-110 transition-all text-sm">
              Dalej
            </button>
          ) : (
            <button onClick={handleSubmit} disabled={loading}
              className="flex-1 bg-[#00FF88] text-black font-bold py-3 rounded-xl hover:brightness-110 transition-all disabled:opacity-50 text-sm">
              {loading ? 'Zapisuję...' : 'Zacznij trening'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
