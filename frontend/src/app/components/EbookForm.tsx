'use client'

import { useState } from 'react'

type State = 'idle' | 'loading' | 'success' | 'error'

export function EbookForm() {
  const [email, setEmail] = useState('')
  const [state, setState] = useState<State>('idle')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) return

    setState('loading')
    try {
      const webhookUrl = process.env.NEXT_PUBLIC_N8N_EBOOK_WEBHOOK_URL
      if (!webhookUrl) throw new Error('brak webhook URL')

      const res = await fetch(webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setState('success')
    } catch {
      setState('error')
    }
  }

  if (state === 'success') {
    return (
      <div className="text-center sm:text-right shrink-0">
        <p className="text-[#00FF88] font-semibold text-sm">Wysłane! Sprawdź skrzynkę.</p>
        <p className="text-zinc-500 text-xs mt-1">Może trafić do spamu.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2 shrink-0 w-full sm:w-auto">
      <input
        type="email"
        required
        placeholder="Twój e-mail"
        value={email}
        onChange={e => setEmail(e.target.value)}
        disabled={state === 'loading'}
        className="bg-[#0D0D0D] border border-[#2A2A2A] text-[#F2EEE8] placeholder-zinc-600 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#00FF88] transition-colors disabled:opacity-50 w-full sm:w-48"
      />
      <button
        type="submit"
        disabled={state === 'loading'}
        className="bg-[#1A1A1A] border border-[#2A2A2A] text-[#F2EEE8] font-semibold px-5 py-3 rounded-xl text-sm hover:bg-[#2A2A2A] active:scale-[0.97] transition-all duration-150 whitespace-nowrap disabled:opacity-50"
      >
        {state === 'loading' ? 'Wysyłam…' : 'Wyślij →'}
      </button>
      {state === 'error' && (
        <p className="text-red-400 text-xs self-center">Coś poszło nie tak. Spróbuj jeszcze raz.</p>
      )}
    </form>
  )
}
