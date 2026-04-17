import Link from 'next/link'

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 px-4 py-10">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Polityka prywatności</h1>

        <p className="text-zinc-400 text-sm mb-8">
          Ostatnia aktualizacja: kwiecień 2026
        </p>

        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">1. Administrator danych</h2>
          <p className="text-zinc-300 text-sm">
            Administratorem danych osobowych jest Konrad Pochwała, prowadzący serwis
            BEZ PIERDOLENIA (bezp-rag-agent.vercel.app). Kontakt:{' '}
            <a href="mailto:pochwala.konrad@gmail.com" className="underline text-zinc-200">
              pochwala.konrad@gmail.com
            </a>
          </p>
        </section>

        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">2. Jakie dane zbieramy</h2>
          <ul className="text-zinc-300 text-sm list-disc pl-5 space-y-1">
            <li>Adres email i hasło (rejestracja konta)</li>
            <li>Imię i nazwisko</li>
            <li>Dane treningowe: wiek, waga, cel treningowy, poziom zaawansowania, dostępny sprzęt, kontuzje, czas treningu</li>
            <li>Historia rozmów z agentem AI</li>
          </ul>
        </section>

        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">3. Cel przetwarzania</h2>
          <p className="text-zinc-300 text-sm">
            Dane przetwarzamy wyłącznie w celu świadczenia usługi AI trenera personalnego —
            personalizacji porad treningowych, zapamiętywania Twojego progresu i generowania
            planów treningowych.
          </p>
        </section>

        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">4. Podstawa prawna</h2>
          <p className="text-zinc-300 text-sm">
            Przetwarzanie odbywa się na podstawie Twojej zgody (art. 6 ust. 1 lit. a RODO)
            wyrażonej przy rejestracji. Dane zdrowotne (kontuzje, parametry ciała) przetwarzamy
            na podstawie art. 9 ust. 2 lit. a RODO (wyraźna zgoda).
          </p>
        </section>

        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">5. Przechowywanie danych</h2>
          <p className="text-zinc-300 text-sm">
            Dane przechowujemy na serwerach Supabase (region EU West, Londyn) tak długo,
            jak posiadasz aktywne konto. Po usunięciu konta dane są usuwane w ciągu 30 dni.
          </p>
        </section>

        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">6. Twoje prawa</h2>
          <ul className="text-zinc-300 text-sm list-disc pl-5 space-y-1">
            <li>Prawo dostępu do danych</li>
            <li>Prawo do sprostowania danych</li>
            <li>Prawo do usunięcia danych (&quot;prawo do bycia zapomnianym&quot;)</li>
            <li>Prawo do wycofania zgody w dowolnym momencie</li>
            <li>Prawo do wniesienia skargi do UODO (uodo.gov.pl)</li>
          </ul>
          <p className="text-zinc-300 text-sm mt-2">
            Aby skorzystać z powyższych praw, skontaktuj się:{' '}
            <a href="mailto:pochwala.konrad@gmail.com" className="underline text-zinc-200">
              pochwala.konrad@gmail.com
            </a>
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-lg font-semibold mb-2">7. Pliki cookie i tokeny sesji</h2>
          <p className="text-zinc-300 text-sm">
            Serwis używa localStorage przeglądarki do przechowywania tokenu sesji (JWT).
            Token jest usuwany po wylogowaniu. Nie używamy plików cookie do śledzenia ani
            reklam.
          </p>
        </section>

        <Link href="/" className="text-zinc-400 hover:text-white text-sm transition-colors">
          &larr; Wróć do strony głównej
        </Link>
      </div>
    </div>
  )
}
