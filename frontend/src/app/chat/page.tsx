'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getValidToken } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const THINKING_PHRASES = [
  'Pitbul myśli...',
  'Pitbul wytęża szare komórki...',
  'Słychać jak trybiki w głowie zgrzytają...',
  'Pitbul myśli aż dym z uszu idzie...',
  'Słychać tarcie opon w głowie...',
  'Trwa heroiczna walka o jedną myśl...',
  'Pali się sprzęgło w głowie...',
  'Zwarcie intelektualne w toku...',
]

function randomPhrase() {
  return THINKING_PHRASES[Math.floor(Math.random() * THINKING_PHRASES.length)]
}

const CHAR_INTERVAL_MS = 18 // prędkość pisania — ms na znak

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const saved = sessionStorage.getItem('bezp_chat_messages')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [thinkingPhrase, setThinkingPhrase] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)
  const charQueueRef = useRef<string[]>([])
  const typingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const typingTargetIndexRef = useRef<number>(-1)

  useEffect(() => {
    async function checkAuth() {
      const token = localStorage.getItem('bezp_token')
      if (!token) {
        router.replace('/')
        return
      }
      try {
        const res = await fetch(`${API_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) {
          localStorage.removeItem('bezp_token')
          router.replace('/')
          return
        }
        const data = await res.json()
        if (!data.has_profile) {
          router.replace('/quiz')
          return
        }
      } catch {
        router.replace('/')
        return
      }
      setChecking(false)
    }
    checkAuth()
  }, [router])

  useEffect(() => {
    if (messages.length > 0) {
      sessionStorage.setItem('bezp_chat_messages', JSON.stringify(messages))
    }
  }, [messages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return

    const token = await getValidToken()
    if (!token) {
      router.replace('/')
      return
    }

    setInput('')
    setError('')
    setThinkingPhrase(randomPhrase())
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60000)

    try {
      const res = await fetch(`${API_URL}/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text }),
        signal: controller.signal,
      })

      if (res.status === 429) {
        throw new Error('Dzienny limit wiadomości wyczerpany')
      }
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Błąd odpowiedzi agenta')
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let started = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.error) throw new Error(data.error)
            if (data.token) {
              // Pierwszy token — dopiero teraz pokazuj bąbelek i zacznij pisać
              if (!started) {
                started = true
                setMessages(prev => {
                  const next = [...prev, { role: 'assistant' as const, content: '' }]
                  typingTargetIndexRef.current = next.length - 1
                  return next
                })
                setLoading(false)
                charQueueRef.current = []
                typingIntervalRef.current = setInterval(() => {
                  if (charQueueRef.current.length === 0) return
                  const char = charQueueRef.current.shift()!
                  const targetIdx = typingTargetIndexRef.current
                  setMessages(prev => {
                    if (targetIdx < 0 || targetIdx >= prev.length) return prev
                    const msgs = [...prev]
                    msgs[targetIdx] = {
                      ...msgs[targetIdx],
                      content: msgs[targetIdx].content + char,
                    }
                    return msgs
                  })
                }, CHAR_INTERVAL_MS)
              }
              for (const char of data.token) {
                charQueueRef.current.push(char)
              }
            }
          } catch {
            // niepełna linia — czekaj na więcej danych
          }
        }
      }

      // Poczekaj aż kolejka się opróżni zanim wyczyścimy interval
      await new Promise<void>(resolve => {
        const wait = setInterval(() => {
          if (charQueueRef.current.length === 0) {
            clearInterval(wait)
            resolve()
          }
        }, 50)
      })
    } catch (e: unknown) {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
        typingIntervalRef.current = null
      }
      charQueueRef.current = []
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.role === 'assistant' && last.content === '') return prev.slice(0, -1)
        return prev
      })
      if (e instanceof Error && e.name === 'AbortError') {
        setError('Brak odpowiedzi od serwera — spróbuj ponownie')
      } else {
        setError(e instanceof Error ? e.message : 'Błąd połączenia')
      }
    } finally {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
        typingIntervalRef.current = null
      }
      clearTimeout(timeoutId)
      setLoading(false)
    }
  }

  function handleLogout() {
    localStorage.removeItem('bezp_token')
    localStorage.removeItem('bezp_refresh_token')
    sessionStorage.removeItem('bezp_chat_messages')
    router.push('/')
  }

  if (checking) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <p className="text-zinc-500">Sprawdzanie sesji...</p>
      </div>
    )
  }

  return (
    <div className="h-[100dvh] bg-zinc-950 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="border-b border-zinc-800 px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-white font-bold leading-tight text-sm sm:text-base">BEZ PIERDOLENIA</h1>
          <p className="text-zinc-500 text-xs">z Pitbulem</p>
        </div>
        <div className="flex items-center gap-3">
          <nav className="flex gap-1 bg-zinc-900 rounded p-1">
            <span className="px-3 py-1.5 text-sm rounded bg-white text-black font-medium">
              Chat
            </span>
            {loading ? (
              <span className="px-3 py-1.5 text-sm rounded text-zinc-700 cursor-not-allowed">
                Plan
              </span>
            ) : (
              <Link
                href="/plan"
                className="px-3 py-1.5 text-sm rounded text-zinc-400 hover:text-white transition-colors"
              >
                Plan
              </Link>
            )}
          </nav>
          <button
            onClick={handleLogout}
            className="text-zinc-400 hover:text-white text-xs sm:text-sm transition-colors"
          >
            Wyloguj
          </button>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <p className="text-zinc-600 text-center text-sm mt-8">
            Napisz do swojego AI trenera personalnego
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-white text-black whitespace-pre-wrap'
                  : 'bg-zinc-800 text-zinc-100 prose prose-invert prose-sm max-w-none'
              }`}
            >
              {msg.role === 'user' ? (
                msg.content
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                    li: ({ children }) => <li>{children}</li>,
                    strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                    h1: ({ children }) => <h1 className="text-base font-bold mb-1">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-base font-bold mb-1">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
                    code: ({ children }) => <code className="bg-zinc-700 px-1 rounded text-xs">{children}</code>,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800 text-zinc-400 rounded-lg px-4 py-3 text-sm italic">
              {thinkingPhrase}
            </div>
          </div>
        )}
        {error && <p className="text-red-400 text-sm text-center">{error}</p>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-zinc-800 px-4 py-4">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="Napisz wiadomość..."
            disabled={loading}
            className="flex-1 bg-zinc-900 border border-zinc-700 text-white rounded px-4 py-3 focus:outline-none focus:border-zinc-500 disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="bg-white text-black font-medium px-5 py-3 rounded hover:bg-zinc-200 disabled:opacity-50 transition-colors"
          >
            Wyślij
          </button>
        </div>
      </div>
    </div>
  )
}
