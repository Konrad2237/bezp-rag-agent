# BEZ PIERDOLENIA — AI Trener

> Personalizowany asystent treningowy oparty na RAG i Claude, który odpowiada konkretnie — na podstawie bazy wiedzy, nie z głowy.

---

## Spis treści

- [Co robi](#co-robi)
- [Funkcjonalności](#funkcjonalności)
- [Technologie](#technologie)
- [Jak to działa](#jak-to-działa)
- [Architektura AI](#architektura-ai)
- [Struktura projektu](#struktura-projektu)
- [Czego się nauczyłem](#czego-się-nauczyłem)
- [Autor](#autor)

---

## Co robi

**AI Trener** to webowa aplikacja SaaS, która zastępuje generyczne porady treningowe z internetu spersonalizowanym asystentem. Użytkownik wypełnia quiz onboardingowy (cel, poziom zaawansowania, dostępny sprzęt, wyniki siłowni), po czym rozmawia z trenerem odpowiadającym na podstawie bazy wiedzy z książek i badań naukowych — nie wymyśla, lecz cytuje źródła. Aplikacja pamięta profil użytkownika między sesjami, generuje gotowe plany treningowe i samodzielnie aktualizuje swoją wiedzę o użytkowniku w trakcie każdej rozmowy. Dostęp płatny przez Stripe: 19 / 69 / 189 PLN (tydzień / miesiąc / kwartał).

---

## Funkcjonalności

- **Chat z AI trenerem** — streaming rozmowy z Claude Sonnet 4.6, odpowiedzi zakorzenione w bazie wiedzy RAG. Agent sam decyduje kiedy przeszukać bazę, kiedy wyszukać w sieci, a kiedy wygenerować plan
- **Quiz onboardingowy** — 22 pytania zbierające profil użytkownika (cel, wiek, waga, poziom, sprzęt, wyniki na ćwiczeniach bazowych). Dane trafiają do bazy i są dołączane do każdego requestu
- **Generowanie planu treningowego** — Szybcior (pipeline Claude Sonnet) tworzy pełny plan JSON: ćwiczenia, serie, powtórzenia, progresja, notatki. Plan można edytować przez chat
- **Aktualizacja profilu w tle** — po każdej rozmowie Uszatek (Claude Haiku) wyciąga z niej nowe informacje o użytkowniku i aktualizuje profil bez pytania
- **Kondensacja historii** — co 15 wiadomości Blacha (Claude Haiku) tworzy podsumowanie sesji (max 250 słów), żeby agent zawsze miał kontekst nawet po długich rozmowach
- **Strona ustawień** — zmiana emaila, hasła, 18 pól profilu, podgląd planu, usunięcie konta (kaskada 8 tabel)
- **Subskrypcja Stripe** — checkout, webhook, anulowanie z zachowaniem dostępu do końca okresu rozliczeniowego
- **Rate limiting** — 5 wiadomości/minutę i 100/dzień, atomic check przez `asyncio.Lock` zapobiegający race condition przy równoległych requestach

---

## Technologie

### Backend

| Narzędzie | Wersja | Do czego |
|---|---|---|
| Python | 3.11+ | Język backendu |
| FastAPI | najnowsza | REST API + SSE streaming |
| LangGraph | najnowsza | Graf agenta Pitbul (ReAct loop z narzędziami) |
| langchain-anthropic | najnowsza | Integracja Claude z LangGraph |
| Anthropic SDK | ≥0.39.0,<1.0.0 | Wywołania Claude z prompt caching |
| OpenAI SDK | najnowsza | Embeddingi do RAG (text-embedding-3-small) |
| Supabase Python | najnowsza | Klient bazy danych i autentykacji |
| Stripe | najnowsza | Płatności i subskrypcje |
| Tavily Python | najnowsza | Web search dla agenta |
| httpx | najnowsza | Async HTTP (weryfikacja hasła przez gotrue API) |
| Pydantic | v2 | Walidacja requestów |
| LangSmith | najnowsza | Tracing wywołań LLM (opcjonalne) |

### Frontend

| Narzędzie | Wersja | Do czego |
|---|---|---|
| Next.js | ^16.2.4 | Framework (App Router) |
| React | 19.2.4 | UI |
| TypeScript | ^5 | Typowanie |
| Tailwind CSS | ^4 | Stylowanie |
| react-markdown | ^10.1.0 | Renderowanie odpowiedzi agenta w Markdown |
| remark-gfm | ^4.0.1 | GitHub Flavored Markdown |

### Infrastruktura i serwisy zewnętrzne

| Serwis | Do czego |
|---|---|
| Supabase (PostgreSQL + pgvector) | Baza danych, autentykacja, similarity search (HNSW) |
| Anthropic Claude Sonnet 4.6 | Główny agent (Pitbul) + generator planów (Szybcior) |
| Anthropic Claude Haiku 4.5 | Ekstrakcja profilu (Uszatek) + sumaryzacja (Blacha) |
| OpenAI text-embedding-3-small | Wektory RAG (1536 dim, 1364 chunki z 8 źródeł) |
| Tavily | Web search w czasie rzeczywistym |
| Stripe | Subskrypcje |
| Railway | Hosting backendu |
| Vercel | Hosting frontendu |

---

## Jak to działa

### Flow od inputu do outputu

```
Użytkownik wpisuje wiadomość
        │
        ▼
[middleware.py] Weryfikacja JWT
  run_in_threadpool(supabase.auth.get_user) — nie blokuje event loop
  require_active_subscription → 403 jeśli brak aktywnej subskrypcji
        │
        ▼
[chat.py] Atomic rate limit check
  asyncio.Lock + _in_flight dict
  DB_count + in_flight[user_id] >= limit? → 429
        │
        ▼
[graph.py fetch_context] Równoległe pobieranie (ThreadPoolExecutor, 6 workerów):
  profil użytkownika, historia 6 wiadomości, podsumowanie sesji, pending_conflicts
        │
        ▼
[graph.py — Pitbul] LangGraph StateGraph (ReAct loop)
  fetch_context → orchestrator → tools ↔ orchestrator → post_process

  Dostępne narzędzia:
  • search_knowledge_tool  →  pgvector RPC match_knowledge() (top_k=5, threshold=0.3)
  • search_web_tool         →  Tavily
  • generate_training_plan  →  wywołuje Szybcior (osobny pipeline)
  • edit_plan_exercise      →  UPDATE w tabeli training_plans
  • resolve_conflict        →  rozwiązanie sprzeczności w profilu
        │
        ▼
[chat.py] SSE stream — cała odpowiedź w jednej paczce na końcu
  keepalive `: keepalive` co 20s (asyncio.shield + timeout)
  Disconnect? → agent_task.cancel() + asyncio.create_task(background_tasks)
        │
        ▼
[BackgroundTasks — w tle po odpowiedzi]
  save_messages()      →  tabela messages (null byte sanitization)
  extraction.py        →  Uszatek (Haiku): 1 wywołanie, JSON {updates, conflicts} → user_profiles
  summarizer.py        →  Blacha (Haiku): co 15 wiadomości, max 250 słów → conversation_summaries
```

### Kluczowe decyzje techniczne

**`ainvoke` zamiast `astream` w LangGraph**  
Frontend animuje "pisanie" przez CSS — backend zwraca całą odpowiedź w jednej paczce SSE (`data: {"token": "..."}`). Upraszcza obsługę tool calls w strumieniu i eliminuje potrzebę agregowania tokenów po stronie klienta.

**Haiku dla Uszatka i Blachy, Sonnet dla Pitbula i Szybciora**  
Ekstrakcja JSON z rozmowy i sumaryzacja tekstu nie wymagają jakości Sonnet. Haiku jest ~15x tańszy — przy każdej wiadomości te dwa wywołania są obowiązkowe, więc koszt ma bezpośredni wpływ na marżę.

**Szybcior jako pipeline, nie agent**  
Generowanie planu to deterministyczny przepływ: pobierz RAG → wstrzyknij kontekst → generuj JSON. `_szybcior_setup` node pre-injectuje wszystko do HumanMessage, agent generuje w jednym wywołaniu bez tool calls. LangGraph używany tylko dla retry logic przy pustym outputcie.

**Osobny `supabase_admin` dla wszystkich zapisów DB**  
Po `supabase.auth.sign_up()` klient Supabase zmienia wewnętrzny token, co powoduje naruszenia RLS przy zapisach. `supabase` (anon key) — tylko auth; `supabase_admin` (service_role) — wszystkie zapisy do DB. Rozdzielenie w `config.py`, efekt w całym backendzie.

**Prompt caching Anthropic**  
Statyczna część system promptu Pitbula i Szybciora oznaczona `cache_control: ephemeral`. Cache TTL 5 minut — przy częstych requestach oszczędza ~80% kosztów tokenów wejściowych na statycznym kontekście.

---

## Architektura AI

System składa się z czterech komponentów AI. Tylko jeden z nich jest prawdziwym agentem.

---

### Pitbul — główny agent (`agents/graph.py`) · Claude Sonnet 4.6

Jedyny komponent z prawdziwą pętlą decyzyjną. Zbudowany jako LangGraph `StateGraph` z 4 węzłami: `fetch_context → orchestrator → tools ↔ orchestrator → post_process`. Przy każdym requestcie dostaje profil użytkownika, ostatnie 6 wiadomości, podsumowanie sesji i listę nierozwiązanych sprzeczności w profilu. Sam decyduje które narzędzie wywołać (i czy w ogóle), ile razy i kiedy zakończyć.

**Narzędzia Pitbula:**

| Narzędzie | Co robi |
|---|---|
| `search_knowledge_tool` | Similarity search w pgvector — odpytuje 1364 chunki z 8 źródeł naukowych (top_k=5, threshold=0.3) |
| `search_web_tool` | Tavily API — dla pytań spoza bazy wiedzy, np. aktualne badania lub sprzęt |
| `generate_training_plan` | Wywołuje Szybciora i zwraca wygenerowany plan treningowy |
| `edit_plan_exercise` | Modyfikuje konkretne ćwiczenie w planie (UPDATE w tabeli training_plans) |
| `resolve_conflict` | Rozwiązuje sprzeczność wykrytą przez Uszatka — aktualizuje profil po potwierdzeniu przez użytkownika |

---

### Szybcior — generator planów (`agents/plan_generator.py`) · Claude Sonnet 4.6

Nie jest agentem — to deterministyczny pipeline LangGraph bez tool calls. Węzeł `setup` pre-injectuje kontekst RAG, historię poprzednich planów i podsumowanie sesji bezpośrednio do HumanMessage. Model generuje pełny plan jako JSON w jednym wywołaniu. LangGraph używany wyłącznie do obsługi retry gdy model zwróci pusty output (limit 5 prób).

---

### Uszatek — ekstrakcja profilu (`agents/extraction.py`) · Claude Haiku 4.5

Pojedyncze wywołanie LLM uruchamiane w tle (`BackgroundTasks`) po każdej wymianie wiadomości. Dostaje ostatnią wymianę (user + agent) i aktualny profil użytkownika. Zwraca JSON:

```json
{
  "updates": [{"field": "waga", "value": "85"}],
  "conflicts": [{"field": "poziom", "issue": "napisał że jest początkującym, ale ma ławkę 100 kg"}]
}
```

`updates` trafiają od razu do `user_profiles`. `conflicts` lądują w `pending_conflicts` — Pitbul zapyta o nie przy kolejnej okazji.

---

### Blacha — sumaryzacja historii (`agents/summarizer.py`) · Claude Haiku 4.5

Pojedyncze wywołanie LLM uruchamiane gdy nazbierało się 15 niepodsumowanych wiadomości. Odpala się również gdy użytkownik zamknie kartę (sendBeacon → `/chat/session-end`) lub gdy klient rozłączy się podczas generowania. Dostaje ostatnie 15 wiadomości i poprzednie podsumowanie. Zwraca tekst max 250 słów, który Pitbul dostaje jako część kontekstu przy każdym kolejnym requestcie.

---

## Struktura projektu

```
bezp-rag-agent/
│
├── backend/
│   ├── main.py                  # Punkt wejścia FastAPI, CORS, rejestracja routerów
│   ├── config.py                # Klienty: supabase (anon), supabase_admin (service_role), openai
│   ├── middleware.py            # get_current_user (JWT + threadpool), require_active_subscription
│   ├── requirements.txt
│   │
│   ├── routers/
│   │   ├── auth.py              # /auth — rejestracja, logowanie, /me, refresh
│   │   ├── quiz.py              # /quiz/submit — zapis 22 pól profilu onboardingowego
│   │   ├── chat.py              # /chat — SSE, rate limiting (asyncio.Lock), /session-end
│   │   ├── plan.py              # /plan — GET plan, POST generate (wywołuje Szybciora)
│   │   ├── settings.py          # /settings — profil (18 pól), email, hasło, DELETE konta
│   │   └── payments.py          # /payments — Stripe checkout, webhook (3 eventy), anulowanie
│   │
│   ├── services/
│   │   ├── rag.py               # search_knowledge(): embedding → pgvector RPC match_knowledge()
│   │   ├── search.py            # search_web(): Tavily API
│   │   └── memory.py            # save_messages(), get_conversation_history(), summaries, profile
│   │
│   └── agents/
│       ├── graph.py             # Pitbul — LangGraph ReAct, 5 narzędzi, prompt caching
│       ├── extraction.py        # Uszatek — 1 wywołanie Haiku → JSON {updates, conflicts} → DB
│       ├── summarizer.py        # Blacha — 1 wywołanie Haiku → max 250 słów summary → DB
│       └── plan_generator.py    # Szybcior — LangGraph pipeline bez tool calls, Sonnet, JSON planu
│
├── frontend/
│   └── src/app/
│       ├── page.tsx             # Landing page (publiczna)
│       ├── login/               # Logowanie / rejestracja
│       ├── quiz/                # Onboarding — 22 pytania
│       ├── chat/                # Główny widok czatu, SSE reader, sessionStorage
│       ├── plan/                # Widok i edycja planu treningowego
│       ├── settings/            # Profil, subskrypcja, usunięcie konta
│       └── pricing/             # Strona cenowa Stripe
│
├── scripts/
│   ├── ingest.py                # docx → chunki (GPT-4o-mini) → embeddingi → Supabase
│   ├── ingest_multi.py          # Ingestion wielu plików jednocześnie
│   ├── upload_chunks.py         # Upload gotowych chunków JSON z pominięciem LLM chunkera
│   ├── agent.py                 # Test agenta w terminalu (bez pełnego stacku)
│   └── test_search.py           # Test RAG search — sprawdzenie co zwraca pgvector
│
└── docs/                        # ADR, architektura, schemat DB, system prompty (nie deployowane)
```

---

## Czego się nauczyłem

### Różnica między "chain of prompts" a prawdziwym agentem

Przed tym projektem "agent AI" kojarzył mi się z wywołaniem LLM w pętli. LangGraph nauczył mnie czym faktycznie jest ReAct: model widzi wyniki narzędzi i sam decyduje co dalej — nie po z góry ustalonej ścieżce, lecz na podstawie tego co dostał. Pitbul może wywołać `search_knowledge_tool` trzy razy z różnymi zapytaniami, potem `search_web_tool`, a na koniec stwierdzić że ma wystarczająco i odpowiedzieć. Ta autonomia jest użyteczna dokładnie tam gdzie jest nieprzewidywalność — przy pytaniach treningowych zakres potrzebnej wiedzy jest za każdym razem inny.

### RAG to nie tylko "embeddingi + search"

Strategia chunkowania ma większy wpływ na jakość niż threshold czy top_k. Naiwne dzielenie po 500 znakach rozrywa kontekst w losowych miejscach — zdanie zaczyna się w jednym chunku, kończy w drugim. Wybrałem semantyczne chunkowanie przez GPT-4o-mini: model sam wykrywa przeskoki tematu i tnie tam. 1364 chunki z 8 źródeł, HNSW index w pgvector, threshold 0.3 żeby odrzucać słabe trafienia zamiast zwracać cokolwiek. Testy jakości (LLM-as-judge) pokazały 5/5 na grounding — agent podaje konkretne liczby i mechanizmy, nie ogólniki.

### Async Python na produkcji ≠ "używam async def"

`supabase-py` jest synchronicznym klientem. Wywołany bezpośrednio w `async def` middleware blokuje event loop FastAPI — każdy request czeka na zakończenie poprzedniego. `run_in_threadpool()` przenosi synchroniczne I/O na thread pool i odblokowuje event loop. To samo z rate limiterem: "wystarczająco szybkie" nie znaczy "atomowe" — 8 równoległych requestów wszystkie odczytały `count=0` przed zapisem. Dopiero `asyncio.Lock` + słownik in-flight dało prawdziwy atomic check.

### Koszt jako wymiar architektoniczny, nie afterthought

Pierwotnie wszystkie 4 komponenty były agentami na Claude Sonnet. Po refaktorze Uszatek i Blacha działają na Haiku (deterministyczne zadania: ekstrakcja JSON i sumaryzacja nie potrzebują Sonnet). Statyczne bloki systemu promptu Pitbula i Szybciora mają `cache_control: ephemeral` — Anthropic cache TTL 5 minut, przy częstych requestach to ~80% oszczędności na tokenach wejściowych. Razem obniżyło koszt per-wiadomość o ~70% bez widocznej różnicy w jakości.

### Kiedy LangGraph jest overkill

Uszatek i Blacha zaczęły jako pełne agenty LangGraph — własny StateGraph, własny model, własne węzły. W tygodniu 9 zastąpiłem je pojedynczym `model.invoke([SystemMessage, HumanMessage])`. Graf z jednym węzłem i bez narzędzi to overhead bez żadnej korzyści. Nauczyłem się pytać: "czy ten komponent musi *decydować* o czymś w trakcie działania?" — jeśli nie, to jest wywołanie LLM, nie agent.

### Zewnętrzne API się zmieniają, trzeba to zakładać z góry

stripe-python v5 usunął `.get()` z `StripeObject` — kod crashował przy każdym webhooks evencie. Stripe zmienił strukturę odpowiedzi `Subscription` w API 2026-04-22. supabase-py v2 zmienił chainowanie `.update().eq()` — `.select()` przestało działać na zwróconym builderze. Każda z tych zmian zepsuła działający kod bez ostrzeżenia. Wniosek: izolować dostęp do danych zewnętrznych za cienką warstwą (własna funkcja parsująca), nie rozsiewać `response["key"]` po całym kodzie.

---

## Wyniki testów

Projekt przeszedł trzy rundy testów przed wdrożeniem na produkcję.

| Kategoria | Wynik | Narzędzie |
|---|---|---|
| Testy bezpieczeństwa (OWASP Top 10 + specyficzne) | **73/75 PASS** | aiohttp, pytest |
| Jakość RAG (LLM-as-judge, Claude Haiku) | **11/12 PASS (92%)** | aiohttp, LLM-as-judge |
| Auth i subskrypcje | **10/10 PASS** | aiohttp |

**Testy bezpieczeństwa** pokrywają: SQL injection, XSS, SSTI, IDOR, wyciek wrażliwych danych, omijanie Stripe, ekstrakcję system promptu (10 technik prompt injection), CORS, mass assignment i walidację Pydantic. 2 WARN (brak security headers — Railway dodaje je na poziomie proxy; rejestracja ujawnia istnienie konta — świadomy trade-off UX).

**Testy jakości RAG** używają Claude Haiku jako zewnętrznego sędziego (LLM-as-judge): pytanie + odpowiedź agenta + kryterium → ocena 0–10. Grounding 5/5 (agent podaje konkretne liczby i mechanizmy biologiczne, nie ogólniki), off-topic 3/3 (odmowy są precyzyjne), consistency 1/1. Jedyny nieudany test (T2) to false negative — pytanie "jestem zupełnym początkującym" zadane na koncie testowym z profilem zawodnika; agent słusznie wykrył sprzeczność.

---

## Autor

**Konrad Pochwała**

- GitHub: [DO UZUPEŁNIENIA]
- LinkedIn: [DO UZUPEŁNIENIA]
