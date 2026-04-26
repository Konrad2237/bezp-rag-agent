import Link from 'next/link'
import { AnimatedChatWindow, type Msg } from './components/AnimatedChatWindow'
import { Accordion } from './components/Accordion'

// ─── Data ─────────────────────────────────────────────────────────────────────

const HERO_CONVERSATIONS: Msg[][] = [
  [
    { from: 'user', text: 'Ej, boli mnie bark od tygodnia' },
    { from: 'pitbul', text: 'Pamiętam z ostatniej rozmowy że miałeś z nim problem — kurwa, znowu? Zamieniam wyciskanie:' },
    { from: 'pitbul', text: '✓ Pompki neutral chwyt  4×12\n✓ Fly hantlami  3×15\n✓ Wiosłowanie  4×10\n\nW zakładce Plan masz już podmienione ćwiczenia.' },
  ],
  [
    { from: 'user', text: 'Jem za mało czy za dużo na masę?' },
    { from: 'pitbul', text: 'Mam w bazie że ważysz 78kg. Ile kalorii jesz dziennie?' },
    { from: 'user', text: 'Może z 2000' },
    { from: 'pitbul', text: 'Za mało o jakieś 700 kcal. Podbijamy stopniowo żeby nie zajeść się tłuszczem.' },
  ],
  [
    { from: 'user', text: '3 miesiące trenuję i nic nie widać' },
    { from: 'pitbul', text: 'Mam w bazie że śpisz 6h. To jest Twój problem, nie trening. Kortyzol zjada mięśnie szybciej niż je budujesz.' },
    { from: 'user', text: 'Serio tylko przez sen?' },
    { from: 'pitbul', text: 'Sen i odżywianie to 70% roboty. Ogarnij 7-8h i wróć — wtedy zmieniamy plan.' },
  ],
  [
    { from: 'user', text: 'Jadę na wakacje na 2 tygodnie, nie będzie siłowni' },
    { from: 'pitbul', text: 'Pamiętam że nie lubisz brzuszków — ominam je. Plan hotelowy gotowy:' },
    { from: 'pitbul', text: '✓ Pompki  4×15\n✓ Przysiady  4×20\n✓ Plank  3×45s\n\nW zakładce Plan masz już gotowy plan hotelowy.' },
  ],
]

const PROOF_CONVERSATIONS: Msg[][][] = [
  [
    [
      { from: 'user', text: 'Chcę zbudować masę, od czego zaczynam?' },
      { from: 'pitbul', text: 'Mam w bazie że ważysz 80kg i masz rok stażu. Ile dni w tygodniu możesz trenować?' },
      { from: 'user', text: '4 dni' },
      { from: 'pitbul', text: 'Dobra. Na masę przy 80kg potrzebujesz ~2900 kcal i 160g białka dziennie — masz to ogarnięte?' },
      { from: 'user', text: 'Z jedzeniem to nie jest najgorzej' },
      { from: 'pitbul', text: 'To lecimy. Plan push/pull/nogi/FBW wrzuciłem już do zakładki Plan. Zacznij dziś od push.' },
    ],
  ],
  [
    [
      { from: 'user', text: 'Zjadłem dziś całą pizzę, co teraz' },
      { from: 'pitbul', text: 'Jeden posiłek nic nie zjebał. Jutro wracamy do planu, tyle.' },
    ],
    [
      { from: 'user', text: 'Mogę ćwiczyć z kacem?' },
      { from: 'pitbul', text: 'Możesz, ale jesteś odwodniony i regeneracja jest do niczego. Odpuść dziś.' },
    ],
    [
      { from: 'user', text: 'Nie spałem dziś prawie wcale' },
      { from: 'pitbul', text: 'To nie ćwicz. Kortyzol i tak zniszczy trening — lepiej idź spać.' },
    ],
    [
      { from: 'user', text: 'Boli mnie kolano przy przysiadach' },
      { from: 'pitbul', text: 'Zamieniam na leg press i hack squat. Kolano musi odpocząć — w zakładce Plan masz już zmianę.' },
    ],
  ],
]

const TESTIMONIALS = [
  { name: 'Kuba', age: 18, text: 'Spoko sprawa, pamięta to o czym z nim pisałem i na bieżąco zmienia plan. Za taką cenę naprawdę warto.' },
  { name: 'Justyna', age: 23, text: 'Kiedyś kupowałam plany od trenerów online za sporo kasy. Tu piszę że coś mi nie pasuje i w kilkanaście sekund mam zmianę. Polecam z czystym sumieniem.' },
  { name: 'Dawid', age: 21, text: 'Odpowiada zawsze pod mój profil i nie ocenia. Często mnie łapią fazy na siłkę o 1 w nocy — tu mogę swobodnie pisać i zawsze dostanę konkret.' },
]

const COMPARISON_ROWS = [
  { label: 'Cena', bad: '200 zł/godz.', good: '69 zł/miesiąc' },
  { label: 'Dostępność', bad: 'Umówiona godzina', good: '24/7' },
  { label: 'Pamięta Cię', bad: 'Rzadko', good: 'Zawsze' },
  { label: 'Ocenia', bad: 'Tak', good: 'Nie' },
  { label: 'Zmiana planu', bad: 'Czekasz dni', good: '10 sekund' },
]

const PLANS = [
  { name: 'Tydzień', price: 19, period: 'zł', desc: 'Sprawdź bez zobowiązań.', highlight: false, note: null },
  { name: 'Miesiąc', price: 69, period: 'zł/mies.', desc: 'Taniej niż 4 tygodnie osobno. Pełny dostęp.', highlight: true, note: null },
  { name: '3 miesiące', price: 189, period: 'zł', desc: 'Dla tych co wiedzą że zostają.', highlight: false, note: '63 zł/mies.' },
]

// ─── LandingPage ──────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="bg-[#0D0D0D] text-[#F2EEE8] min-h-screen" style={{ fontFamily: 'Arial, Helvetica, sans-serif' }}>

      {/* Sticky CTA — mobile only */}
      <div className="fixed bottom-0 left-0 right-0 z-50 md:hidden bg-[#0D0D0D]/95 backdrop-blur-sm border-t border-[#1A1A1A] p-3">
        <Link
          href="/login"
          className="block w-full bg-[#00FF88] text-black font-bold text-center py-3.5 rounded-xl text-sm transition-all duration-150 active:scale-[0.97]"
          style={{ boxShadow: '0 0 20px rgba(0,255,136,0.3)' }}
        >
          Zacznij za 19 zł
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex items-center justify-between px-5 py-4 border-b border-[#1A1A1A]">
        <p className="font-bold text-white text-sm tracking-wide">BEZ PIERDOLENIA</p>
        <Link href="/login" className="text-zinc-400 hover:text-white text-sm transition-colors">
          Zaloguj się
        </Link>
      </nav>

      <main>
      {/* Hero */}
      <section className="px-5 py-12 md:py-20">
        <div className="max-w-5xl mx-auto flex flex-col lg:flex-row items-center gap-8 lg:gap-12">
          <div className="flex-1 text-center md:text-left">
            <p className="text-[#00FF88] text-xs font-semibold tracking-widest uppercase mb-4">
              AI Trener Personalny
            </p>
            <h1 className="text-3xl md:text-5xl font-bold text-white leading-tight mb-4">
              Przestań robić<br />treningi bez planu.
            </h1>
            <p className="text-zinc-400 text-base md:text-lg leading-relaxed mb-2">
              Albo masz plan — albo tracisz miesiące bez efektów.
            </p>
            <p className="text-zinc-500 text-sm leading-relaxed mb-8">
              Nie wiesz co robić? To robisz byle co.<br />A potem się dziwisz, że nie rośniesz.
            </p>
            <div className="flex flex-col sm:flex-row items-center md:items-start gap-3">
              <Link
                href="/login"
                className="bg-[#00FF88] text-black font-bold px-8 py-4 rounded-xl text-base w-full sm:w-auto text-center transition-all duration-150 hover:scale-105 active:scale-[0.97] hover:shadow-[0_0_40px_rgba(0,255,136,0.5)]"
                style={{ boxShadow: '0 0 25px rgba(0,255,136,0.25)' }}
              >
                Zacznij za 19 zł →
              </Link>
              <p className="text-zinc-400 text-xs self-center">
                Sprawdź przez tydzień. Bez zobowiązań.
              </p>
            </div>
          </div>

          <div className="flex-shrink-0 w-full lg:w-auto flex justify-center">
            <AnimatedChatWindow
              conversations={HERO_CONVERSATIONS}
              className="w-full max-w-[340px] mx-auto"
            />
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="px-5 py-12 border-t border-[#1A1A1A]">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-8">
            Masz burdel w planie i w głowie.
          </h2>
          <div className="space-y-3">
            {[
              'Jeden mówi FBW, drugi split. TikTok swoje, YouTube swoje.',
              'Plan z neta działa chwilę… potem wracasz do punktu zero.',
              'Trener za 200 zł/h? Albo Cię nie stać, albo nie widzisz sensu.',
              'Robisz treningi… ale nie masz pojęcia czy to w ogóle działa.',
            ].map((text, i) => (
              <div key={i} className="flex items-start gap-3 bg-[#111111] rounded-xl px-4 py-3.5 border border-[#2A2A2A]">
                <span className="text-red-400 mt-0.5 shrink-0 text-sm">✕</span>
                <p className="text-zinc-300 text-sm leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
          <p className="text-zinc-500 text-sm text-center mt-5 leading-relaxed">
            Patrzysz na ludzi obok — rosną, dokładają ciężar.<br />
            Ty robisz to samo co miesiąc temu.
          </p>
        </div>
      </section>

      {/* Jak to działa */}
      <section className="px-5 py-12 border-t border-[#1A1A1A]">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-8">
            Jak to działa
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                n: '01',
                title: 'Klikasz „Zacznij za 19 zł"',
                desc: 'Rejestracja zajmuje 2 minuty. Płatność kartą.',
              },
              {
                n: '02',
                title: 'Odpowiadasz na kilkanaście pytań',
                desc: 'Cel, waga, staż, sprzęt, kontuzje. Pitbul od razu wie o Tobie wszystko.',
              },
              {
                n: '03',
                title: 'Pitbul działa',
                desc: 'Od pierwszej wiadomości masz plan. Bez maili. Bez czekania. Bez pierdolenia.',
              },
            ].map(step => (
              <div key={step.n} className="bg-[#111111] border border-[#2A2A2A] rounded-2xl p-5">
                <p className="text-[#00FF88] text-3xl font-bold mb-3 leading-none">{step.n}</p>
                <p className="text-white font-semibold text-sm mb-2">{step.title}</p>
                <p className="text-zinc-500 text-sm leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Proof */}
      <section className="px-5 py-12 border-t border-[#1A1A1A]">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-3">
            Tak wygląda rozmowa, która zastępuje trenera
          </h2>
          <p className="text-zinc-500 text-sm text-center mb-8">
            Prawdziwe pytania. Prawdziwe odpowiedzi.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-3xl mx-auto">
            {PROOF_CONVERSATIONS.slice(0, 2).map((convos, i) => (
              <AnimatedChatWindow
                key={i}
                conversations={convos}
                compact={i !== 0}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="px-5 py-12 border-t border-[#1A1A1A]">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-white text-center mb-8">
            Co mówią użytkownicy
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {TESTIMONIALS.map((t, i) => (
              <div key={i} className="bg-[#111111] rounded-2xl p-5 border border-[#2A2A2A]">
                <p className="text-zinc-300 text-sm leading-relaxed mb-4">„{t.text}"</p>
                <p className="text-zinc-500 text-xs font-medium">{t.name}, {t.age} lat</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Comparison */}
      <section className="px-5 py-12 border-t border-[#1A1A1A]">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-3">
            Jedna godzina z trenerem = 3 miesiące Pitbula
          </h2>
          <p className="text-zinc-500 text-sm text-center mb-8">
            Serio chcesz dalej przepłacać?
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-[#111111] rounded-2xl p-5 border border-[#2A2A2A]">
              <p className="text-zinc-500 text-xs uppercase tracking-widest mb-5">Trener personalny</p>
              <div className="space-y-4">
                {COMPARISON_ROWS.map(row => (
                  <div key={row.label} className="flex items-center justify-between gap-4">
                    <p className="text-zinc-500 text-sm shrink-0">{row.label}</p>
                    <div className="flex items-center gap-1.5">
                      <span className="text-red-400 text-xs">✕</span>
                      <p className="text-zinc-400 text-sm">{row.bad}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div
              className="bg-[#111111] rounded-2xl p-5"
              style={{ border: '2px solid #00FF88' }}
            >
              <p className="text-[#00FF88] text-xs uppercase tracking-widest mb-5">PITBUL AI</p>
              <div className="space-y-4">
                {COMPARISON_ROWS.map(row => (
                  <div key={row.label} className="flex items-center justify-between gap-4">
                    <p className="text-zinc-400 text-sm shrink-0">{row.label}</p>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[#00FF88] text-xs">✓</span>
                      <p className="text-[#F2EEE8] text-sm font-medium">{row.good}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <p className="text-zinc-400 text-xs text-center mt-5">
            69 zł miesięcznie. Tyle co Netflix i Spotify razem.
          </p>
        </div>
      </section>

      {/* Objekcje */}
      <section className="px-5 py-12 border-t border-[#1A1A1A]">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-white text-center mb-8">Masz wątpliwości?</h2>
          <Accordion />
        </div>
      </section>

      {/* Cennik */}
      <section className="px-5 py-12 border-t border-[#1A1A1A]">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-3">
            Wchodzisz za 19 zł. Nie siądzie — wychodzisz.
          </h2>
          <p className="text-zinc-500 text-sm text-center mb-8">
            Bez długich umów. Bez ukrytych opłat.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PLANS.map((plan, i) => (
              <div
                key={i}
                className="rounded-2xl p-5 flex flex-col"
                style={{
                  border: plan.highlight ? '2px solid #00FF88' : '1px solid #2A2A2A',
                  background: plan.highlight ? '#0D1A10' : '#111111',
                }}
              >
                {plan.highlight && (
                  <span className="text-[#00FF88] text-xs font-bold tracking-widest uppercase mb-3">
                    ★ NAJPOPULARNIEJSZY
                  </span>
                )}
                <p className="text-zinc-400 text-sm mb-1">{plan.name}</p>
                <div className="flex items-baseline gap-1 mb-1">
                  <span className="text-3xl font-bold text-white">{plan.price}</span>
                  <span className="text-zinc-500 text-sm">{plan.period}</span>
                </div>
                {plan.note && (
                  <p className="text-[#00FF88] text-xs mb-2">{plan.note}</p>
                )}
                <p className="text-zinc-500 text-xs mb-5 flex-1">{plan.desc}</p>
                <Link
                  href="/login"
                  className="block text-center py-3 rounded-xl text-sm font-bold transition-all duration-150 active:scale-[0.97]"
                  style={{
                    background: plan.highlight ? '#00FF88' : '#1A1A1A',
                    color: plan.highlight ? '#000' : '#F2EEE8',
                  }}
                >
                  Zacznij teraz
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Ebook */}
      <section className="px-5 py-10 border-t border-[#1A1A1A]">
        <div className="max-w-2xl mx-auto bg-[#111111] rounded-2xl p-6 border border-[#2A2A2A] flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1">
            <p className="text-white font-bold text-base mb-1">Nadal się wahasz?</p>
            <p className="text-zinc-400 text-sm leading-relaxed">
              Weź darmowy ebook{' '}
              <span className="text-[#F2EEE8] font-semibold">BEZ PIERDOLENIA</span>{' '}
              i sam oceń czy wiesz co robisz na siłowni. 90 stron bez mitów i bzdur z TikToka.
            </p>
          </div>
          <a
            href="/ebook.pdf"
            className="bg-[#1A1A1A] border border-[#2A2A2A] text-[#F2EEE8] font-semibold px-5 py-3 rounded-xl text-sm hover:bg-[#2A2A2A] active:scale-[0.97] transition-all duration-150 whitespace-nowrap shrink-0"
          >
            Pobierz za darmo →
          </a>
        </div>
      </section>

      {/* Final CTA */}
      <section className="px-5 py-16 border-t border-[#1A1A1A] text-center">
        <div className="max-w-xl mx-auto">
          <h2 className="text-2xl md:text-4xl font-bold text-white mb-4 leading-tight">
            Dalej możesz zgadywać<br />i kręcić się w kółko…
          </h2>
          <p className="text-zinc-400 text-base mb-8">
            Albo w końcu mieć plan, który daje efekty.
          </p>
          <Link
            href="/login"
            className="inline-block bg-[#00FF88] text-black font-bold px-10 py-4 rounded-xl text-base transition-all duration-150 hover:scale-105 active:scale-[0.97] hover:shadow-[0_0_50px_rgba(0,255,136,0.5)]"
            style={{ boxShadow: '0 0 35px rgba(0,255,136,0.3)' }}
          >
            Zacznij za 19 zł i sprawdź →
          </Link>
          <p className="text-zinc-400 text-xs mt-4">Jeden tydzień. 19 zł. Zero ryzyka.</p>
        </div>
      </section>

      </main>

      {/* Footer */}
      <footer className="px-5 py-8 border-t border-[#1A1A1A] text-center pb-24 md:pb-8">
        <p className="text-zinc-400 text-xs">
          BEZ PIERDOLENIA · AI Trener Personalny ·{' '}
          <Link href="/privacy" className="hover:text-zinc-400 transition-colors">
            Polityka prywatności
          </Link>
        </p>
      </footer>
    </div>
  )
}
