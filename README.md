# Bez Pierdolenia — AI Personal Trainer

> Subskrypcyjna aplikacja webowa z agentem AI pełniącym rolę trenera personalnego.

Agent zna użytkownika (profil z quizu + automatyczne aktualizacje z rozmów), pamięta kontekst między sesjami i odpowiada w oparciu o zweryfikowaną bazę wiedzy treningowej — nie halucynuje. Generuje spersonalizowane plany treningowe i modyfikuje je na żądanie. Zbudowany jako projekt portfoliowy demonstrujący architekturę end-to-end systemu AI z RAG, agentami i subskrypcją.

**Live demo:** [bezp-rag-agent.vercel.app](https://bezp-rag-agent.vercel.app)

---

## Spis treści

- [Funkcjonalności](#funkcjonalności)
- [Jak to działa — flow użytkownika](#jak-to-działa--flow-użytkownika)
- [Architektura](#architektura)
- [Technologie](#technologie)
- [Wymagania](#wymagania)
- [Instalacja lokalna](#instalacja-lokalna)
- [Zmienne środowiskowe](#zmienne-środowiskowe)
- [Struktura projektu](#struktura-projektu)
- [Testowanie](#testowanie)
- [Deployment](#deployment)

---

## Funkcjonalności

- **Agent konwersacyjny (Pitbul)** — Claude Sonnet 4.6 w pętli ReAct z 5 narzędziami: wyszukiwanie w bazie wiedzy (RAG), web search (Tavily), generowanie planu treningowego, edycja ćwiczenia w planie, rozwiązywanie konfliktów profilowych
- **System RAG** — 1374 chunki z 8 źródeł w pgvector, similarity search (cosine, threshold 0.3, top_k=5), embeddingi przez `text-embedding-3-small`
- **Czterowarstwowa pamięć** — profil strukturyzowany, historia ostatnich wymian, podsumowanie starszych rozmów (max 250 słów), oczekujące konflikty profilowe
- **Automatyczna ekstrakcja profilu** — Claude Haiku w tle po każdej wiadomości aktualizuje profil użytkownika na podstawie rozmowy; konflikty z istniejącymi danymi odkładane do rozwiązania przez agenta
- **Generator planów (Szybcior)** — deterministyczny pipeline LangGraph: równoległy fetch kontekstu → Claude Sonnet → JSON planu → zapis do bazy
- **Kondensacja pamięci (Blacha)** — Claude Haiku kompresuje historię rozmów co 15 wiadomości lub przy zamknięciu sesji
- **Subskrypcja Stripe** — checkout, webhook, anulowanie z `cancel_at_period_end`, obsługa wygaśnięcia
- **Rate limiting** — 100 wiadomości dziennie + 5/minutę z atomowym licznikiem in-flight (asyncio.Lock, ochrona przed race condition przy concurrent requestach)
- **Prompt caching** — statyczny prefix promptu cachowany na Anthropic API (TTL 5 min), współdzielony cross-session i cross-user; cached tokens 10x tańsze od standardowych
- **Streaming SSE** — keepalive co 20s (Railway proxy), wykrywanie disconnectu, background tasks niezależne od połączenia
- **Quiz diagnostyczny** — 16-krokowy formularz budujący profil użytkownika przed pierwszą rozmową
- **Monitoring** — LangSmith do śledzenia kosztów i latencji per sesja

---

## Jak to działa — flow użytkownika

1. **Rejestracja** → formularz (email, hasło, imię) → konto w Supabase Auth → pusty profil w bazie
2. **Płatność** → Stripe Checkout (tygodniowy / miesięczny / kwartalny) → webhook ustawia `subscription_status = active`
3. **Quiz diagnostyczny** → 16 pytań (cel, poziom, sprzęt, kontuzje, dostępny czas itd.) → profil zapisany w bazie
4. **Chat z Pitbulem** → agent zna profil, pamięta poprzednie rozmowy, odpowiada w oparciu o bazę wiedzy; po każdej wiadomości automatycznie aktualizuje profil na podstawie tego co user napisał
5. **Generowanie planu** → user prosi o plan → Pitbul wywołuje Szybciora → spersonalizowany plan treningowy pojawia się w zakładce Plan
6. **Ustawienia** → user może edytować profil, zmienić email/hasło, sprawdzić status subskrypcji, anulować subskrypcję

---

## Architektura

```
┌─────────────────────────────────────────────────────┐
│              FRONTEND (Next.js / Vercel)             │
│   Login · Quiz · Chat · Plan · Settings · Pricing   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│              BACKEND (FastAPI / Railway)              │
│                                                      │
│  Auth · Rate Limiter · Stripe Webhooks               │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │              PITBUL (LangGraph ReAct)        │    │
│  │  fetch_context → orchestrator ⇄ tools       │    │
│  │                → post_process               │    │
│  └──────┬──────────────────────┬───────────────┘    │
│         │ background tasks     │ narzędzie           │
│   ┌─────┴──────┐  ┌────────────▼──────────────┐    │
│   ▼            ▼  │    SZYBCIOR (Sonnet)        │    │
│ USZATEK     BLACHA│    LangGraph pipeline       │    │
│ (Haiku)     (Haiku│    setup → agent → finalize │    │
│ ekstrakcja  kond. │    generuje plan JSON        │    │
│ profilu     hist. └───────────────────────────── ┘   │
└──────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              SUPABASE                                │
│  user_profiles · messages · conversation_summaries  │
│  knowledge_embeddings (pgvector) · training_plans   │
│  pending_conflicts · plan_history · profile_changes │
└──────────────────────────────────────────────────────┘
```

**Przepływ jednej wiadomości:**
1. Rate limit + weryfikacja subskrypcji
2. Równoległy fetch: profil + podsumowanie + historia (6 msg) + konflikty + plan
3. Pitbul generuje odpowiedź (wywołując narzędzia jeśli potrzeba) → SSE stream
4. Zapis wiadomości do bazy
5. W tle: Uszatek aktualizuje profil · Blacha kondensuje historię (jeśli ≥15 nowych wiad.)

---

## Technologie

| Warstwa | Technologia |
|---|---|
| Agent | LangGraph · LangChain Anthropic |
| LLM | Claude Sonnet 4.6 (agent, plany) · Claude Haiku 4.5 (ekstrakcja, kondensacja) |
| Embeddingi | OpenAI text-embedding-3-small |
| Web search | Tavily API |
| Backend | Python 3.12 · FastAPI · uvicorn |
| Baza danych | Supabase (PostgreSQL + pgvector + Auth) |
| Płatności | Stripe |
| Frontend | Next.js · Tailwind CSS |
| Hosting | Railway (backend) · Vercel (frontend) |
| Monitoring | LangSmith |
| Automatyzacje | n8n (self-hosted) |

---

## Wymagania

- Python 3.12+
- Node.js 18+
- Konto Supabase z włączonym rozszerzeniem `pgvector`
- Klucze API: Anthropic, OpenAI, Tavily, Stripe

---

## Instalacja lokalna

### Backend

```bash
git clone https://github.com/Konrad2237/bezp-rag-agent.git
cd bezp-rag-agent/backend

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

# Utwórz plik .env.local i uzupełnij zmiennymi (sekcja poniżej)
uvicorn main:app --reload
```

Backend dostępny pod `http://localhost:8000`. Dokumentacja API: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
# Utwórz plik .env.local i uzupełnij zmiennymi (sekcja poniżej)
npm run dev
```

Frontend dostępny pod `http://localhost:3000`.

---

## Zmienne środowiskowe

### Backend (`.env.local`)

```env
# AI
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...   # tylko backend, nigdy frontend
SUPABASE_ANON_KEY=eyJ...

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_WEEK=price_...     # ID ceny z Stripe dashboard
STRIPE_PRICE_MONTH=price_...
STRIPE_PRICE_QUARTER=price_...

# App
ALLOWED_ORIGINS=http://localhost:3000
ENVIRONMENT=development

# Rate limiting (opcjonalne, domyślnie 100/5)
RATE_DAILY_LIMIT=100
RATE_PER_MINUTE_LIMIT=5
```

### Frontend (`.env.local`)

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Struktura projektu

```
bezp-rag-agent/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, routery
│   ├── middleware.py             # JWT auth, weryfikacja subskrypcji
│   ├── config.py                 # klienty Supabase, OpenAI, Anthropic
│   ├── agents/
│   │   ├── graph.py              # Pitbul — LangGraph ReAct agent
│   │   ├── plan_generator.py     # Szybcior — pipeline generowania planów
│   │   ├── extraction.py         # Uszatek — ekstrakcja profilu (Haiku)
│   │   └── summarizer.py         # Blacha — kondensacja historii (Haiku)
│   ├── routers/
│   │   ├── chat.py               # /chat/ — SSE, rate limiting, background tasks
│   │   ├── auth.py               # /auth/ — rejestracja, logowanie, refresh
│   │   ├── payments.py           # /payments/ — Stripe checkout, webhook, anulowanie
│   │   ├── plan.py               # /plan/ — pobieranie planu treningowego
│   │   ├── quiz.py               # /quiz/ — submit quizu diagnostycznego
│   │   └── settings.py           # /settings/ — profil, email, hasło, RODO
│   └── services/
│       ├── rag.py                # similarity search w pgvector
│       ├── search.py             # web search przez Tavily
│       └── memory.py             # operacje na DB: profil, historia, podsumowania
├── frontend/
│   └── src/app/
│       ├── page.tsx              # landing page
│       ├── chat/page.tsx         # interfejs czatu
│       ├── quiz/page.tsx         # quiz diagnostyczny
│       ├── plan/page.tsx         # plan treningowy
│       ├── pricing/page.tsx      # cennik + Stripe checkout
│       └── settings/page.tsx     # ustawienia konta i subskrypcji
├── scripts/
│   ├── ingest.py                 # ingestion chunków do pgvector
│   └── test_search.py            # testowanie similarity search
└── docs/                         # dokumentacja architektury i ADR
```

---

## Testowanie

Pliki testów są lokalne (`.gitignore`) — nie trafiają na GitHub.

```bash
cd backend

# Testy auth i subskrypcji (10 scenariuszy A1-A10)
python -m pytest tests/auth_sub_test.py -v

# Testy bezpieczeństwa (75 przypadków, OWASP Top 10)
python -m pytest tests/security_test.py -v

# Testy jakości RAG z LLM-as-judge (12 scenariuszy)
python tests/rag_quality_test.py

# Stress testy concurrent
python tests/stress_test.py
```

Wyniki ostatnich uruchomień:
- Auth/sub: **10/10 PASS**
- Security: **73/75 PASS** (2 WARN — świadome decyzje architektoniczne)
- RAG quality: **11/12 PASS** (92%) — jedyny nieudany test to false negative metodologiczny

---

## Deployment

### Backend → Railway

1. Połącz repozytorium GitHub z Railway
2. Ustaw zmienne środowiskowe w Railway dashboard
3. Railway automatycznie wykrywa Python i uruchamia `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Frontend → Vercel

1. Połącz repozytorium GitHub z Vercel
2. Ustaw `NEXT_PUBLIC_*` zmienne w Vercel dashboard
3. Vercel automatycznie wykrywa Next.js i deployuje

### Baza danych → Supabase

1. Utwórz projekt w Supabase
2. Włącz rozszerzenie `pgvector` (Database → Extensions)
3. Uruchom migracje SQL (schematy tabel w `docs/database.md`)
4. Uruchom `scripts/ingest.py` żeby zaindeksować bazę wiedzy

---

## Licencja

Projekt prywatny — kod dostępny do wglądu jako portfolio. Nie do użytku komercyjnego bez zgody autora.
