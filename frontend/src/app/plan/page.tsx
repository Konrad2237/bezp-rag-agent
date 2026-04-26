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
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchPlan()
  }, [])

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

  async function fetchPlan(isRefresh = false) {
    if (isRefresh) setRefreshing(true)
    setError('')
    const token = await getValidToken()
    if (!token) {
      router.replace('/')
      return
    }
    try {
      const res = await fetch(`${API_URL}/plan/?t=${Date.now()}`, {
        headers: { Authorization: `Bearer ${token}`, 'Cache-Control': 'no-cache' },
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
      setRefreshing(false)
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

  const goalLabel: Record<string, string> = {
    masa: 'Budowa masy',
    redukcja: 'Redukcja',
    sila: 'Siła',
    kondycja: 'Kondycja',
  }

  if (loading) {
    return (
      <div className="h-[100dvh] bg-[#0D0D0D] flex items-center justify-center">
        <p className="text-zinc-500 text-sm">Ładuję plan...</p>
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
          <div className="shrink-0">
            <p className="text-white font-semibold text-sm leading-none mb-1">Pitbul</p>
            <p className="text-[#00FF88] text-xs whitespace-nowrap">● online 24/7</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <nav className="flex gap-1 bg-[#111111] border border-[#2A2A2A] rounded-lg p-1">
            <Link href="/chat" className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors">
              Chat
            </Link>
            <span className="px-3 py-1.5 text-xs rounded-md bg-[#00FF88] text-black font-bold">
              Plan
            </span>
            <Link href="/settings" className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors">
              Ustawienia
            </Link>
          </nav>
          <button
            onClick={handleLogout}
            className="hidden sm:inline text-zinc-500 hover:text-zinc-300 text-xs transition-colors"
          >
            Wyloguj
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 max-w-2xl mx-auto w-full">
        {!plan && !loading && (
          <div className="text-center py-16">
            <p className="text-zinc-400 mb-2">Nie masz jeszcze planu treningowego.</p>
            <p className="text-zinc-500 text-sm mb-6">Napisz do Pitbula — on wywoła Szybciora i plan pojawi się tutaj automatycznie.</p>
            <Link
              href="/chat"
              className="bg-[#00FF88] text-black font-bold px-6 py-3 rounded-xl hover:brightness-110 transition-all"
            >
              Idź do chatu →
            </Link>
          </div>
        )}

        {plan && (
          <div>
            <div className="mb-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-white text-xl font-bold">{plan.plan_name}</h2>
                  <div className="flex gap-3 mt-1 flex-wrap">
                    <span className="text-[#00FF88] text-sm">{goalLabel[plan.goal] ?? plan.goal}</span>
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
                  onClick={() => fetchPlan(true)}
                  disabled={refreshing}
                  className="shrink-0 border border-[#2A2A2A] text-zinc-400 hover:text-white hover:border-[#00FF88] text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                >
                  {refreshing ? 'Odświeżam...' : 'Odśwież'}
                </button>
              </div>
              {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
            </div>

            <div className="space-y-4">
              {plan.days.map((day, di) => (
                <div key={di} className="bg-[#111111] rounded-xl overflow-hidden border border-[#2A2A2A]">
                  <div className="px-4 py-3 border-b border-[#2A2A2A]">
                    <h3 className="text-white font-semibold text-sm">{day.day_label}</h3>
                    {day.scheduled_days?.length > 0 && (
                      <p className="text-zinc-500 text-xs mt-0.5">{day.scheduled_days.join(', ')}</p>
                    )}
                  </div>
                  <div className="divide-y divide-[#1A1A1A]">
                    {day.exercises.map((ex, ei) => (
                      <div key={ei} className="px-4 py-3 flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-[#F2EEE8] text-sm font-medium">{ex.name}</div>
                          <div className="text-zinc-500 text-xs mt-0.5">{ex.muscle_group}</div>
                          {ex.notes && (
                            <div className="text-zinc-600 text-xs mt-0.5 italic">{ex.notes}</div>
                          )}
                        </div>
                        <div className="shrink-0 text-right">
                          <div className="text-[#00FF88] text-sm font-bold">{ex.sets}×{ex.reps}</div>
                          <div className="text-zinc-600 text-xs">{ex.rest_seconds}s przerwy</div>
                        </div>
                      </div>
                    ))}
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
