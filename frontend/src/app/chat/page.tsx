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
  'Słychać jak trybiki zgrzytają...',
  'Pitbul myśli aż dym z uszu...',
  'Trwa heroiczna walka o myśl...',
  'Zwarcie intelektualne w toku...',
]

function randomPhrase() {
  return THINKING_PHRASES[Math.floor(Math.random() * THINKING_PHRASES.length)]
}

const CHAR_INTERVAL_MS = 18

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function ThinkingIndicator({ phrase }: { phrase: string }) {
  return (
    <div className="flex justify-start">
      <div className="bg-[#111111] border border-[#2A2A2A] rounded-2xl rounded-bl-sm px-4 py-3 flex flex-col gap-2.5">
        <div className="flex items-center gap-1.5">
          {[0, 150, 300].map(d => (
            <span
              key={d}
              className="w-2 h-2 bg-[#00FF88] rounded-full animate-bounce"
              style={{ animationDelay: `${d}ms` }}
            />
          ))}
        </div>
        <p className="text-[#00FF88] text-xs flex flex-wrap" style={{ gap: '1px' }}>
          {phrase.split('').map((char, i) => (
            <span
              key={i}
              style={{
                display: 'inline-block',
                animation: 'wave 1.2s ease-in-out infinite',
                animationDelay: `${i * 0.045}s`,
              }}
            >
              {char === ' ' ? ' ' : char}
            </span>
          ))}
        </p>
      </div>
    </div>
  )
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
  const [isTyping, setIsTyping] = useState(false)
  const [thinkingPhrase, setThinkingPhrase] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)
  const charQueueRef = useRef<string[]>([])
  const typingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const typingTargetIndexRef = useRef<number>(-1)
  const messagesRef = useRef<Message[]>([])

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
    messagesRef.current = messages
    if (messages.length > 0) {
      sessionStorage.setItem('bezp_chat_messages', JSON.stringify(messages))
    }
  }, [messages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
      }
    }
  }, [])

  useEffect(() => {
    const handleBeforeUnload = () => {
      const token = localStorage.getItem('bezp_token')
      if (!token) return
      navigator.sendBeacon(
        `${API_URL}/chat/session-end`,
        new Blob([JSON.stringify({ token })], { type: 'application/json' })
      )
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

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
    let timeoutId = setTimeout(() => controller.abort(), 150000)

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

        clearTimeout(timeoutId)
        timeoutId = setTimeout(() => controller.abort(), 150000)

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.error) throw new Error(data.error)
            if (data.token) {
              if (!started) {
                started = true
                const fullContent = data.token

                const withFull = [
                  ...messagesRef.current,
                  { role: 'assistant' as const, content: fullContent },
                ]
                sessionStorage.setItem('bezp_chat_messages', JSON.stringify(withFull))

                setMessages(prev => {
                  const next = [...prev, { role: 'assistant' as const, content: '' }]
                  typingTargetIndexRef.current = next.length - 1
                  return next
                })
                setLoading(false)
                setIsTyping(true)
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
            // niepełna linia
          }
        }
      }

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
      setIsTyping(false)
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
      setIsTyping(false)
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
    sessionStorage.removeItem('bezp_chat_messages')
    router.push('/')
  }

  if (checking) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <p className="text-zinc-500 text-sm">Sprawdzanie sesji...</p>
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
            <span className="px-3 py-1.5 text-xs rounded-md bg-[#00FF88] text-black font-bold">
              Chat
            </span>
            {(loading || isTyping) ? (
              <span className="px-3 py-1.5 text-xs rounded-md text-zinc-700 cursor-not-allowed">
                Plan
              </span>
            ) : (
              <Link
                href="/plan"
                className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors"
              >
                Plan
              </Link>
            )}
            {(loading || isTyping) ? (
              <span className="px-3 py-1.5 text-xs rounded-md text-zinc-700 cursor-not-allowed">
                Ustawienia
              </span>
            ) : (
              <Link
                href="/settings"
                className="px-3 py-1.5 text-xs rounded-md text-zinc-400 hover:text-white transition-colors"
              >
                Ustawienia
              </Link>
            )}
          </nav>
          <button
            onClick={handleLogout}
            className="hidden sm:inline text-zinc-500 hover:text-zinc-300 text-xs transition-colors"
          >
            Wyloguj
          </button>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <p className="text-zinc-600 text-center text-sm mt-8">
            Napisz do Pitbula — odpowie bez owijania w bawełnę.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-[#2A2A2A] text-[#F2EEE8] rounded-br-sm whitespace-pre-wrap'
                  : 'bg-[#00FF88] text-black rounded-bl-sm prose prose-sm max-w-none'
              }`}
            >
              {msg.role === 'user' ? (
                msg.content
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0 text-black">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1 text-black">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1 text-black">{children}</ol>,
                    li: ({ children }) => <li className="text-black">{children}</li>,
                    strong: ({ children }) => <strong className="font-bold text-black">{children}</strong>,
                    h1: ({ children }) => <h1 className="text-base font-bold mb-1 text-black">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-base font-bold mb-1 text-black">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-bold mb-1 text-black">{children}</h3>,
                    code: ({ children }) => <code className="bg-black/10 px-1 rounded text-xs text-black font-mono">{children}</code>,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ))}
        {loading && <ThinkingIndicator phrase={thinkingPhrase} />}
        {error && <p className="text-red-400 text-sm text-center">{error}</p>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-[#1A1A1A] px-4 py-4 shrink-0">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="Napisz wiadomość..."
            disabled={loading || isTyping}
            className="flex-1 bg-[#111111] border border-[#2A2A2A] text-[#F2EEE8] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#00FF88] disabled:opacity-40 transition-colors placeholder:text-zinc-600"
          />
          <button
            onClick={sendMessage}
            disabled={loading || isTyping || !input.trim()}
            className="bg-[#00FF88] text-black font-bold px-5 py-3 rounded-xl text-sm hover:brightness-110 disabled:opacity-40 transition-all active:scale-[0.97]"
          >
            Wyślij
          </button>
        </div>
      </div>
    </div>
  )
}
