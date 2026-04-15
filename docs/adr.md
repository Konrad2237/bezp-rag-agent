# Architecture Decision Records

> Dokumentacja kluczowych decyzji architektonicznych z kontekstem, rozważanymi opcjami i konsekwencjami.
>
> Data: 2026-04-14

---

## ADR-001: Wybór architektury systemu

**Status:** Zaakceptowana | **Data:** 2026-04-14

### Kontekst

System składa się z frontendu, backendu (agenci AI, RAG) i bazy danych. Buduje jedna osoba w 3 tygodnie. Docelowo 10-100 użytkowników. Budżet ~300 PLN/mies.

### Rozważane opcje

**Opcja A: Monolit (jeden backend, jeden frontend)**

Jeden serwer FastAPI obsługuje całe API. Frontend jako osobna aplikacja Next.js.

- Zalety: najprostszy deploy, debugging i development. Najtańszy (1 instancja Railway)
- Wady: wszystko pada naraz, skalowanie = skalowanie wszystkiego

**Opcja B: Mikroserwisy (osobny serwis per agent/domena)**

Osobne serwisy: Chat API, RAG Service, Extraction Service, Summarizer Service, Plan Generator.

- Zalety: niezależne skalowanie, izolacja błędów
- Wady: 4-6 instancji = 60-150 PLN hosting, distributed debugging, ogromny overhead dla jednej osoby

**Opcja C: Serverless (funkcje per endpoint)**

Każdy endpoint jako osobna funkcja (Vercel Functions, AWS Lambda).

- Zalety: płacisz za użycie, auto-skalowanie
- Wady: cold start 1-5s (zabija UX czatu), limity timeout (za mało na streaming LLM), vendor lock-in

### Decyzja

**Opcja A: Monolit.** Jeden backend FastAPI na Railway, jeden frontend Next.js na Vercel.

1. Jedna osoba, 3 tygodnie — mikroserwisy to niepotrzebny overhead
2. FastAPI BackgroundTasks — extraction i summarization bez osobnego serwisu
3. Serverless odpada — cold start + timeout na streaming LLM
4. Jeden serwer = 15-25 PLN vs mikroserwisy 4-6x więcej
5. Jeden log, jeden proces, jedno miejsce do debugowania

### Konsekwencje

- **Pozytywne:** Minimalny czas na infra, najprostszy deploy/CI/CD, czytelne w portfolio
- **Negatywne:** Backend pada = pada wszystko (ale Railway ma auto-restart). Long-running requests blokują workera (fix: uvicorn z 2-4 workerami)
- **Migracja:** Powyżej ~500 userów — wydziel background tasks do kolejki (2-3 dni), potem RAG do osobnego serwisu (2-3 dni). Nie wymaga przepisywania kodu

---

## ADR-002: Wybór modeli AI

**Status:** Zaakceptowana | **Data:** 2026-04-14

### Kontekst

System używa AI w czterech miejscach o różnych wymaganiach. Przy 10 userach, ~10 msg/dzień = ~3000 msg/miesiąc.

| Zadanie | Wymagana jakość | Częstotliwość | Wrażliwość na koszt |
|---|---|---|---|
| Rozmowa (Orchestrator) | Wysoka | Każda wiadomość | Średnia |
| Ekstrakcja informacji | Średnia | Każda wiadomość (background) | Wysoka |
| Sumaryzacja | Średnia | Co 10 wiadomości | Wysoka |
| Generowanie planu | Wysoka | Raz na kilka tygodni | Niska |
| Embeddingi (RAG) | N/A | Raz przy ingestion + raz per wiadomość | Wysoka |

### Rozważane opcje

**Opcja A: Jeden model do wszystkiego (Sonnet)**

- Zalety: prostota, spójna jakość
- Wady: przepłacasz za proste zadania ~15x

**Opcja B: Dwa modele — Sonnet + Haiku**

- Zalety: Haiku 15x tańszy, wystarczający do ekstrakcji i sumaryzacji. Oszczędność ~60-70% na background tasks
- Wady: dwa modele do testowania (nieistotne — nie rozmawiają z userem)

**Opcja C: Open source (Llama, Mistral) self-hosted**

- Zalety: zero kosztów API
- Wady: GPU 300+ PLN/mies., gorsza jakość w polskim, wymaga DevOps

**Opcja D: Mieszanka providerów (np. GPT-4o)**

- Zalety: dywersyfikacja
- Wady: dwa API, podwójne testowanie promptów

### Decyzja

**Opcja B: Sonnet + Haiku + OpenAI embeddingi.**

| Zadanie | Model | Uzasadnienie |
|---|---|---|
| Orchestrator | `claude-sonnet-4-6` | Ton, personalizacja, rozumowanie |
| Extraction | `claude-haiku-4-5` | Prosty JSON, 15x tańszy |
| Summarizer | `claude-haiku-4-5` | Streszczenie, Haiku wystarczy |
| Plan Generator | `claude-sonnet-4-6` | Złożone, ale rzadkie |
| Embeddingi | `text-embedding-3-small` | Anthropic nie ma embeddingów |

**Szacunkowy koszt przy 3000 msg/mies.: ~$41 (~170 PLN).** Mieści się w budżecie z zapasem.

### Konsekwencje

- **Pozytywne:** Koszt pod kontrolą, Haiku oszczędza ~60%, jeden provider = jeden SDK
- **Negatywne:** Vendor lock-in na Anthropic. Haiku może czasem źle wyekstrahować (ale walidacja JSON łapie błędy). Dwa providery = dwa billingi
- **Migracja:** Zamiana modelu = przetestowanie promptów (~2-3 dni). Zamiana embeddingów = re-ingestion (~5 minut przy 10k słów)

---

## ADR-003: Strategia obsługi błędów AI

**Status:** Zaakceptowana | **Data:** 2026-04-14

### Kontekst

Modele AI mogą zawieść: halucynacja, błędna ekstrakcja, API failure, malformed output, prompt injection. Każdy typ ma inną częstotliwość i wpływ.

### Rozważane opcje

**Opcja A: Fail silently**

- Zalety: zero kodu
- Wady: błędy się kumulują, nie wiesz że coś nie działa

**Opcja B: Retry + fallback + walidacja (warstwowe)**

- Zalety: system odporny, błędy nie docierają do usera, logi do debugowania
- Wady: więcej kodu i edge case'ów

**Opcja C: Enterprise-grade (circuit breaker, dead letter queue, Sentry)**

- Zalety: bullet-proof
- Wady: 2-3 dni na infra błędów, overkill dla 10 userów

### Decyzja

**Opcja B: Retry + fallback + walidacja** — pragmatyczna wersja.

#### Halucynacja agenta

- Prewencja: PROMPT-01 nakazuje mówić "nie wiem" gdy brak danych w RAG
- Runtime: similarity_score poniżej 0.3 → rag_context = "Brak materiałów"
- Post-hoc: ręczny monitoring 5-10 losowych rozmów dziennie

#### Błędna ekstrakcja (PROMPT-02)

- Parsowanie JSON — fail → log + skip (nie aktualizuj profilu)
- Walidacja wartości — podejrzane zakresy → log + skip
- Konflikty z profilem → zapis do pending_conflicts, agent pyta usera

#### API failure (Anthropic / OpenAI)

- Orchestrator: 1 retry po 2s, potem komunikat "spróbuj ponownie"
- Background tasks: 2 retry z exponential backoff, potem skip
- Embeddingi: 2 retry; fail przy retrieval → odpowiedź bez RAG

#### Malformed output (JSON)

- PROMPT-02: parse fail → log + skip (user nic nie traci)
- PROMPT-03: output pusty lub za długi → zachowaj poprzednie podsumowanie
- PROMPT-04: parse fail → 1 retry, potem komunikat "spróbuj ponownie"

#### Prompt injection

- PROMPT-01 sekcja "OCHRONA PRZED MANIPULACJĄ"
- Wiadomość usera WYŁĄCZNIE jako user message, nigdy w system prompt
- Logowanie podejrzanych odpowiedzi ("jako AI model", "moje instrukcje")

### Konsekwencje

- **Pozytywne:** User nie widzi stack trace, błędne dane nie trafiają do profilu, background tasks mogą failować bez wpływu na UX
- **Negatywne:** Retry dodaje latency (2-4s). Ręczny monitoring nie skaluje się powyżej ~50 userów
- **Migracja:** Sentry (pół dnia), klasyfikator halucynacji (1-2 dni), dedykowany logging (pół dnia)
