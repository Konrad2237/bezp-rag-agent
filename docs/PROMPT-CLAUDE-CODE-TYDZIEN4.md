# PROMPT STARTOWY — Tydzień 4 (Claude Code)

## Jak zacząć

Przeczytaj te pliki zanim cokolwiek zrobisz:

```
docs/ADR-TYDZIEN-1.md
docs/ADR-TYDZIEN-2.md
docs/ADR-TYDZIEN-3-NIECALY.md
docs/mvp-plan.md
```

Przejrzyj też aktualny stan kodu — szczególnie:
- `frontend/src/app/` — wszystkie 3 strony
- `backend/routers/` — auth, quiz, chat
- `backend/agents/` — graph, extraction, summarizer

---

## Kontekst projektu

Projekt: **BEZ PIERDOLENIA** — AI trener personalny oparty na RAG i agentach.
Ścieżka projektu: `C:\Users\pochw\Desktop\bezp-rag-agent`

Stack: Supabase + FastAPI + LangGraph + Next.js 16 + Tailwind v4

---

## Stan projektu

**Produkcja działa:**
- Frontend: https://bezp-rag-agent.vercel.app
- Backend: https://bezp-rag-agent-production.up.railway.app
- Health check: https://bezp-rag-agent-production.up.railway.app/health

**Co działa end-to-end:**
- Rejestracja (email, hasło, imię, nazwisko) z potwierdzeniem emaila
- Logowanie z polskimi komunikatami błędów
- Quiz 3-krokowy z walidacją → zapis do `user_profiles`
- Chat z agentem — RAG, pamięć, Extraction Agent w tle
- Deploy: Railway (backend) + Vercel (frontend)

**Znane długi techniczne do ogarnięcia:**
- Brak renderowania Markdown w chacie (surowy tekst z gwiazdkami)
- Brak timeoutu na requesty do backendu
- Brak obsługi wygasłego tokenu JWT (auto-refresh)
- RODO: brak checkboxa zgody i polityki prywatności
- Disable przycisku "Wyślij" podczas oczekiwania na odpowiedź agenta

---

## Ważne decyzje architektoniczne (nie zmieniaj bez powodu)

- JWT w localStorage jako `bezp_token` — celowo, httpOnly cookie post-MVP
- user_id pochodzi ZAWSZE z JWT, nigdy z body requestu
- RAG jako narzędzie LangGraph — agent sam decyduje kiedy szukać
- Extraction + Summarizer jako background tasks po odpowiedzi agenta
- CORS: `ALLOWED_ORIGINS=https://bezp-rag-agent.vercel.app` na Railway
- Vercel env variables: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Next.js 16.2.x ma bug z `next build` lokalnie — ignoruj, Vercel buduje OK
- Tailwind v4 — używa `@import "tailwindcss"` w CSS, bez `tailwind.config.js`

---

## Kolejność deployów (przypomnienie)

Każda zmiana w backendzie → push → Railway auto-deployuje z GitHub (branch: main)
Każda zmiana w frontendzie → push → Vercel auto-deployuje z GitHub (branch: main)

Po zmianie `ALLOWED_ORIGINS` na Railway → restart serwisu ręcznie lub poczekaj na auto-restart.

---

## Priorytety na Tydzień 4

### Priorytet 1 — Markdown w chacie
Zainstaluj `react-markdown` i użyj go do renderowania odpowiedzi agenta w `/chat`.
Agent odpowiada z `**bold**`, `- listy`, `### nagłówki` — bez renderowania wygląda brzydko.

### Priorytet 2 — UX czatu
- Disable przycisku "Wyślij" i inputu podczas oczekiwania na odpowiedź (już częściowo zrobione, sprawdź)
- Timeout na fetch do backendu (np. 30 sekund) z komunikatem błędu dla usera
- Obsługa błędu 429 (rate limit) z komunikatem "Dzienny limit wiadomości wyczerpany"

### Priorytet 3 — RODO (przed publicznym launch)
- Checkbox zgody na przetwarzanie danych przy rejestracji (wymagany przed wysłaniem formularza)
- Prosta strona `/privacy` z polityką prywatności (statyczna strona, wystarczy podstawowy tekst)
- Link do `/privacy` przy checkboxie

### Priorytet 4 — Training Plan Generator (Faza 1)
To jest główny feature post-MVP. Wymaga:
- PROMPT-04 z `docs/system-prompt.md` — przeczytaj go zanim zaczniesz
- Nowy endpoint `POST /plan/generate` w backendzie
- Nowa zakładka `/plan` w frontendzie
- Przycisk "Wygeneruj plan" w chacie lub osobna strona

### Priorytet 5 — Stripe (Faza 2)
Płatności. Nie rób tego zanim nie masz co najmniej kilku testowych userów którzy potwierdzili że produkt działa.

---

## Zasady współpracy

- Pracujemy krok po kroku — zacznij od Priorytetu 1
- Czytaj pliki projektu zanim coś napiszesz
- Commituj po każdym działającym etapie na branch `main`
- Tłumacz co robisz i dlaczego
- Styl komunikacji: bezpośredni, bez owijania w bawełnę
- Przy błędach: czytaj logi w terminalu

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

Potwierdź że przeczytałeś ADR-TYDZIEN-3-NIECALY.md i powiedz co widzisz w aktualnym kodzie czatu (`frontend/src/app/chat/page.tsx`). Następnie zacznij od Priorytetu 1 — Markdown w chacie.
