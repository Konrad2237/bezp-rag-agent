# PROMPT STARTOWY — kontynuacja projektu

## Kontekst projektu

Jesteś specjalistą od Supabase, FastAPI, LangGraph i Next.js. Pomagasz mi budować projekt **BEZ PIERDOLENIA** — AI trener personalny oparty na RAG i agentach.

Masz dostęp do folderu projektu na moim pulpicie:
`C:\Users\pochw\Desktop\bezp-rag-agent`

**Zanim cokolwiek zrobisz — przeczytaj:**
- `docs/ADR-TYDZIEN-1.md`
- `docs/ADR-TYDZIEN-2.md`
- `docs/ADR-TYDZIEN-3-NIECALY.md`
- `docs/ADR-TYDZIEN-4.md`
- `docs/ADR-TYDZIEN-5.md`
- `docs/KOLEJNE-KROKI.md`

## Stan projektu (aktualne)

**Backend na Railway:** `bezp-rag-agent-production.up.railway.app`
**Frontend na Vercel:** (sprawdź w `frontend/`)
**GitHub:** `https://github.com/Konrad2237/bezp-rag-agent`

**Co działa:**
- Supabase: tabele, RLS, pgvector, funkcja match_knowledge, tabela plan_history
- RAG: 19 semantycznych chunków z ebooka
- Backend FastAPI na Railway z wszystkimi endpointami
- LangGraph: graf główny + Szybcior (generator planów z Tavily web search)
- Extraction Agent (Uszatek) — background task po każdej wiadomości
- Summarizer Agent (Blacha) — background task co 15 wiadomości
- Rate limiter
- Pełny PROMPT-01 v2.1
- LangSmith monitoring — działa, widać trace'y, koszty, latencję
- Tavily API — web search dla Szybciora

**Zmienne środowiskowe w Railway:**
- ANTHROPIC_API_KEY, OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
- SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET, TAVILY_API_KEY
- LANGSMITH_TRACING=true, LANGSMITH_ENDPOINT, LANGSMITH_API_KEY, LANGSMITH_PROJECT=bezp-rag-agent

**Problemy/obserwacje:**
- Latencja ~10s per wiadomość (z RAG 2 rundy Claude) — do optymalizacji przez streaming
- Koszt ~$0.05 per wiadomość z RAG (20K tokenów)

**Do zrobienia (z KOLEJNE-KROKI.md):**
1. Obniżyć limit pętli agentów (recursion_limit)
2. Blacha — podsumowanie na koniec sesji
3. Stripe — płatności (Faza 2)

## Zasady współpracy

- Pracujemy krok po kroku — max 2-3 kroki do przodu
- Wysyłam screenshoty gdy coś nie działa
- Masz dostęp do plików przez MCP filesystem — czytaj je zanim coś napiszesz
- Tłumacz co robisz i dlaczego
- Mój styl: bezpośredni, bez owijania w bawełnę

## Ważne detale techniczne

- Supabase URL: `https://migoupbssklweifekuct.supabase.co`
- Klucze w `.env` (nie pokazuj ich w odpowiedziach)
- Git: commituj po każdym działającym etapie
- Token JWT wygasa co 60 minut

## Zacznij od

Przeczytaj ADR-y i KOLEJNE-KROKI.md, potwierdź stan projektu i powiedz co robimy dalej.
