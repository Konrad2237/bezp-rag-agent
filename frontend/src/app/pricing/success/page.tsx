'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const MAX_ATTEMPTS = 15
const INTERVAL_MS = 1000

export default function PricingSuccessPage() {
  const router = useRouter()
  const attemptsRef = useRef(0)

  useEffect(() => {
    const token = localStorage.getItem('bezp_token')
    if (!token) {
      router.replace('/login')
      return
    }

    const interval = setInterval(async () => {
      attemptsRef.current += 1
      try {
        const res = await fetch(`${API_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const data = await res.json()
          if (data.subscription_status === 'active') {
            clearInterval(interval)
            router.replace(data.has_profile ? '/chat' : '/quiz')
            return
          }
        }
      } catch {
        // sieć — spróbuj ponownie
      }

      if (attemptsRef.current >= MAX_ATTEMPTS) {
        clearInterval(interval)
        // webhook nie dotarł w 15s — przekieruj na /pricing z informacją
        router.replace('/pricing?payment=pending')
      }
    }, INTERVAL_MS)

    return () => clearInterval(interval)
  }, [router])

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex flex-col items-center justify-center px-4 gap-6">
      <div className="w-14 h-14 rounded-full bg-[#00FF88] flex items-center justify-center font-bold text-black text-2xl"
        style={{ boxShadow: '0 0 30px rgba(0,255,136,0.3)' }}
      >
        P
      </div>
      <h1 className="text-xl font-bold text-white">Płatność przyjęta!</h1>
      <p className="text-zinc-400 text-sm text-center max-w-xs">
        Aktywujemy Twoje konto — to chwilę potrwa...
      </p>

      <div className="flex gap-1 mt-2">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-[#00FF88] animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  )
}
