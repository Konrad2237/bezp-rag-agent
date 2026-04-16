# PROMPT STARTOWY — Tydzień 3 (Claude Code)

## Jak zacząć

Przeczytaj te pliki zanim cokolwiek zrobisz:

```
docs/ADR-TYDZIEN-1.md
docs/ADR-TYDZIEN-2.md
docs/mvp-plan.md
```

Możesz też przejrzeć `docs/` w całości jeśli uznasz za potrzebne — szczególnie `architecture.md` i `system-prompt.md`.

---

## Kontekst projektu

Projekt: **BEZ PIERDOLENIA** — AI trener personalny oparty na RAG i agentach.
Ścieżka projektu: `C:\Users\pochw\Desktop\bezp-rag-agent`

Stack: Supabase + FastAPI + LangGraph + Next.js

---

## Stan projektu

**Gotowe (Tydzień 1-2):**
- Supabase: tabele, RLS, pgvector, HNSW index, funkcja match_knowledge
- RAG: agentic chunking (GPT-4o-mini), 19 semantycznych chunków, embeddingi w bazie
- Backend FastAPI: `backend/` z auth, quiz, chat endpointami
- LangGraph: graf z 3 node'ami (fetch_context, orchestrator, post_process)
- Extraction Agent (Haiku) — background task po każdej wiadomości
- Summarizer Agent (Haiku) — background task co 10 wiadomości
- Rate limiter: 30/dzień + 5/min
- Pełny PROMPT-01 v2.1
- GitHub: https://github.com/Konrad2237/bezp-rag-agent

**Gotowe (Tydzień 3 — start):**
- Frontend Next.js zainicjowany w `frontend/` (TS + Tailwind + App Router)
- Dev server działa na localhost:3000

**Do zrobienia (Tydzień 3):**
- Frontend Next.js: 3 strony (login, quiz, chat)
- Deploy backend na Railway
- Deploy frontend na Vercel
- Testy end-to-end z prawdziwym użytkownikiem

---

## Ważne decyzje architektoniczne (nie zmieniaj bez powodu)

- JWT weryfikowany przez `supabase.auth.get_user(token)` — nie przez python-jose
- user_id pochodzi ZAWSZE z JWT, nigdy z body requestu
- RAG jako narzędzie LangGraph (nie pre-fetch) — agent sam decyduje kiedy szukać
- Extraction + Summarizer działają jako background tasks po odpowiedzi agenta
- Supabase service_role_key w backendzie (omija RLS) — klucze w `.env`
- CORS: `ALLOWED_ORIGINS` w `.env` — na dev `http://localhost:3000`

---

## Kolejność deployów (ważne — chicken-and-egg problem)

1. Deploy backend na Railway → dostajesz URL np. `bezp-backend.railway.app`
2. Wpisujesz ten URL do `frontend/.env.local` jako `NEXT_PUBLIC_API_URL`
3. Deploy frontend na Vercel → dostajesz URL np. `bezp.vercel.app`
4. Wracasz do Railway i aktualizujesz `ALLOWED_ORIGINS` na URL Vercela
5. Restart backendu

---

## Specyfikacja frontendu

### Strona 1: Login (`/`)
- Formularz: email + hasło
- Dwa przyciski: "Zaloguj się" i "Zarejestruj się"
- Po zalogowaniu: sprawdź czy user ma profil w `user_profiles`
  - Brak profilu → redirect na `/quiz`
  - Ma profil → redirect na `/chat`
- Token JWT zapisywany w localStorage jako `bezp_token`
- Endpoint rejestracji: `POST /auth/register` → `{ email, password }`
- Endpoint logowania: `POST /auth/login` → `{ email, password }`

### Strona 2: Quiz (`/quiz`)
- Chroniona: niezalogowany → redirect na `/`
- 14 pytań zgrupowanych w 3 kroki (nie 14 osobnych ekranów)

**Krok 1 — Podstawy:**
- Wiek (number, 12-100)
- Płeć (select: mężczyzna/kobieta/inne)
- Waga (number, 30-300 kg)
- Wzrost (number, 100-250 cm)
- Cel (select: masa/redukcja/siła/kondycja)

**Krok 2 — Trening:**
- Poziom zaawansowania (select: początkujący/średniozaawansowany/zaawansowany)
- Dni treningowe w tygodniu (number, 1-7)
- Dostępny sprzęt (select: siłownia/dom_z_sprzętem/dom_bez_sprzętu/kettlebells)
- Czas treningu w minutach (number, 20-180)
- Kontuzje/ograniczenia (textarea, opcjonalne)

**Krok 3 — Styl życia:**
- Godziny snu (number, 3-12)
- Poziom aktywności poza treningiem (select: siedzący/lekko_aktywny/aktywny/bardzo_aktywny)
- Dieta (select: standardowa/wegetariańska/wegańska/bez_glutenu/bez_laktozy)
- Dodatkowe uwagi (textarea, opcjonalne)

- Walidacja zakresów przed wysłaniem
- Endpoint: `POST /quiz/submit` z Bearer tokenem
- Body: wszystkie pola zgodnie z `backend/routers/quiz.py`
- Po sukcesie → redirect na `/chat`

### Strona 3: Chat (`/chat`)
- Chroniona: niezalogowany → `/`, brak profilu → `/quiz`
- Odpowiedzi bez streamingu (zwykły fetch, czekamy na pełną odpowiedź) — streaming można dodać post-MVP
- "Agent pisze..." gdy czeka na odpowiedź
- Disable inputu i przycisku podczas oczekiwania
- Scroll to bottom po każdej wiadomości
- Historia wiadomości trzymana w stanie React (nie w localStorage)
- Endpoint: `POST /chat/` z Bearer tokenem
- Body: `{ "message": "treść" }`
- Przycisk wylogowania → czyści localStorage, redirect na `/`

### Zmienne środowiskowe frontendu
Utwórz plik `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://migoupbssklweifekuct.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<skopiuj z backend/.env>
```

### Wygląd
- Ciemny motyw (czarne/grafitowe tło)
- Minimalistyczny — to MVP, nie landing page
- Tailwind CSS
- Bez zewnętrznych bibliotek UI (shadcn, MUI itp.) — zbędna złożoność dla 3 stron

---

## Zasady współpracy

- Pracujemy krok po kroku — max 2-3 kroki do przodu
- Czytaj pliki projektu zanim coś napiszesz
- Commituj po każdym działającym etapie
- Tłumacz co robisz i dlaczego — właściciel projektu chce rozumieć decyzje
- Styl komunikacji: bezpośredni, bez owijania w bawełnę
- Przy błędach: czytaj logi w terminalu, nie zgaduj

---

## Komendy

```powershell
# Backend (lokalnie)
cd C:\Users\pochw\Desktop\bezp-rag-agent\backend
uvicorn main:app --reload

# Frontend (lokalnie)
cd C:\Users\pochw\Desktop\bezp-rag-agent\frontend
npm run dev

# Git
cd C:\Users\pochw\Desktop\bezp-rag-agent
git add .
git commit -m "opis"
git push
```

---

## Zacznij od

Potwierdź że przeczytałeś ADR-TYDZIEN-1, ADR-TYDZIEN-2 i mvp-plan.md.
Następnie powiedz co robimy jako pierwszy krok i zacznij to robić.
