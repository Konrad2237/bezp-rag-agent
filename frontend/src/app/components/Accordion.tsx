'use client'

import { useState } from 'react'

const OBJEKCJE = [
  { q: '"AI nie rozumie mojego ciała"', a: 'Uwzględnia Twoje kontuzje i historię — więc nie robisz głupot, które pogorszą sytuację.' },
  { q: '"To będą jakieś generyczne plany"', a: 'Dostajesz plan pod siebie — nie coś, co pasuje do wszystkich i nikogo.' },
  { q: '"Nie będę z tego korzystać"', a: 'Dlatego wchodzisz za 19 zł, nie 69.' },
  { q: '"AI mnie nie zmotywuje"', a: 'Nie musi. Ma Ci mówić co robić, nie pierdolić cytaty.' },
  { q: '"Nie wiem czy zaufać"', a: 'Dlatego wchodzisz za 19 zł i sprawdzasz sam.' },
]

export function Accordion() {
  const [open, setOpen] = useState<number | null>(null)

  return (
    <div className="space-y-2">
      {OBJEKCJE.map((item, i) => (
        <div key={i} className="border border-[#2A2A2A] rounded-xl overflow-hidden">
          <button
            onClick={() => setOpen(open === i ? null : i)}
            className="w-full flex items-center justify-between px-4 py-4 text-left text-[#F2EEE8] font-medium text-sm hover:bg-[#1A1A1A] active:bg-[#1E1E1E] transition-colors"
          >
            <span>{item.q}</span>
            <span
              className="text-[#00FF88] text-xl font-light ml-4 shrink-0 leading-none transition-transform duration-300 ease-in-out"
              style={{ transform: open === i ? 'rotate(45deg)' : 'rotate(0deg)' }}
            >
              +
            </span>
          </button>
          <div
            className="overflow-hidden transition-all duration-300 ease-in-out"
            style={{ maxHeight: open === i ? '200px' : '0px' }}
          >
            <div className="px-4 pb-4 pt-3 text-zinc-400 text-sm leading-relaxed border-t border-[#2A2A2A]">
              {item.a}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
