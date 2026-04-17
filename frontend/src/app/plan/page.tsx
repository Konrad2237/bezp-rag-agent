'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { getValidToken } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Exercise {
  name: string
  muscle_group: string
  sets: number
  reps: string
  rest_seconds: number
  notes?: string
}

interface TrainingDay {
  day_label: string
  scheduled_days: string[]
  exercises: Exercise[]
}

interface TrainingPlan {
  plan_name: string
  goal: string
  frequency_per_week: number
  duration_weeks: number
  notes?: string
  days: TrainingDay[]
}

export default function PlanPage() {
  const router = useRouter()
  const [plan, setPlan] = useState<TrainingPlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchPlan()
  }, [])

  // Gdy strona jest otwarta bez planu, co 3s cicho sprawdzaj czy Pitbul już go wygenerował
  useEffect(() => {
    if (loading || plan) return
    const interval = setInterval(async () => {
      const token = await getValidToken()
      if (!token) return
      try {
        const res = await fetch(`${API_URL}/plan/`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const data = await res.json()
          setPlan(data)
          clearInterval(interval)
        }
      } catch {
        // cicho ignoruj
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [loading, plan])

  async function fetchPlan() {
    const token = await getValidToken()
    if (!token) {
      router.replace('/')
      return
    }
    try {
      const res = await fetch(`${API_URL}/plan/`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.status === 404) {
        setPlan(null)
      } else if (res.ok) {
        const data = await res.json()
        setPlan(data)
      } else {
        setError('Błąd pobierania planu')
      }
    } catch {
      setError('Błąd połączenia')
    } finally {
      setLoading(false)
    }
  }

  const goalLabel: Record<string, string> = {
    masa: 'Budowa masy',
    redukcja: 'Redukcja',
    sila: 'Siła',
    kondycja: 'Kondycja',
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <p className="text-zinc-500">Ładuję plan...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-white font-bold leading-tight">BEZ PIERDOLENIA</h1>
          <p className="text-zinc-500 text-xs">z Pitbulem</p>
        </div>
        <div className="flex items-center gap-4">
          <nav className="flex gap-1 bg-zinc-900 rounded p-1">
            <Link
              href="/chat"
              className="px-3 py-1.5 text-sm rounded text-zinc-400 hover:text-white transition-colors"
            >
              Chat
            </Link>
            <span className="px-3 py-1.5 text-sm rounded bg-white text-black font-medium">
              Plan
            </span>
          </nav>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 max-w-2xl mx-auto w-full">
        {!plan && !loading && (
          <div className="text-center py-16">
            <p className="text-zinc-400 mb-2">Nie masz jeszcze planu treningowego.</p>
            <p className="text-zinc-600 text-sm mb-6">Napisz do Pitbula — on wywoła Szybciora i plan pojawi się tutaj automatycznie.</p>
            <Link
              href="/chat"
              className="bg-white text-black font-medium px-6 py-3 rounded hover:bg-zinc-200 transition-colors"
            >
              Idź do chatu →
            </Link>
          </div>
        )}

        {plan && (
          <div>
            {/* Plan header */}
            <div className="mb-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-white text-xl font-bold">{plan.plan_name}</h2>
                  <div className="flex gap-3 mt-1 flex-wrap">
                    <span className="text-zinc-400 text-sm">{goalLabel[plan.goal] ?? plan.goal}</span>
                    <span className="text-zinc-600 text-sm">·</span>
                    <span className="text-zinc-400 text-sm">{plan.frequency_per_week}x / tydzień</span>
                    <span className="text-zinc-600 text-sm">·</span>
                    <span className="text-zinc-400 text-sm">{plan.duration_weeks} tygodnie</span>
                  </div>
                  {plan.notes && (
                    <p className="text-zinc-500 text-sm mt-2">{plan.notes}</p>
                  )}
                </div>
                <button
                  onClick={fetchPlan}
                  className="shrink-0 border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 text-sm px-4 py-2 rounded transition-colors"
                >
                  Odśwież
                </button>
              </div>
              {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
            </div>

            {/* Days */}
            <div className="space-y-6">
              {plan.days.map((day, di) => (
                <div key={di} className="bg-zinc-900 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 border-b border-zinc-800">
                    <h3 className="text-white font-medium">{day.day_label}</h3>
                    {day.scheduled_days?.length > 0 && (
                      <p className="text-zinc-500 text-xs mt-0.5">{day.scheduled_days.join(', ')}</p>
                    )}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-zinc-800">
                          <th className="text-left px-4 py-2 text-zinc-500 font-normal">Ćwiczenie</th>
                          <th className="text-center px-3 py-2 text-zinc-500 font-normal whitespace-nowrap">Serie</th>
                          <th className="text-center px-3 py-2 text-zinc-500 font-normal whitespace-nowrap">Powt.</th>
                          <th className="text-center px-3 py-2 text-zinc-500 font-normal whitespace-nowrap">Przerwa</th>
                        </tr>
                      </thead>
                      <tbody>
                        {day.exercises.map((ex, ei) => (
                          <tr key={ei} className="border-b border-zinc-800 last:border-0">
                            <td className="px-4 py-3">
                              <div className="text-white">{ex.name}</div>
                              <div className="text-zinc-500 text-xs">{ex.muscle_group}</div>
                              {ex.notes && (
                                <div className="text-zinc-600 text-xs mt-0.5 italic">{ex.notes}</div>
                              )}
                            </td>
                            <td className="px-3 py-3 text-center text-zinc-300">{ex.sets}</td>
                            <td className="px-3 py-3 text-center text-zinc-300">{ex.reps}</td>
                            <td className="px-3 py-3 text-center text-zinc-500 text-xs whitespace-nowrap">{ex.rest_seconds}s</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
