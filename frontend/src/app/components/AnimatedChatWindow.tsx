'use client'

import { useState, useEffect, useRef } from 'react'

export type Msg = { from: 'user' | 'pitbul'; text: string }

function sleep(ms: number) {
  return new Promise<void>(r => setTimeout(r, ms))
}

export function AnimatedChatWindow({
  conversations,
  className = '',
  compact = false,
}: {
  conversations: Msg[][]
  className?: string
  compact?: boolean
}) {
  const [convoIndex, setConvoIndex] = useState(0)
  const [visibleCount, setVisibleCount] = useState(0)
  const [isTyping, setIsTyping] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const isVisibleRef = useRef(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { isVisibleRef.current = entry.isIntersecting },
      { threshold: 0.1 }
    )
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function run() {
      let c = 0
      while (!cancelled) {
        if (!isVisibleRef.current) {
          await sleep(300)
          continue
        }

        setConvoIndex(c)
        setVisibleCount(0)
        setIsTyping(false)
        await sleep(compact ? 600 : 800)

        const convo = conversations[c]
        for (let i = 0; i < convo.length; i++) {
          if (cancelled) return
          if (!isVisibleRef.current) break
          if (convo[i].from === 'pitbul') {
            setIsTyping(true)
            await sleep(compact ? 1200 : 1500)
            if (cancelled) return
            setIsTyping(false)
          }
          setVisibleCount(i + 1)
          await sleep(compact ? 1100 : 1300)
        }

        await sleep(compact ? 5000 : 6000)
        c = (c + 1) % conversations.length
      }
    }

    run()
    return () => { cancelled = true }
  }, [conversations, compact])

  const currentMessages = conversations[convoIndex] || []

  return (
    <div ref={containerRef} className={`bg-[#111111] rounded-2xl border border-[#2A2A2A] overflow-hidden ${className}`}>
      <div className={`flex items-center gap-2 border-b border-[#2A2A2A] ${compact ? 'px-3 py-2.5' : 'px-4 py-3'}`}>
        <div className={`rounded-full bg-[#00FF88] flex items-center justify-center font-bold text-black shrink-0 ${compact ? 'w-6 h-6 text-xs' : 'w-8 h-8 text-sm'}`}>
          P
        </div>
        <div>
          <p className={`text-white font-semibold leading-none mb-1 ${compact ? 'text-xs' : 'text-sm'}`}>Pitbul</p>
          <p className="text-[#00FF88] text-xs">● online 24/7</p>
        </div>
      </div>

      <div className={`flex flex-col justify-end space-y-2.5 overflow-hidden ${compact ? 'p-3 h-[180px]' : 'p-4 h-[250px]'}`}>
        {currentMessages.slice(0, visibleCount).map((msg, i) => (
          <div key={`${convoIndex}-${i}`} className={`flex ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-2xl whitespace-pre-line leading-relaxed ${
                compact ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-2 text-sm'
              } ${
                msg.from === 'user'
                  ? 'bg-[#2A2A2A] text-[#F2EEE8] rounded-br-sm'
                  : 'bg-[#00FF88] text-black font-medium rounded-bl-sm'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-[#1A1A1A] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5">
              {[0, 150, 300].map(d => (
                <span
                  key={d}
                  className="w-2 h-2 bg-[#00FF88] rounded-full animate-bounce"
                  style={{ animationDelay: `${d}ms` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
