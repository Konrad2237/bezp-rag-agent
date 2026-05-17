# BEZ PIERDOLENIA — AI Trener

> Inteligentny asystent treningowy zbudowany na bazie RAG, LangGraph i modeli Claude. Łączy wiedzę z ebooka o treningu siłowym z profilem użytkownika, by generować spersonalizowane plany i odpowiadać na pytania jak doświadczony kumpel z siłowni.

---

## Spis treści

- [O projekcie](#o-projekcie)
- [Architektura](#architektura)
- [Wymagania](#wymagania)
- [Instalacja](#instalacja)
  - [1. Klonowanie repozytorium](#1-klonowanie-repozytorium)
  - [2. Backend (FastAPI)](#2-backend-fastapi)
  - [3. Frontend (Next.js)](#3-frontend-nextjs)
  - [4. Zmienne środowiskowe](#4-zmienne-środowiskowe)
  - [5. Baza danych (Supabase)](#5-baza-danych-supabase)
  - [6. Ingestion bazy wiedzy](#6-ingestion-bazy-wiedzy)
- [Przykłady użycia](#przykłady-użycia)
  - [Przykład 1 — test agenta w terminalu](#przykład-1--test-agenta-w-terminalu)
  - [Przykład 2 — pełny flow przez API](#przykład-2--pełny-flow-przez-api)
- [Struktura projektu](#struktura-projektu)
- [Technologie i wersje](#technologie-i-wersje)
- [Agenci i prompty](#agenci-i-prompty)
- [Deployment produkcyjny](#deployment-produkcyjny)
  - [Backend — Railway](#backend--railway)
  - [Frontend — Vercel](#frontend--vercel)
  - [Baza danych — Supabase](#baza-danych--supabase)
- [FAQ / Troubleshooting](#faq--troubleshooting)
- [Licencja](#licencja)

---

## O projekcie

**BEZ PIERDOLENIA** to SaaS dla osób zaczynających przygodę z treningiem siłowym. Zamiast ogólnikowych odpowiedzi, aplikacja:

- odpowiada **na podstawie konkretnej bazy wiedzy** (ebook poddany procesowi RAG z semantycznym chunkingiem),
- **pamięta profil użytkownika** — dane z quizu onboardingowego, wiek, cel, poziom zaawansowania, sprzęt,
- **generuje spersonalizowane plany treningowe** dopasowane do możliwości i celu użytkownika,
- **uczy się w trakcie rozmów** — wyciąga z konwersacji nowe dane o użytkowniku (Extraction Agent) i kondensuje długie sesje (Summarizer Agent),
- obsługuje **płatny dostęp** przez Stripe (subskrypcja tygodniowa / miesięczna / kwartalna).

Projekt jest zbudowany jako monolit — jeden backend FastAPI, jeden frontend Next.js — co upraszcza deployment i utrzymanie przy zachowaniu pełnej funkcjonalności.

---

## Architektura

```
                  ┌─────────────────────────────┐
                  │  FRONTEND (Next.js / Vercel) │
                  │  Login │ Quiz │ Chat │ Plan  │
                  └──────────────┬──────────────┘
                                 │ JWT (Supabase Auth)
                                 ▼
        ┌────────────────────────────────────────────────┐
        │           BACKEND (FastAPI / Railway)          │
        │                                                │
        │   /auth  /quiz  /chat  /plan  /settings        │
        │                   /payments                    │
        │                                                │
        │  ┌──────────────────────────────────────────┐  │
        │  │  Pitbul — Orchestrator (Claude Sonnet)  │  │
        │  │  • RAG tool  • Web search tool          │  │
        │  │  • generate_training_plan tool          │  │
        │  │  • edit_plan_exercise tool              │  │
        │  └──────────────────────────────────────────┘  │
        │       │ background          │ background        │
        │       ▼                     ▼                   │
        │  ┌─────────────┐   ┌──────────────────┐        │
        │  │   Uszatek   │   │     Blacha       │        │
        │  │  Extraction │   │   Summarizer     │        │
        │  │  (Haiku)    │   │   (Haiku)        │        │
        │  └─────────────┘   └──────────────────┘        │
        │                                                │
        │  ┌────────────────────────────────────────┐    │
        │  │  Szybcior — Plan Generator (Sonnet)   │    │
        │  └────────────────────────────────────────┘    │
        └────────────────────────────────────────────────┘
                 │               │               │
                 ▼               ▼               ▼
          ┌────────────┐  ┌──────────────┐  ┌──────────┐
          │  Supabase  │  │  Anthropic   │  │  OpenAI  │
          │ PostgreSQL │  │   (Claude)   │  │ Embeddings│
          │ + pgvector │  └──────────────┘  └──────────┘
          └────────────┘
```

**Przepływ danych przy żądaniu `/chat`:**

1. Middleware weryfikuje JWT i sprawdza aktywną subskrypcję.
2. Sprawdzany jest rate limit (per-minute + dzienny) atomowo w Supabase.
3. Pobierany jest profil użytkownika, historia rozmów i podsumowanie sesji.
4. Zapytanie zamieniane jest na embedding (OpenAI), uruchamiane jest wyszukiwanie pgvector (top 5 chunków, threshold 0.3).
5. **Pitbul** (LangGraph + Sonnet) streamuje odpowiedź z dostępem do narzędzi (RAG, web search, generator planu).
6. W tle — **Uszatek** (Haiku) analizuje wymianę i aktualizuje profil użytkownika.
7. Co 15 wiadomości — **Blacha** (Haiku) kondensuje historię do max 250 słów.

---

## Wymagania

### Backend
- Python **3.11+**
- Konto [Supabase](https://supabase.com) z włączonym rozszerzeniem `pgvector`
- Klucze API: [Anthropic](https://console.anthropic.com), [OpenAI](https://platform.openai.com), [Tavily](https://tavily.com)
- Klucze API: [Stripe](https://stripe.com) (dla modułu płatności)

### Frontend
- Node.js **20+**
- npm lub yarn

### Opcjonalne
- [Railway](https://railway.app) — deploy backendu
- [Vercel](https://vercel.com) — deploy frontendu
- [LangSmith](https://smith.langchain.com) — monitoring wywołań LLM

---

## Instalacja

### 1. Klonowanie repozytorium

```bash
git clone https://github.com/[TODO-REPO-URL]/bezp-rag-agent.git
cd bezp-rag-agent
```

### 2. Backend (FastAPI)

```bash
cd backend

# Utwórz i aktywuj wirtualne środowisko
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# Zainstaluj zależności
pip install -r requirements.txt
```

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
```

### 4. Zmienne środowiskowe

Utwórz plik `.env` w katalogu głównym projektu (obok `backend/` i `frontend/`):

```env
# ─── Anthropic (Claude) ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ─── OpenAI (embeddingi RAG) ───────────────────────────────────────────────────
OPENAI_API_KEY=sk-...

# ─── Tavily (web search) ───────────────────────────────────────────────────────
TAVILY_API_KEY=tvly-...

# ─── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...

# ─── Stripe ────────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_WEEK=price_...
STRIPE_PRICE_MONTH=price_...
STRIPE_PRICE_QUARTER=price_...

# ─── Aplikacja ─────────────────────────────────────────────────────────────────
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000
PROMPT_VERSION=v1.0

# ─── Rate limiting ─────────────────────────────────────────────────────────────
RATE_DAILY_LIMIT=100
RATE_PER_MINUTE_LIMIT=5

# ─── LangSmith (opcjonalne, monitoring) ────────────────────────────────────────
# LANGCHAIN_API_KEY=ls__...
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_PROJECT=bezp-rag-agent
```

Dla **frontendu** utwórz `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 5. Baza danych (Supabase)

W panelu Supabase uruchom SQL Editor i wykonaj migracje tworzące tabele:

```sql
-- Włącz rozszerzenie pgvector
create extension if not exists vector;

-- Główne tabele (uproszczona kolejność)
-- Szczegółowy schemat: docs/database.md
create table user_profiles ( ... );
create table knowledge_embeddings ( ... );
create table conversation_sessions ( ... );
create table messages ( ... );
create table conversation_summaries ( ... );
create table training_plans ( ... );
create table plan_history ( ... );
create table pending_conflicts ( ... );
create table subscriptions ( ... );

-- Funkcja do similarity search
create or replace function match_knowledge(
  query_embedding vector(1536),
  match_threshold float,
  match_count int
) returns table (...) ...;
```

> Pełny schemat SQL z wszystkimi kolumnami i indeksami znajdziesz w `docs/database.md`.

### 6. Ingestion bazy wiedzy

Przed uruchomieniem aplikacji musisz wgrać bazę wiedzy do Supabase. Skrypty do ingestion znajdziesz w katalogu `scripts/`:

| Skrypt | Zastosowanie |
|---|---|
| `scripts/ingest.py` | Jeden plik `.docx` → semantyczne chunki (GPT-4o-mini) → embeddingi → Supabase |
| `scripts/ingest_multi.py` | Wiele plików naraz |
| `scripts/upload_chunks.py` | Upload gotowych chunków JSON (bez ponownego chunkowania) |

```bash
# Aktywuj venv backendu, umieść plik źródłowy w katalogu projektu
python scripts/ingest.py
```

Skrypt:
1. Wyciąga tekst z pliku `.docx`
2. Wysyła go do GPT-4o-mini w celu semantycznego podziału na chunki
3. Generuje embeddingi (OpenAI `text-embedding-3-small`)
4. Wgrywa chunki do tabeli `knowledge_embeddings` w Supabase

Prosi o potwierdzenie przed wgraniem — wpisz `t` aby kontynuować.

---

## Uruchomienie lokalne

### Backend

```bash
cd backend
# (venv aktywowane)
uvicorn main:app --reload --port 8000
```

API dostępne pod: `http://localhost:8000`  
Dokumentacja Swagger: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm run dev
```

Aplikacja dostępna pod: `http://localhost:3000`

---

## Przykłady użycia

### Przykład 1 — test agenta w terminalu

Najprostszy sposób na przetestowanie agenta bez uruchamiania pełnego stacku:

```bash
# Aktywuj venv, upewnij się że .env jest skonfigurowany
python scripts/agent.py
```

```
=== AGENT TRENINGOWY — TEST TERMINALOWY ===
Wpisz pytanie (lub 'q' żeby wyjść)

Ty: Ile razy w tygodniu powinienem trenować jako początkujący?

Agent: Jako początkujący zacznij od 3 treningów tygodniowo w systemie FBW (Full Body Workout).
Dlaczego 3? Bo twoje mięśnie potrzebują czasu na regenerację — 48 godzin minimum między sesjami.
Wtorek-czwartek-sobota albo poniedziałek-środa-piątek to klasyki, które działają.
Nie kombinuj z 5 dniami — na początku więcej znaczy gorzej, nie lepiej.
```

Skrypt używa bezpośredniego wywołania RAG + Claude Sonnet — bez pełnej logiki sesji ani Stripe.

---

### Przykład 2 — pełny flow przez API

Poniżej pełna sekwencja żądań HTTP ilustrująca działanie aplikacji (np. przez `curl` lub Postman):

**Krok 1: Rejestracja**

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "jan@example.com", "password": "SuperHaslo123"}'
```

```json
{ "message": "Zarejestrowano pomyślnie" }
```

**Krok 2: Logowanie i pobranie tokenu JWT**

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "jan@example.com", "password": "SuperHaslo123"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Krok 3: Wysłanie wyników quizu onboardingowego**

```bash
curl -X POST http://localhost:8000/quiz/submit \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "wiek": 28,
    "plec": "mezczyzna",
    "waga": 80,
    "wzrost": 180,
    "cel": "masa",
    "poziom": "poczatkujacy",
    "dostepny_sprzet": "silownia",
    "dni_w_tygodniu": 3,
    "czas_na_trening": 60
  }'
```

**Krok 4: Rozmowa z agentem (streaming)**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"message": "Wygeneruj mi plan treningowy"}' \
  --no-buffer
```

Odpowiedź spływa jako stream Server-Sent Events. Agent ma dostęp do profilu użytkownika z quizu i bazy wiedzy RAG, więc wygeneruje plan dopasowany do 3 dni tygodniowo, sylwetki i celu "masa".

**Krok 5: Sprawdzenie wygenerowanego planu**

```bash
curl http://localhost:8000/plan \
  -H "Authorization: Bearer eyJ..."
```

```json
{
  "plan_name": "FBW 3x — Masa dla początkujących",
  "goal": "Budowa masy mięśniowej",
  "frequency_per_week": 3,
  "duration_weeks": 8,
  "days": [
    {
      "day_label": "Trening A",
      "exercises": [
        { "name": "Przysiad ze sztangą", "sets": 3, "reps": "8-10", "notes": "Progresja co tydzień +2,5 kg" },
        { "name": "Wyciskanie na ławce poziomej", "sets": 3, "reps": "8-10", "notes": "" },
        { "name": "Martwy ciąg", "sets": 3, "reps": "5", "notes": "Technika ważniejsza niż ciężar" }
      ]
    }
  ]
}
```

---

## Struktura projektu

```
bezp-rag-agent/
│
├── backend/                        # Serwer API (FastAPI)
│   ├── main.py                     # Punkt wejścia — tworzy aplikację FastAPI, rejestruje routery
│   ├── config.py                   # Inicjalizacja klientów: Supabase, OpenAI, Anthropic
│   ├── middleware.py               # get_current_user (JWT), require_active_subscription
│   ├── requirements.txt            # Zależności Python
│   │
│   ├── routers/                    # Endpointy REST API
│   │   ├── auth.py                 # /auth — rejestracja, logowanie, refresh, /me
│   │   ├── quiz.py                 # /quiz/submit — zapis wyników onboardingu
│   │   ├── chat.py                 # /chat — streaming rozmów z agentem, rate limiting
│   │   ├── plan.py                 # /plan — pobieranie i edycja planu treningowego
│   │   ├── settings.py             # /settings — dane użytkownika, plan
│   │   └── payments.py             # /payments — Stripe checkout, webhook, anulowanie
│   │
│   ├── services/                   # Warstwa usług (logika biznesowa)
│   │   ├── rag.py                  # Embedding + similarity search w pgvector (top_k=5, threshold=0.3)
│   │   ├── search.py               # Web search przez Tavily API
│   │   └── memory.py               # Zarządzanie profil/sesja/historia/podsumowania
│   │
│   └── agents/                     # Agenci AI
│       ├── graph.py                # Pitbul — LangGraph orchestrator (Sonnet) + definicje narzędzi
│       ├── extraction.py           # Uszatek — ekstrakcja danych z rozmów (Haiku)
│       ├── summarizer.py           # Blacha — kondensacja historii rozmów (Haiku)
│       └── plan_generator.py       # Szybcior — generator planu treningowego (Sonnet)
│
├── frontend/                       # Interfejs użytkownika (Next.js)
│   ├── package.json                # Zależności Node.js
│   ├── tsconfig.json               # Konfiguracja TypeScript
│   ├── eslint.config.mjs           # Konfiguracja ESLint
│   ├── postcss.config.mjs          # Konfiguracja PostCSS / Tailwind
│   └── src/
│       └── app/                    # Next.js App Router (strony i komponenty)
│
├── scripts/                        # Narzędzia i skrypty pomocnicze
│   ├── ingest.py                   # Ingestion ebooka: docx → chunki (GPT) → embeddingi → Supabase
│   ├── ingest_multi.py             # Ingestion wielu plików jednocześnie
│   ├── agentic_chunk.py            # Alternatywny chunker (agentic approach)
│   ├── upload_chunks.py            # Upload gotowych chunków JSON do Supabase
│   ├── agent.py                    # Test agenta w terminalu (bez pełnego stacku)
│   ├── test_search.py              # Test wyszukiwania RAG
│   ├── check_pdf.py                # Podgląd zawartości pliku PDF
│   ├── check_docx.py               # Podgląd zawartości pliku DOCX
│   └── generate_adr_docs.py        # Generator dokumentów ADR
│
├── docs/                           # Dokumentacja projektowa (nie deployowana)
│   ├── KOLEJNE-KROKI.md            # Bieżące priorytety, dług techniczny, znane bugi
│   ├── architecture.md             # Kompletna architektura systemu
│   ├── database.md                 # Schemat tabel Supabase z typami i indeksami
│   ├── rag-pipeline.md             # Strategia chunkingu i retrievalu
│   ├── system-prompt.md            # Treść wszystkich 4 promptów systemowych
│   ├── env-variables.md            # Pełna lista zmiennych środowiskowych z opisami
│   ├── security.md                 # Bezpieczeństwo, RODO, wyniki stress-testów
│   ├── quiz.md                     # 22 pytania quizu onboardingowego i schemat profilu
│   ├── langgraph.md                # Architektura grafu LangGraph
│   ├── ux-and-flows.md             # UX i przepływ ekranów
│   ├── testing-and-ops.md          # Strategia testowania i operacje
│   ├── adr.md                      # Architecture Decision Records
│   ├── mvp-plan.md                 # Plan MVP i kryteria sukcesu
│   └── convert_adr.py              # Skrypt do konwersji ADR
│
├── .env                            # Zmienne środowiskowe (w .gitignore — NIE commitować)
├── .gitignore                      # Pliki wykluczone z repozytorium
└── README.md                       # Ten plik
```

---

## Technologie i wersje

### Backend

| Technologia | Wersja | Zastosowanie |
|---|---|---|
| Python | 3.11+ | Język backendu |
| FastAPI | najnowsza | Framework REST API |
| Uvicorn | najnowsza | ASGI server |
| LangGraph | najnowsza | Orkiestracja agentów AI |
| LangChain Anthropic | 0.3.0 | Integracja Claude z LangGraph |
| LangChain Core | najnowsza | Podstawowe abstrakcje LangChain |
| Anthropic SDK | ≥0.39.0, <1.0.0 | Wywołania Claude Sonnet i Haiku |
| OpenAI SDK | najnowsza | Generowanie embeddingów (text-embedding-3-small) |
| Supabase Python | najnowsza | Klient bazy danych i autentykacji |
| Tavily Python | najnowsza | Web search dla agenta |
| Stripe | najnowsza | Obsługa płatności |
| Pydantic | v2 | Walidacja danych |
| python-dotenv | najnowsza | Zmienne środowiskowe |
| httpx | najnowsza | Async HTTP client |
| LangSmith | najnowsza | Monitoring wywołań LLM (opcjonalne) |

### Frontend

| Technologia | Wersja | Zastosowanie |
|---|---|---|
| Next.js | 16.2.4 | Framework React (App Router) |
| React | 19.2.4 | Biblioteka UI |
| TypeScript | ^5 | Typowanie statyczne |
| Tailwind CSS | ^4 | Stylowanie |
| react-markdown | ^10.1.0 | Renderowanie Markdown w czacie |
| remark-gfm | ^4.0.1 | GitHub Flavored Markdown |

### Infrastruktura i usługi zewnętrzne

| Usługa | Zastosowanie |
|---|---|
| Supabase (PostgreSQL + pgvector) | Baza danych, autentykacja, similarity search |
| Anthropic Claude Sonnet | Główny agent (Pitbul) i generator planów (Szybcior) |
| Anthropic Claude Haiku | Extraction Agent (Uszatek) i Summarizer (Blacha) |
| OpenAI text-embedding-3-small | Wektory do RAG |
| Tavily API | Web search w czasie rzeczywistym |
| Stripe | Subskrypcje i płatności |
| Railway | Hosting backendu |
| Vercel | Hosting frontendu |

---

## Agenci i prompty

System używa czterech wyspecjalizowanych agentów AI, każdy z odrębną rolą i modelem:

| Agent | Kod | Model | Rola |
|---|---|---|---|
| **Pitbul** | `agents/graph.py` | Claude Sonnet | Główny orchestrator — rozmawia z użytkownikiem, wywołuje narzędzia (RAG, web search, generator planu), odpowiada strumieniowo |
| **Uszatek** | `agents/extraction.py` | Claude Haiku | Ekstrakcja — po każdej rozmowie analizuje wymianę i aktualizuje profil użytkownika w tle |
| **Blacha** | `agents/summarizer.py` | Claude Haiku | Summarizer — co 15 wiadomości kondensuje historię do max 250 słów |
| **Szybcior** | `agents/plan_generator.py` | Claude Sonnet | Generator planów — tworzy spersonalizowany plan JSON na podstawie profilu i bazy wiedzy |

Decyzja o podziale: **Haiku** dla zadań ekstrakcji i sumaryzacji (15x tańszy od Sonnet, wystarczająca jakość), **Sonnet** tam gdzie jakość rozmowy jest krytyczna.

---

## Deployment produkcyjny

### Backend — Railway

1. Utwórz nowy projekt w [Railway](https://railway.app).
2. Połącz z repozytorium GitHub lub wgraj kod ręcznie.
3. Skonfiguruj **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Ustaw **Root Directory**: `backend`
5. Dodaj wszystkie zmienne środowiskowe z sekcji [Zmienne środowiskowe](#4-zmienne-środowiskowe) (zmień `ENVIRONMENT=production`).
6. Zmień `ALLOWED_ORIGINS` na domenę frontendu (np. `https://twoja-aplikacja.vercel.app`).

Szacowany koszt: **~15–25 PLN/miesiąc** przy planie Hobby.

### Frontend — Vercel

1. Zaloguj się do [Vercel](https://vercel.com) i kliknij **Add New Project**.
2. Importuj repozytorium GitHub.
3. Ustaw **Root Directory**: `frontend`
4. Framework Preset: **Next.js** (wykryje automatycznie)
5. Dodaj zmienne środowiskowe (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` — adres Railway)
6. Kliknij **Deploy**.

### Baza danych — Supabase

1. Projekt na [Supabase](https://supabase.com) — plan Free wystarczy na start.
2. Włącz rozszerzenie `pgvector` w SQL Editor: `create extension if not exists vector;`
3. Wykonaj migracje z `docs/database.md`.
4. Skonfiguruj **Row Level Security (RLS)** według zaleceń z `docs/security.md`.
5. W sekcji **Authentication → Settings** wyłącz "Enable email confirmations" (auto-login po rejestracji nie wymaga potwierdzenia).

### Stripe — konfiguracja webhooków

1. W panelu Stripe utwórz **Webhook Endpoint** wskazujący na: `https://twoj-backend.railway.app/payments/webhook`
2. Subskrybuj zdarzenia: `checkout.session.completed`, `customer.subscription.deleted`, `invoice.payment_failed`
3. Skopiuj **Signing Secret** do zmiennej `STRIPE_WEBHOOK_SECRET`.
4. Utwórz **Products i Prices** dla planów tygodniowego / miesięcznego / kwartalnego i wklej ID do zmiennych `STRIPE_PRICE_*`.

### Health check

Po deployu zweryfikuj działanie:

```bash
curl https://twoj-backend.railway.app/health
# Oczekiwana odpowiedź: {"status": "ok"}
```

---

## FAQ / Troubleshooting

### Backend nie startuje — błąd importu Supabase lub OpenAI

**Problem:** `ModuleNotFoundError: No module named 'supabase'`

**Rozwiązanie:** Upewnij się że masz aktywowane wirtualne środowisko i zainstalowane zależności:
```bash
pip install -r requirements.txt
```

---

### Brak odpowiedzi RAG — agent mówi że nie ma wiedzy na temat

**Problem:** Agent odpowiada że nie ma informacji na dany temat, mimo że temat jest w ebooku.

**Rozwiązanie:** Sprawdź czy baza wiedzy została wgrana:
```bash
python scripts/test_search.py
```
Jeśli zwraca pusty wynik, uruchom ponownie `python scripts/ingest.py`.

---

### Błąd 401 Unauthorized przy wywołaniu `/chat`

**Problem:** `{"detail": "Brak tokenu autoryzacji"}`

**Rozwiązanie:** Token JWT wygasa. Frontend powinien automatycznie odświeżać token przez `POST /auth/refresh`. Przy testach API ręcznie zaloguj się ponownie i użyj nowego tokenu.

---

### Stripe webhook zwraca 400

**Problem:** Płatność przechodzi w Stripe, ale subskrypcja nie aktywuje się w bazie.

**Rozwiązanie:**
1. Sprawdź czy `STRIPE_WEBHOOK_SECRET` jest prawidłowy (Signing Secret, nie Secret Key).
2. Upewnij się że endpoint `POST /payments/webhook` jest dostępny publicznie (nie działa przez localhost bez Stripe CLI).
3. Do lokalnych testów użyj [Stripe CLI](https://stripe.com/docs/stripe-cli): `stripe listen --forward-to localhost:8000/payments/webhook`

---

### CORS error — frontend nie może się połączyć z backendem

**Problem:** `Access to fetch at 'http://...' has been blocked by CORS policy`

**Rozwiązanie:** Ustaw zmienną środowiskową `ALLOWED_ORIGINS` na adres frontendu:
```env
ALLOWED_ORIGINS=https://twoja-aplikacja.vercel.app
```
Przy wielu domenach (np. podgląd Vercel + produkcja): [TODO — sprawdź czy backend obsługuje listę domen].

---

### Agent odpowiada wolno lub request wisi

**Problem:** `/chat` nie odpowiada przez >15 sekund.

**Rozwiązanie:** Możliwy timeout na jednym z zewnętrznych serwisów (Supabase, Tavily, OpenAI). Sprawdź logi Railway (`railway logs`). Znany dług techniczny: brak jawnych timeoutów na wywołaniach zewnętrznych — tymczasowo użyj retry po stronie frontendu.

---

### Rate limit — użytkownik dostaje 429

**Problem:** `{"detail": "Przekroczono limit wiadomości na minutę"}`

**Rozwiązanie:** Domyślny limit to 5 wiadomości/minutę i 100/dziennie. Jeśli testujesz aplikację, zwiększ limity tymczasowo w `.env`:
```env
RATE_PER_MINUTE_LIMIT=20
RATE_DAILY_LIMIT=500
```

---

### Ingestion — skrypt zawiesza się na "czekam na semantyczne chunki"

**Problem:** `python scripts/ingest.py` czeka bez odpowiedzi po wysłaniu do GPT.

**Rozwiązanie:** GPT-4o-mini ma długi czas przetwarzania dla dużych dokumentów (>100 stron). Poczekaj 2–3 minuty. Jeśli ebook jest bardzo duży, użyj `scripts/ingest_multi.py` który przetwarza plik po częściach.

---

### Subskrypcja — badge nie aktualizuje się po płatności

**Problem:** Po udanym Stripe Checkout strona `/settings` nadal pokazuje "Brak subskrypcji".

**Rozwiązanie:** Sprawdź czy webhook Stripe dostarczył zdarzenie `checkout.session.completed` i czy zapisał `subscription_status = 'active'` w Supabase. Możliwe że webhook nie dotarł — sprawdź logi w panelu Stripe → Developers → Webhooks.

---

## Licencja

**Wszelkie prawa zastrzeżone. All Rights Reserved.**

Copyright © 2025 Konrad Pochwała

Kod źródłowy niniejszego projektu jest prywatny i poufny. Zabrania się:

- kopiowania, reprodukowania lub dystrybucji kodu lub jego części,
- używania kodu w projektach komercyjnych lub prywatnych bez pisemnej zgody autora,
- sprzedaży, sublicencjonowania lub przekazywania kodu osobom trzecim,
- tworzenia produktów pochodnych opartych na tym kodzie.

Wszelkie nieuprawnione użycie jest zabronione i może skutkować odpowiedzialnością prawną.

Kontakt w sprawie licencji: pochwala.konrad@gmail.com
