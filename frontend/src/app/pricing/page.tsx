'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const plans = [
  {
    id: 'week',
    label: 'Tygodniowy',
    price: '19',
    period: '/ tydzień',
    highlight: false,
    desc: 'Idealne na start — wypróbuj bez zobowiązań.',
  },
  {
    id: 'month',
    label: 'Miesięczny',
    price: '69',
    period: '/ miesiąc',
    highlight: true,
    badge: 'Najpopularniejszy',
    desc: 'Pełen miesiąc pracy z AI trenerem. Oszczędzasz 7 zł vs tygodniowy.',
  },
  {
    id: 'quarter',
    label: 'Kwartalny',
    price: '189',
    period: '/ 3 miesiące',
    highlight: false,
    desc: 'Najlepsza cena. Oszczędzasz 18 zł vs miesięczny.',
  },
]

export default function PricingPage() {
  const router = useRouter()
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)

  async function choosePlan(planId: string) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('bezp_token') : null

    if (!token) {
      // Niezalogowany → rejestracja z wybranym planem
      router.push(`/login?plan=${planId}&mode=register`)
      return
    }

    // Zalogowany → od razu Stripe Checkout
    setLoadingPlan(planId)
    try {
      const res = await fetch(`${API_URL}/payments/create-checkout-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan: planId }),
      })
      if (!res.ok) {
        // Token mógł wygasnąć
        router.push(`/login?plan=${planId}&mode=register`)
        return
      }
      const data = await res.json()
      window.location.href = data.checkout_url
    } catch {
      router.push(`/login?plan=${planId}&mode=register`)
    } finally {
      setLoadingPlan(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex flex-col items-center justify-center px-4 py-16">

      <div className="w-14 h-14 rounded-full bg-[#00FF88] flex items-center justify-center font-bold text-black text-2xl mb-4"
        style={{ boxShadow: '0 0 30px rgba(0,255,136,0.3)' }}
      >
        P
      </div>
      <h1 className="text-2xl font-bold text-white mb-1">Wybierz plan</h1>
      <p className="text-zinc-400 text-sm mb-10 text-center">
        Nieograniczony dostęp do AI trenera. Anuluj kiedy chcesz.
      </p>

      <div className="w-full max-w-3xl grid grid-cols-1 sm:grid-cols-3 gap-4">
        {plans.map(plan => (
          <div
            key={plan.id}
            className={`relative flex flex-col rounded-2xl border p-6 transition-all ${
              plan.highlight
                ? 'border-[#00FF88] bg-[#0a1a12]'
                : 'border-[#2A2A2A] bg-[#111111]'
            }`}
            style={plan.highlight ? { boxShadow: '0 0 30px rgba(0,255,136,0.12)' } : {}}
          >
            {plan.badge && (
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#00FF88] text-black text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap">
                {plan.badge}
              </span>
            )}
            <p className="text-zinc-400 text-sm mb-1">{plan.label}</p>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-3xl font-bold text-white">{plan.price} zł</span>
              <span className="text-zinc-500 text-sm mb-1">{plan.period}</span>
            </div>
            <p className="text-zinc-500 text-xs mb-6 leading-snug">{plan.desc}</p>
            <button
              onClick={() => choosePlan(plan.id)}
              disabled={loadingPlan !== null}
              className={`mt-auto w-full py-3 rounded-xl font-bold text-sm transition-all active:scale-[0.97] disabled:opacity-60 ${
                plan.highlight
                  ? 'bg-[#00FF88] text-black hover:brightness-110'
                  : 'bg-[#1A1A1A] text-white border border-[#2A2A2A] hover:border-[#00FF88] hover:text-[#00FF88]'
              }`}
              style={plan.highlight ? { boxShadow: '0 0 20px rgba(0,255,136,0.2)' } : {}}
            >
              {loadingPlan === plan.id ? '...' : 'Wybierz'}
            </button>
          </div>
        ))}
      </div>

      <p className="text-zinc-600 text-xs text-center mt-10">
        Masz już konto?{' '}
        <Link href="/login" className="text-zinc-400 hover:text-white underline transition-colors">
          Zaloguj się
        </Link>
      </p>
      <p className="text-zinc-700 text-xs text-center mt-2">
        <Link href="/" className="hover:text-zinc-500 transition-colors">← Wróć na stronę główną</Link>
      </p>
    </div>
  )
}
