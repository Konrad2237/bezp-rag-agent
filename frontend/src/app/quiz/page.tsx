'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'


const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const SPRZET_OPTIONS = [
  { value: 'sztanga', label: 'Sztanga' },
  { value: 'hantle', label: 'Hantle' },
  { value: 'maszyny', label: 'Maszyny (siłownia)' },
  { value: 'kettlebell', label: 'Kettlebell' },
  { value: 'drążek', label: 'Drążek' },
  { value: 'gumy', label: 'Gumy oporowe' },
  { value: 'brak', label: 'Bez sprzętu' },
]

const inputClass =
  'w-full bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500'
const labelClass = 'block text-zinc-400 text-sm mb-1'

export default function QuizPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [form, setForm] = useState({
    wiek: '',
    plec: '',
    waga: '',
    wzrost: '',
    cel: '',
    poziom: '',
    dni_treningowe: '',
    miejsce_treningu: '',
    dostepny_sprzet: [] as string[],
    czas_treningu: '',
    kontuzje: '',
    ograniczenia: '',
    notatki_quiz: '',
  })

  useEffect(() => {
    const token = localStorage.getItem('bezp_token')
    if (!token) router.push('/')
  }, [router])

  function update(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  function toggleSprzet(value: string) {
    setForm(prev => ({
      ...prev,
      dostepny_sprzet: prev.dostepny_sprzet.includes(value)
        ? prev.dostepny_sprzet.filter(s => s !== value)
        : [...prev.dostepny_sprzet, value],
    }))
  }

  function validateStep1(): string {
    const wiek = parseInt(form.wiek)
    const waga = parseFloat(form.waga)
    const wzrost = parseInt(form.wzrost)
    if (!form.wiek || isNaN(wiek) || wiek < 12 || wiek > 100) return 'Wiek musi być między 12 a 100'
    if (!form.plec) return 'Wybierz płeć'
    if (!form.waga || isNaN(waga) || waga < 30 || waga > 300) return 'Waga musi być między 30 a 300 kg'
    if (!form.wzrost || isNaN(wzrost) || wzrost < 100 || wzrost > 250) return 'Wzrost musi być między 100 a 250 cm'
    if (!form.cel) return 'Wybierz cel treningowy'
    return ''
  }

  function validateStep2(): string {
    const dni = parseInt(form.dni_treningowe)
    if (!form.poziom) return 'Wybierz poziom zaawansowania'
    if (!form.dni_treningowe || isNaN(dni) || dni < 2 || dni > 6) return 'Dni treningowe muszą być między 2 a 6'
    if (!form.miejsce_treningu) return 'Wybierz miejsce treningu'
    if (form.dostepny_sprzet.length === 0) return 'Wybierz co najmniej jeden sprzęt'
    if (!form.czas_treningu) return 'Wybierz czas treningu'
    return ''
  }

  function nextStep() {
    setError('')
    const err = step === 1 ? validateStep1() : step === 2 ? validateStep2() : ''
    if (err) {
      setError(err)
      return
    }
    setStep(step + 1)
  }

  async function handleSubmit() {
    setError('')
    setLoading(true)
    const token = localStorage.getItem('bezp_token')

    try {
      const res = await fetch(`${API_URL}/quiz/submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          wiek: parseInt(form.wiek),
          plec: form.plec,
          waga: parseFloat(form.waga),
          wzrost: parseInt(form.wzrost),
          cel: form.cel,
          poziom: form.poziom,
          dni_treningowe: parseInt(form.dni_treningowe),
          miejsce_treningu: form.miejsce_treningu,
          dostepny_sprzet: form.dostepny_sprzet,
          czas_treningu: form.czas_treningu,
          kontuzje: form.kontuzje || null,
          ograniczenia: form.ograniczenia || null,
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

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-white">Quiz startowy</h1>
          <span className="text-zinc-500 text-sm">Krok {step} / 3</span>
        </div>

        <div className="flex gap-2 mb-8">
          {[1, 2, 3].map(n => (
            <div key={n} className={`h-1 flex-1 rounded ${n <= step ? 'bg-white' : 'bg-zinc-700'}`} />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-zinc-400 text-sm mb-4">Podstawowe informacje</p>
            <div>
              <label className={labelClass}>Wiek</label>
              <input
                type="number"
                className={inputClass}
                value={form.wiek}
                onChange={e => update('wiek', e.target.value)}
                placeholder="np. 25"
                min={12}
                max={100}
              />
            </div>
            <div>
              <label className={labelClass}>Płeć</label>
              <select className={inputClass} value={form.plec} onChange={e => update('plec', e.target.value)}>
                <option value="">Wybierz...</option>
                <option value="mezczyzna">Mężczyzna</option>
                <option value="kobieta">Kobieta</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Waga (kg)</label>
              <input
                type="number"
                className={inputClass}
                value={form.waga}
                onChange={e => update('waga', e.target.value)}
                placeholder="np. 80"
                min={30}
                max={300}
              />
            </div>
            <div>
              <label className={labelClass}>Wzrost (cm)</label>
              <input
                type="number"
                className={inputClass}
                value={form.wzrost}
                onChange={e => update('wzrost', e.target.value)}
                placeholder="np. 175"
                min={100}
                max={250}
              />
            </div>
            <div>
              <label className={labelClass}>Cel treningowy</label>
              <select className={inputClass} value={form.cel} onChange={e => update('cel', e.target.value)}>
                <option value="">Wybierz...</option>
                <option value="masa">Budowa masy</option>
                <option value="redukcja">Redukcja tkanki tłuszczowej</option>
                <option value="sila">Budowa siły</option>
                <option value="kondycja">Poprawa kondycji</option>
              </select>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-zinc-400 text-sm mb-4">Trening</p>
            <div>
              <label className={labelClass}>Poziom zaawansowania</label>
              <select className={inputClass} value={form.poziom} onChange={e => update('poziom', e.target.value)}>
                <option value="">Wybierz...</option>
                <option value="poczatkujacy">Początkujący (0–1 rok)</option>
                <option value="srednio">Średniozaawansowany (1–3 lata)</option>
                <option value="zaawansowany">Zaawansowany (3+ lat)</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Dni treningowe w tygodniu</label>
              <input
                type="number"
                className={inputClass}
                value={form.dni_treningowe}
                onChange={e => update('dni_treningowe', e.target.value)}
                placeholder="np. 3"
                min={2}
                max={6}
              />
            </div>
            <div>
              <label className={labelClass}>Miejsce treningu</label>
              <select
                className={inputClass}
                value={form.miejsce_treningu}
                onChange={e => update('miejsce_treningu', e.target.value)}
              >
                <option value="">Wybierz...</option>
                <option value="silownia">Siłownia</option>
                <option value="dom">Dom</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Dostępny sprzęt (możesz wybrać kilka)</label>
              <div className="space-y-2 mt-2">
                {SPRZET_OPTIONS.map(opt => (
                  <label key={opt.value} className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.dostepny_sprzet.includes(opt.value)}
                      onChange={() => toggleSprzet(opt.value)}
                      className="w-4 h-4 accent-white"
                    />
                    <span className="text-zinc-300 text-sm">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className={labelClass}>Czas treningu</label>
              <select
                className={inputClass}
                value={form.czas_treningu}
                onChange={e => update('czas_treningu', e.target.value)}
              >
                <option value="">Wybierz...</option>
                <option value="30-45">30–45 minut</option>
                <option value="45-60">45–60 minut</option>
                <option value="60-90">60–90 minut</option>
                <option value="90+">90+ minut</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Kontuzje / bóle (opcjonalne)</label>
              <textarea
                className={inputClass + ' resize-none h-20'}
                value={form.kontuzje}
                onChange={e => update('kontuzje', e.target.value)}
                placeholder="np. ból kolana, problem z barkiem..."
              />
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <p className="text-zinc-400 text-sm mb-4">Dodatkowe informacje</p>
            <div>
              <label className={labelClass}>Ograniczenia zdrowotne (opcjonalne)</label>
              <textarea
                className={inputClass + ' resize-none h-24'}
                value={form.ograniczenia}
                onChange={e => update('ograniczenia', e.target.value)}
                placeholder="np. problemy z kręgosłupem, nadciśnienie..."
              />
            </div>
            <div>
              <label className={labelClass}>Coś jeszcze co powinienem wiedzieć? (opcjonalne)</label>
              <textarea
                className={inputClass + ' resize-none h-24'}
                value={form.notatki_quiz}
                onChange={e => update('notatki_quiz', e.target.value)}
                placeholder="np. trenuję od roku, wolę ćwiczenia złożone..."
              />
            </div>
          </div>
        )}

        {error && <p className="text-red-400 text-sm mt-4">{error}</p>}

        <div className="flex gap-3 mt-8">
          {step > 1 && (
            <button
              onClick={() => { setError(''); setStep(step - 1) }}
              className="flex-1 border border-zinc-600 text-white py-3 rounded hover:bg-zinc-800 transition-colors"
            >
              Wstecz
            </button>
          )}
          {step < 3 ? (
            <button
              onClick={nextStep}
              className="flex-1 bg-white text-black font-medium py-3 rounded hover:bg-zinc-200 transition-colors"
            >
              Dalej
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="flex-1 bg-white text-black font-medium py-3 rounded hover:bg-zinc-200 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Zapisuję...' : 'Zacznij trening'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
