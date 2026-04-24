# ADR — Tydzień 3 (niepełny): Frontend + Deploy

> Dokument decyzji architektonicznych dla Tygodnia 3 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie były problemy i decyzje, co odrzucono i co zostało.
>
> Data: 2026-04-16 | Autor: Konrad + Claude | Status: W toku

---

## Spis treści

1. [Przegląd tygodnia](#1-przegląd-tygodnia)
2. [Frontend — Next.js 16](#2-frontend--nextjs-16)
3. [Rozbudowa backendu](#3-rozbudowa-backendu)
4. [Aktualizacja promptów](#4-aktualizacja-promptów)
5. [Deploy — Railway + Vercel](#5-deploy--railway--vercel)
6. [Problemy i rozwiązania](#6-problemy-i-rozwiązania)
7. [Znane długi techniczne](#7-znane-długi-techniczne)
8. [Zmiany względem planu](#8-zmiany-względem-planu)
9. [Stan na koniec tygodnia](#9-stan-na-koniec-tygodnia)

---

## 1. Przegląd tygodnia

### Co miało powstać (plan)

- Frontend Next.js: 3 strony (login, quiz, chat)
- Deploy backendu na Railway
- Deploy frontendu na Vercel
- Testy end-to-end z prawdziwym użytkownikiem

### Co faktycznie powstało

Frontend działa, deploy działa, aplikacja dostępna pod `https://bezp-rag-agent.vercel.app`. Tydzień nie jest formalnie zakończony — brakuje testów z zewnętrznymi użytkownikami i kilku pomniejszych funkcji.

### Podsumowanie komponentów

| Komponent | Status | Opis |
|---|---|---|
| Strona logowania / rejestracji (/) | ✅ | Przełącznik login/register, imię, nazwisko, potwierdzenie hasła |
| Quiz startowy (/quiz) | ✅ | 3 kroki, walidacja, zgodny ze schema backendu |
| Chat (/chat) | ✅ | Auth check, wysyłanie wiadomości, logout, scroll to bottom |
| Endpoint GET /auth/me | ✅ | Sprawdza czy user ma wypełniony quiz (quiz_completed) |
| Deploy backend na Railway | ✅ | `https://bezp-rag-agent-production.up.railway.app` |
| Deploy frontend na Vercel | ✅ | `https://bezp-rag-agent.vercel.app` |
| CORS produkcyjny | ✅ | ALLOWED_ORIGINS ustawiony na URL Vercel |
| Aktualizacja PROMPT-02 i PROMPT-03 | ✅ | Prompty z docs/system-prompt.md wdrożone w kodzie |

---

## 2. Frontend — Next.js 16

### Stack

- Next.js 16.2.4 (App Router, Turbopack)
- React 19
- Tailwind v4 (`@import "tailwindcss"` w CSS, bez tailwind.config.js)
- TypeScript

### Decyzja: brak bibliotek UI

**Powód:** Minimalizm. 3 strony, dark theme, żadnych animacji. Czyste Tailwind wystarczy — dodatkowa biblioteka to zbędna zależność i potencjalne problemy z kompatybilnością Next.js 16.

### Decyzja: `'use client'` na wszystkich stronach

Wszystkie 3 strony są Client Components. Powód: każda ma interaktywność (formularze, stan, router), więc Server Components nic by tu nie dały.

### Routing i ochrona ścieżek

| Ścieżka | Warunek dostępu | Przekierowanie |
|---|---|---|
| `/` | Zawsze dostępna | — |
| `/quiz` | Wymaga tokenu w localStorage | → `/` jeśli brak |
| `/chat` | Wymaga tokenu + `quiz_completed: true` | → `/` lub `/quiz` |

Logika sprawdzana w `useEffect` przy montowaniu komponentu przez `GET /auth/me`.

### Decyzja: token w localStorage zamiast httpOnly cookie

**Powód:** Prostota implementacji na MVP. HttpOnly cookie wymagałoby dodatkowej logiki odświeżania tokenu po stronie serwera. Na MVP z małą liczbą użytkowników localStorage jest wystarczające.

**Ryzyko:** XSS może wykraść token. Mitygacja: React domyślnie escapuje HTML, nigdzie nie używamy `dangerouslySetInnerHTML`.

### Problem: `next build` — `workStore not initialized`

**Błąd:** `Invariant: Expected workStore to be initialized` podczas statycznej generacji.

**Przyczyna:** Bug w Next.js 16.2.x — `createServerSearchParamsForMetadata()` wywołuje `workAsyncStorage.getStore()` poza kontekstem AsyncLocalStorage podczas prerenderowania `/_not-found` i `/_global-error`.

**Próby naprawy (nieudane):**
- `export const dynamic = 'force-dynamic'`
- `cacheComponents: true` w next.config.ts
- `turbopack.root` w konfiguracji
- Usunięcie Google Fonts
- Minimalizacja stron do `<div>test</div>`
- Webpack zamiast Turbopack

**Rozwiązanie:** Zignorowanie — `npm run dev` nie triggeruje statycznej generacji i działa poprawnie. Vercel buduje przez własny pipeline i build przechodzi bez problemu.

**Lekcja:** Dev server i `next build` zachowują się różnie. Błąd w buildzie lokalnym nie musi oznaczać błędu na Vercelu.

---

## 3. Rozbudowa backendu

### Nowy endpoint: GET /auth/me

```python
@router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    response = supabase.table("user_profiles")
        .select("quiz_completed")
        .eq("user_id", user_id)
        .execute()
    has_profile = len(response.data) > 0 and response.data[0].get("quiz_completed") is True
    return {"user_id": user_id, "has_profile": has_profile}
```

**Cel:** Frontend sprawdza czy user po zalogowaniu ma wypełniony quiz. Jeśli nie — przekierowuje na `/quiz`. Jeśli tak — na `/chat`.

**Ważna zmiana:** Pierwotna wersja sprawdzała tylko czy rekord istnieje (`len > 0`). Po dodaniu imię/nazwisko przy rejestracji rekord powstaje od razu, więc warunek zmieniony na `quiz_completed is True`.

### Rejestracja z imieniem i nazwiskiem

**Decyzja:** Imię i nazwisko zbierane przy rejestracji, nie w quizie.

**Powód:** Bardziej naturalny UX — quiz dotyczy danych treningowych, nie danych osobowych.

**Implementacja:**
- `RegisterRequest` rozszerzony o `imie: str` i `nazwisko: str`
- Po udanej rejestracji tworzony rekord w `user_profiles` z `quiz_completed: False`
- Kolumny `imie` i `nazwisko` dodane do tabeli `user_profiles` w Supabase (TEXT, nullable)

**Problem z duplikatem emaila:** Supabase przy `sign_up` na istniejący email zwraca usera bez `identities` (pusta lista) zamiast błędu — ze względów bezpieczeństwa. Wykrywanie:
```python
if not response.user.identities:
    raise HTTPException(400, "Konto z tym adresem email już istnieje.")
```

### Quiz — poprawka czas_treningu

**Problem:** Frontend wysyłał `"60 minut"`, baza danych miała CHECK constraint akceptujący tylko `'30-45'`, `'45-60'`, `'60-90'`, `'90+'`.

**Przyczyna:** Wartości w dropdownie nie zgadzały się z dokumentacją w `docs/database.md`.

**Fix:** Zmiana wartości opcji w `<select>` na wartości akceptowane przez bazę.

**Lekcja:** Zawsze sprawdzaj `docs/database.md` przed pisaniem formularzy — tam są CHECK constraints.

---

## 4. Aktualizacja promptów

### PROMPT-02 (Extraction Agent) — v2.0

Zaktualizowany do wersji z `docs/system-prompt.md`. Kluczowe zmiany:
- Osobna sekcja `WAŻNE ROZRÓŻNIENIE: WAGA CIAŁA vs CIĘŻAR TRENINGOWY` z konkretnymi przykładami
- Bardziej rozbudowana sekcja `CO NIE JEST WARTE ZAPISANIA`
- Rozbudowana sekcja `WYKRYWANIE KONFLIKTÓW`

### PROMPT-03 (Summarizer Agent) — v1.1

Zaktualizowany do wersji z `docs/system-prompt.md`. Kluczowe zmiany:
- Dodana sekcja `CO WARTO ZACHOWAĆ` z przykładem dobrego podsumowania
- Punkt "O co agent dopytywał (żeby nie pytać dwa razy o to samo)"

**Ważne:** Format JSON w PROMPT-02 i nazwy zmiennych (`{user_profile}`, `{user_message}`, `{agent_response}`) pozostały bez zmian — kod backendu zależy od tych nazw.

---

## 5. Deploy — Railway + Vercel

### Railway (backend)

**Konfiguracja:**
- Root directory: `backend`
- Start command: automatycznie wykryty przez Railway (uvicorn)
- Env variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `ALLOWED_ORIGINS`
- URL: `https://bezp-rag-agent-production.up.railway.app`

**Problem z requirements.txt:** Początkowo brak pliku. Railway nie wiedział jak zainstalować zależności. Fix: dodanie `requirements.txt` do folderu `backend`.

**Problem z wersjami:** Konflikty między `anthropic` i `langchain-anthropic`. Fix: `anthropic>=0.39.0,<1.0.0` + `langchain-anthropic==0.3.0`.

### Vercel (frontend)

**Konfiguracja:**
- Root directory: `frontend`
- Framework: Next.js (auto-wykryty)
- Env variables ustawione ręcznie w panelu (`.env.local` nie trafia na GitHub):
  - `NEXT_PUBLIC_API_URL` = URL Railway
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- URL: `https://bezp-rag-agent.vercel.app`

**Problem ze spacjami w URL:** `NEXT_PUBLIC_API_URL` miało spacje na końcu (`%20%20%20` w requestach). Fix: ręczne usunięcie spacji w panelu Vercel.

### CORS

**Konfiguracja w main.py:**
```python
allow_origins=[os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")]
```

**Wartość na Railway:** `https://bezp-rag-agent.vercel.app`

**Problem podczas deploy:** Tymczasowo ustawiono `*` bo Vercel URL nie był jeszcze znany. Po deploymencie zmieniono na konkretny URL.

**Ważne:** Vercel tworzy preview URL (`bezp-rag-agent-xxx.vercel.app`) różny od głównego (`bezp-rag-agent.vercel.app`). CORS blokuje preview URL — testować zawsze na głównym.

### Supabase — konfiguracja produkcyjna

Po deploymencie konieczna zmiana w **Authentication → URL Configuration**:
- `Site URL` → `https://bezp-rag-agent.vercel.app`
- `Redirect URLs` → dodać `https://bezp-rag-agent.vercel.app`

Bez tego linki potwierdzające email przekierowywały na `localhost:3000`.

---

## 6. Problemy i rozwiązania

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `next build` crash | Bug w Next.js 16.2.x (workStore) | Zignorować lokalnie — Vercel buduje OK |
| `czas_treningu` 422 | Wartości frontendu nie zgadzały się z CHECK constraint w bazie | Zmiana opcji dropdownu na `30-45`, `45-60`, `60-90`, `90+` |
| Stary JS w przeglądarce | Mój background process serwował stary kod na porcie 3000 | `taskkill /F /PID 8788`, restart serwera |
| Spacje w `NEXT_PUBLIC_API_URL` | Wklejenie URL z spacjami w panelu Vercel | Ręczne usunięcie spacji |
| CORS blokuje requesty | Preview URL Vercel inny niż główny | Używać `bezp-rag-agent.vercel.app` |
| Email przekierowuje na localhost | Supabase miał stary Site URL | Zmiana w Auth → URL Configuration |
| `[object Object]` zamiast błędu | `data.detail` to obiekt/tablica, nie string | Obsługa wszystkich typów `detail` w catch bloku |
| Błędy po angielsku | Komunikaty Supabase po angielsku | `.replace()` na kluczowych angielskich frazach |
| `feature/rejestracja-ux` nie zmergowana | Za szybko przeszliśmy do deploy | Merge przed testami produkcyjnymi |
| requirements.txt brak | Plik nie istniał w repo | Stworzenie `backend/requirements.txt` |
| Konflikty wersji anthropic | `langchain-anthropic` wymaga konkretnej wersji | Pinowanie `anthropic>=0.39.0,<1.0.0` |

---

## 7. Znane długi techniczne

| # | Dług | Priorytet | Kiedy naprawić |
|---|---|---|---|
| 1 | RODO: brak checkboxa zgody i polityki prywatności | Wysoki | Przed publicznym launch |
| 2 | Komunikat po rejestracji nie przetestowany (email rate limit Supabase) | Średni | Przy kolejnej sesji testów |
| 3 | `feature/rejestracja-ux` zmergowana ale nie usunięta | Niski | Sprzątanie gałęzi |
| 4 | Token JWT w localStorage (nie httpOnly cookie) | Niski | Post-MVP |
| 5 | Brak obsługi wygasłego tokenu (auto-refresh) | Średni | Przed większą liczbą użytkowników |
| 6 | Brak timeoutu na requesty do backendu (frontend czeka w nieskończoność) | Średni | Tydzień 4 |
| 7 | Disable przycisku "Wyślij" w chacie po wysłaniu | Niski | Tydzień 4 |
| 8 | Markdown w odpowiedziach agenta nie renderowany (surowy tekst) | Średni | Tydzień 4 |

---

## 8. Zmiany względem planu

| Co było w planie | Co zrobiono inaczej | Powód |
|---|---|---|
| Quiz: 22 pytania | Quiz: ~12 pytań | Uproszczenie UX, agent dopytuje resztę |
| Supabase Auth UI jako gotowy komponent | Własny formularz od zera | Supabase Auth UI nie jest kompatybilny z Next.js 16 App Router |
| Build lokalny przed deployem | Deploy bez lokalnego buildu | Bug w Next.js 16.2.x — build lokalnie crashuje, Vercel buduje OK |
| Rejestracja: tylko email + hasło | Rejestracja: email, hasło, imię, nazwisko | Lepszy UX, agent może używać imienia w rozmowie |
| PROMPT-02 i PROMPT-03 bez zmian | Zaktualizowane do wersji z docs | Kod miał starsze wersje niż dokumentacja |

---

## 9. Stan na koniec tygodnia

### Co działa

- Rejestracja z emailem, hasłem, imieniem i nazwiskiem
- Potwierdzenie emaila (Supabase wysyła link)
- Logowanie z polskimi komunikatami błędów
- Quiz 3-krokowy z walidacją
- Chat z agentem — RAG, pamięć, Extraction Agent działa w tle
- Deploy: backend na Railway, frontend na Vercel

### Co nie zostało zrobione z planu tygodnia 3

- Testy z zewnętrznymi użytkownikami (2-3 znajomych bez instrukcji)
- Streaming odpowiedzi agenta (agent pisze całą odpowiedź naraz, nie token po tokenie)
- Renderowanie Markdown w chacie

### Następne kroki (Tydzień 4 lub Faza 1)

1. Testy z prawdziwymi użytkownikami
2. RODO (checkbox zgody, polityka prywatności) — przed publicznym launch
3. Markdown w chacie (`react-markdown`)
4. Training Plan Generator (PROMPT-04 + endpoint + zakładka "Plan")
5. Stripe — płatności i dostęp

### URL produkcyjny

**Frontend:** https://bezp-rag-agent.vercel.app
**Backend:** https://bezp-rag-agent-production.up.railway.app
**Health check:** https://bezp-rag-agent-production.up.railway.app/health
