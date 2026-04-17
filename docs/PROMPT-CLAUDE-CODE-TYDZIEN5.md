# PROMPT STARTOWY — Tydzień 5 (Claude Code)

## Kontekst

MVP gotowe i działa na produkcji. Tydzień 4 skończony w 2 dni zamiast planowanych 4 tygodni.

**Stripe i fazy 2-5 z mvp-plan.md odkładamy.**

Priorytet: rozbudowa do prawdziwego multi-agent systemu — dla wartości CV i jakości produktu.

---

## Co mamy teraz

4 byty, ale tylko Pitbul jest prawdziwym agentem:

| Agent | Typ | Narzędzia |
|---|---|---|
| Pitbul (Orchestrator) | Prawdziwy agent — pętla ReAct | search_knowledge, generate_training_plan, edit_plan_exercise |
| Szybcior (Plan Generator) | Pipeline — jedno wywołanie Claude | Brak |
| Uszatek (Extraction Agent) | Pipeline — jedno wywołanie Claude | Brak |
| Blacha (Summarizer) | Pipeline — jedno wywołanie Claude | Brak |

Szybcior, Uszatek i Blacha to "funkcje z LLM w środku" — dostają input, zwracają output, zero autonomii.

---

## Co budujemy w tym tygodniu

### Cel główny

Prawdziwy multi-agent system gdzie każdy agent ma własny ReAct loop i narzędzia.
Na CV: "multi-agent system z LangGraph, supervisor pattern, external tool integrations".

---

### 1. Szybcior → prawdziwy agent

Zamiast jednego strzału do Claude, Szybcior dostaje pętlę i narzędzia:

- `search_knowledge` — sam szuka ćwiczeń w RAG zanim napisze plan
- `get_user_plan_history` — sprawdza poprzednie plany żeby nie powtarzać
- `search_web` (Tavily API) — szuka aktualnych informacji gdy RAG nie wystarczy

Efekt: Szybcior iteruje — szuka → drafuje → waliduje → poprawia. Lepsza jakość planów.

### 2. Uszatek → prawdziwy agent

Teraz zwraca JSON który zewnętrzny kod przetwarza. Po zmianie:

- `update_user_profile` — sam zapisuje do bazy
- `create_conflict` — sam flaguje konflikty
- `search_knowledge` — może zweryfikować twierdzenie usera

Efekt: Uszatek jest autonomiczny, nie potrzebuje "opiekuna" który wykona jego decyzje.

### 3. Blacha → agent z dostępem do danych

- `get_recent_messages` — sam pobiera historię zamiast dostawać ją z zewnątrz
- `get_profile_changes` — widzi co Uszatek zmienił ostatnio
- `update_summary` — sam zapisuje podsumowanie

### 4. Supervisor pattern w LangGraph

Pitbul jako świadomy koordynator który deleguje do subgrafów — każdy agent ma własny graf w LangGraph, Pitbul wie kiedy i do kogo delegować.

### 5. Tavily Search API

Zewnętrzne źródło wiedzy dla agentów — web search gdy RAG nie ma odpowiedzi.
Darmowy tier, gotowa integracja z LangChain (~10 linii kodu).

### 6. Opcjonalnie (jeśli zostanie czas)

- ExerciseDB API — baza ~1300 ćwiczeń z opisami i grupami mięśniowymi
- Nutritionix API — dane żywieniowe jeśli Pitbul ma gadać o diecie

---

## Szacowany czas

2-3 dni robocze przy tempie z poprzednich sesji.

Fundament (LangGraph, Supabase, pattern narzędzi z closures) zostaje bez zmian.
Zmieniamy wewnętrzną logikę agentów, nie przepisujemy stosu.

---

## Czego NIE robimy teraz

- Stripe (Faza 2 z mvp-plan.md)
- Monitoring (Faza 3)
- n8n Automations (Faza 4)
- Landing page (Faza 5)

Wrócimy do tego po multi-agent refaktorze.

---

## Pliki które warto przeczytać przed startem

```
docs/ADR-TYDZIEN-4.md         — co zbudowaliśmy, jak działają agenci teraz
backend/agents/graph.py        — Pitbul + tool_dispatcher + obecne narzędzia
backend/agents/plan_generator.py — Szybcior (do refaktoru)
backend/agents/extraction.py   — Uszatek (do refaktoru)
backend/agents/summarizer.py   — Blacha (do refaktoru)
```

---

## Stan produkcji

- Frontend: https://bezp-rag-agent.vercel.app
- Backend: https://bezp-rag-agent-production.up.railway.app
- Branch: main (Railway i Vercel auto-deployują z main)
