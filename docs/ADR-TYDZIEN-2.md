# ADR — Tydzień 2: Backend API + Agent z pamięcią

> Dokument decyzji architektonicznych dla Tygodnia 2 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, dlaczego, co odrzucono i co się zmieniło względem pierwotnego planu.
>
> Data: 2026-04-15 | Autor: Konrad | Status: Ukończony

---

## Spis treści

1. [Przegląd tygodnia](#1-przegląd-tygodnia)
2. [FastAPI — struktura i decyzje](#2-fastapi--struktura-i-decyzje)
3. [Middleware JWT — ewolucja](#3-middleware-jwt--ewolucja)
4. [LangGraph — graf agenta](#4-langgraph--graf-agenta)
5. [Extraction Agent](#5-extraction-agent)
6. [Summarizer Agent](#6-summarizer-agent)
7. [Rate Limiter](#7-rate-limiter)
8. [Pełny PROMPT-01](#8-pełny-prompt-01)
9. [Optymalizacja tokenów](#9-optymalizacja-tokenów)
10. [Zmiany względem pierwotnego planu](#10-zmiany-względem-pierwotnego-planu)
11. [Znane długi techniczne](#11-znane-długi-techniczne)
12. [Diagram architektury po Tygodniu 2](#12-diagram-architektury-po-tygodniu-2)
13. [Pierwsze testy end-to-end](#13-pierwsze-testy-end-to-end)

---

## 1. Przegląd tygodnia

### Co miało powstać (plan)

Działające API — czat z agentem przez Postmana, agent pamięta kontekst.

### Co faktycznie powstało

Pełny działający backend z agentem LangGraph, Extraction Agentem, Summarizerem, rate limiterem i pełnym PROMPT-01. Wszystko przetestowane przez PowerShell (zamiast Postmana).

### Podsumowanie komponentów

| Komponent | Status | Opis |
|---|---|---|
| FastAPI — struktura projektu | ✅ | main.py, config.py, routers/, services/, agents/ |
| Endpointy auth (register/login) | ✅ | Supabase Auth, walidacja emaila przez pydantic[email] |
| Endpoint quiz/submit | ✅ | 14 pól, walidacja zakresów na 3 warstwach |
| Endpoint chat/ | ✅ | Rate limit + LangGraph + background tasks |
| Middleware JWT | ✅ | Weryfikacja przez Supabase Auth API (nie HS256) |
| LangGraph graf | ✅ | 3 node'y: fetch_context, orchestrator, post_process |
| Extraction Agent | ✅ | Haiku-4-5, background task, audit log zmian |
| Summarizer Agent | ✅ | Haiku-4-5, co 10 wiadomości, max 250 słów |
| Rate Limiter | ✅ | 30/dzień + 5/minutę |
| Pełny PROMPT-01 v2.1 | ✅ | Zastąpił skróconą wersję roboczą |
| GitHub | ✅ | Repozytorium prywatne: Konrad2237/bezp-rag-agent |

---

## 2. FastAPI — struktura i decyzje

### Struktura katalogów

```
backend/
├── main.py              ← FastAPI app, CORS, lifespan, routery
├── config.py            ← Singleton klienty: Supabase, OpenAI, Anthropic
├── middleware.py        ← Weryfikacja JWT tokenu
├── routers/
│   ├── __init__.py
│   ├── auth.py          ← POST /auth/register, POST /auth/login
│   ├── quiz.py          ← POST /quiz/submit
│   └── chat.py          ← POST /chat/ (główny endpoint)
├── services/
│   ├── __init__.py
│   ├── rag.py           ← get_embedding(), search_knowledge()
│   └── memory.py        ← sesje, historia, profil, zapis wiadomości
└── agents/
    ├── __init__.py
    ├── graph.py          ← LangGraph graf + PROMPT-01
    ├── extraction.py     ← Extraction Agent (Haiku)
    └── summarizer.py     ← Summarizer Agent (Haiku)
```

### Decyzja: config.py jako singleton

Klienty Supabase, OpenAI i Anthropic są inicjalizowane raz przy starcie aplikacji w `config.py`:

```python
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
```

**Dlaczego:** Inicjalizacja klienta przy każdym requeście byłaby kosztowna (nawiązywanie połączeń, overhead). Singleton zapewnia jedno połączenie na cały lifetime aplikacji.

### Decyzja: lifespan zamiast @app.on_event

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Uruchamiam backend...")
    yield
    print("Zamykam backend...")
```

`@app.on_event("startup")` jest deprecated w nowszych wersjach FastAPI. `lifespan` to nowy standard — kod przed `yield` = startup, kod po `yield` = shutdown.

### Decyzja: CORS middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Bez CORS przeglądarka blokuje requesty z frontendu (Next.js na porcie 3000) do backendu (port 8000). `allow_origins` pobierany ze zmiennej środowiskowej — na produkcji będzie to URL Vercela.

### Walidacja quizu — 3 warstwy

Zgodnie z `security.md` — walidacja na 3 warstwach:

| Warstwa | Gdzie | Co sprawdza |
|---|---|---|
| Frontend (post-MVP) | Next.js | min/max na inputach, wymagane pola |
| Backend | routers/quiz.py | zakresy liczbowe, dozwolone wartości enum |
| Baza danych | CHECK constraints w SQL | ostatnia linia obrony |

```python
# Przykład walidacji w quiz.py
if not (12 <= body.wiek <= 100):
    raise HTTPException(status_code=400, detail="Wiek poza zakresem (12-100)")
if body.cel not in ["masa", "redukcja", "sila", "kondycja"]:
    raise HTTPException(status_code=400, detail="Nieprawidłowy cel")
```

---

## 3. Middleware JWT — ewolucja

### Pierwotna implementacja (nie zadziałała)

```python
# PRZED — ręczna weryfikacja przez python-jose
from jose import jwt, JWTError
payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
user_id = payload.get("sub")
```

**Problem:** Supabase przeszedł na nowe klucze ECC P-256 zamiast HS256. Nowo wydawane tokeny są podpisane nowym algorytmem i nie pasują do starego Legacy JWT Secret.

**Błąd:** `JWTError: Nieprawidłowy token` mimo poprawnego tokenu.

### Aktualna implementacja (działa)

```python
# PO — weryfikacja przez Supabase Auth API
response = supabase.auth.get_user(token)
user_id = response.user.id
```

**Dlaczego działa:** Supabase sam weryfikuje swój token używając aktualnego klucza. Nie musimy znać algorytmu ani klucza.

**Kompromis:** Każdy request do `/chat/` wykonuje dodatkowy request do Supabase Auth API (`get_user`). Przy MVP i małym ruchu nieistotne. Post-MVP: cache tokenu po stronie serwera (Redis lub in-memory dict z TTL).

### Zasada bezpieczeństwa

```python
async def get_current_user(authorization: str = Header(...)) -> str:
```

`user_id` pochodzi WYŁĄCZNIE z zweryfikowanego JWT, nigdy z body requestu ani query params. To eliminuje Lukę #1 z `security.md` — atak gdzie user A podaje user_id usera B w body.

---

## 4. LangGraph — graf agenta

### Dlaczego LangGraph a nie zwykły pipeline

| | Pipeline (scripts/agent.py) | LangGraph (backend/agents/graph.py) |
|---|---|---|
| RAG | Zawsze odpytywany | Agent decyduje kiedy |
| Decyzje | Brak | Pętla ReAct: myśli → działa → myśli |
| Pamięć | Brak | Profil + summary + historia sesji |
| Narzędzia | Brak | search_knowledge_tool |
| Portfolio value | Pipeline/chatbot | Prawdziwy agent |

### State — obiekt przepływający przez graf

```python
class AgentState(TypedDict):
    user_id: str
    session_id: str
    user_message: str
    user_profile: dict
    memory_summary: str
    conversation_history: list
    messages: Annotated[list, operator.add]  # ← akumulacja!
    agent_response: str
```

**Kluczowy detail — `Annotated[list, operator.add]`:**
LangGraph przy każdym przejściu przez node domyślnie nadpisuje wartości w state. Dla `messages` tego nie chcemy — każdy node powinien DOPISYWAĆ do listy, nie nadpisywać. `operator.add` sprawia że listy są łączone zamiast zastępowane.

Bez tego: po wywołaniu narzędzia i powrocie do orchestratora historia wiadomości byłaby utracona.

### Trzy node'y grafu

```
START
  │
  ▼
fetch_context ──→ orchestrator ──→ (narzędzie?) ──→ tools ──→ orchestrator
                       │                                           │
                       └──────────────────────────────────────────┘
                       │ (brak narzędzia)
                       ▼
                  post_process
                       │
                       ▼
                      END
```

**Node 1: fetch_context**
Pobiera równolegle z Supabase:
- Profil usera (`user_profiles`)
- Podsumowanie rozmów (`conversation_summaries`)
- ID sesji (tworzy nową jeśli wygasła po 30 min)
- Ostatnie 10 wiadomości z bieżącej sesji (`messages`)
- Nierozwiązane konflikty (`pending_conflicts`)

Określa typ sesji: `pierwsze_wejscie` / `nowa_sesja` / `kontynuacja`.

Buduje listę `messages` dla Claude: SystemMessage (PROMPT-01 z kontekstem) + historia + HumanMessage (aktualne pytanie).

**Node 2: orchestrator**
Claude Sonnet z narzędziem `search_knowledge_tool`. Analizuje wiadomość i kontekst, decyduje:
- Wywołać narzędzie → pętla wraca do orchestratora z wynikiem RAG
- Odpowiedzieć bezpośrednio → idzie do post_process

**Funkcja should_continue:**
```python
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "post_process"
```

**Node 3: post_process**
Zapisuje obie wiadomości (user + agent) do tabeli `messages` z `prompt_version`.
Aktualizuje `last_activity_at` i `message_count` w sesji.

### Narzędzie search_knowledge_tool

```python
@tool
def search_knowledge_tool(query: str) -> str:
    """
    Przeszukuje bazę wiedzy z ebooka treningowego.
    Używaj gdy user pyta o ćwiczenia, progresję, plany, dietę, regenerację, suplementy.
    Nie używaj przy powitaniach i prostych rozmowach bez potrzeby wiedzy faktualnej.
    Sam formułuj query — nie kopiuj wiadomości usera dosłownie.
    """
```

**Dlaczego docstring jest ważny:** LangGraph przekazuje docstring narzędzia do Claude jako opis. Claude decyduje kiedy wywołać narzędzie NA PODSTAWIE tego opisu. Dobry docstring = lepsze decyzje agenta.

**Dowód z testów:**
```
"Cześć co tam?"         → Agent odpowiada bez narzędzi   ✓
"Ile białka jeść?"      → [RAG] Agent szuka: 'ile białka...'  ✓
"Jaki film polecasz?"   → Agent odpowiada bez narzędzi   ✓ (potem odmawia)
"Czy warto brać kreatynę?" → [RAG] Agent szuka: 'kreatyna...'  ✓
```

---

## 5. Extraction Agent

### Cel

Po każdej rozmowie wyciągnąć z wymiany (1 wiadomość usera + 1 odpowiedź agenta) fakty o userze i zapisać do profilu. Działa w tle — user nic nie widzi.

### Model: Haiku-4-5

**Dlaczego Haiku a nie Sonnet:**
- Zadanie proste: przeczytaj wymianę, zwróć JSON
- Haiku ~15x tańszy od Sonnet
- ~1000-1200 tokenów inputu per wywołanie = ~0.001 PLN
- Przy 3000 wiadomości/mies. = ~3 PLN całkowity koszt ekstrakcji

### Optymalizacja — kompaktowy JSON profilu

```python
# PRZED (indent=2) — ~400 tokenów
profile_str = json.dumps(user_profile, ensure_ascii=False, indent=2)

# PO (separators) — ~200 tokenów, oszczędność ~50%
profile_str = json.dumps(user_profile, ensure_ascii=False, separators=(',', ':'))
```

### Logika ekstrakcji

```
Ostatnia wymiana + profil
         │
         ▼
    Haiku analizuje
         │
    ┌────┴────┐
    │         │
has_updates  brak aktualizacji
    │             │
    │         return (nic nie rób)
    ▼
conflict?
    │
  ┌─┴──┐
  TAK  NIE
  │    │
  │    ├─→ UPDATE user_profiles
  │    └─→ INSERT profile_changes (audit log)
  │
  └─→ INSERT pending_conflicts
      (Orchestrator zapyta usera przy następnej wiad.)
```

### Rozróżnienie waga ciała vs ciężar treningowy

Kluczowy edge case opisany w PROMPT-02:
- `"Ważę 85kg"` → `waga: 85` (waga ciała)
- `"Robię 85kg na ławce"` → `osiagniecia: "ławka 85kg"` (NIE waga ciała)

Bez tego rozróżnienia agent nadpisywałby wagę ciała ciężarem treningowym.

**Próg konfliktu:** zmiana wagi > 10kg względem profilu = automatyczny konflikt (podejrzane).

### Audit log — profile_changes

Każda zmiana profilu przez Extraction Agent jest logowana:

| Pole | Opis |
|---|---|
| user_id | Czyj profil zmieniono |
| field | Które pole (np. "kontuzje") |
| old_value | Wartość przed zmianą |
| new_value | Wartość po zmianie |
| source | "extraction_agent" |
| created_at | Kiedy |

Dzięki temu można cofnąć błędną ekstrakcję bez utraty historii.

---

## 6. Summarizer Agent

### Cel

Co 10 wiadomości usera skondensować historię rozmów do max 250 słów. Ta notatka trafia do Orchestratora jako `memory_summary` — agent "pamięta" poprzednie sesje bez czytania całej historii.

### Trigger

```python
count = get_message_count(user_id)  # liczba wiadomości usera łącznie
if count > 0 and count % 10 == 0:
    run_summarizer_agent(user_id)
```

Sprawdzane po każdej wiadomości w background_tasks w `chat.py`.

### Model: Haiku-4-5

Analogicznie jak Extraction Agent — proste zadanie (streszczenie), nie wymaga Sonnet.

### Co zachowuje, czego nie

| Zachowuje ✓ | Nie zachowuje ✗ |
|---|---|
| Rekordy i osiągnięcia | Pytania o technikę |
| Aktualne kontuzje | Rozmowy bez long-term value |
| Zmiany celu | Informacje już w profilu usera |
| O co agent już dopytywał | Emocje chwilowe |
| Preferencje treningowe | |

**Kluczowy punkt:** "O co agent już dopytywał" — żeby nie pytać dwa razy o ten sam temat (np. o sen) w różnych sesjach.

### Trzy warstwy pamięci agenta

```
┌─────────────────────────────────────────────────┐
│  PAMIĘĆ AGENTA                                  │
│                                                 │
│  Krótka (bieżąca sesja)                         │
│  └─ ostatnie 10 wiadomości z messages           │
│     (czysta, surowa historia)                   │
│                                                 │
│  Strukturalna (profil)                          │
│  └─ user_profiles: wiek, waga, cel, kontuzje... │
│     (Extraction Agent aktualizuje na bieżąco)   │
│                                                 │
│  Długoterminowa (summary)                       │
│  └─ conversation_summaries: max 250 słów        │
│     (Summarizer kondensuje co 10 wiadomości)    │
└─────────────────────────────────────────────────┘
```

---

## 7. Rate Limiter

### Implementacja

```python
def check_rate_limit(user_id: str):
    # Dzienny limit: max 30 wiadomości
    daily = supabase.table("messages")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("role", "user")
        .gte("created_at", day_ago)
        .execute()

    if daily.count >= 30:
        raise HTTPException(429, "Dzienny limit wiadomości wyczerpany.")

    # Per-minutowy limit: max 5 wiadomości
    per_minute = supabase.table("messages")
        .select("id", count="exact")
        ...
    if per_minute.count >= 5:
        raise HTTPException(429, "Za dużo wiadomości naraz.")
```

### Dlaczego dwa limity

| Limit | Cel | Zagrożenie bez niego |
|---|---|---|
| 30/dzień | Budżet API | 1 user może przepalić miesięczny budżet w 1 dzień |
| 5/minutę | Burst protection | 30 wiadomości w 30 sekund blokuje workerów, triggeruje rate limit Anthropic |

### Gdzie w flow

Rate limit sprawdzany PRZED uruchomieniem agenta — jeśli limit przekroczony, Claude nie jest w ogóle wywoływany. Zero zużycia tokenów przy overdosie.

---

## 8. Pełny PROMPT-01

### Ewolucja promptu

| Wersja | Gdzie | Co miała |
|---|---|---|
| Skrócona robocza (Tydzień 1) | scripts/agent.py | Podstawowy ton, RAG, prosta odmowa |
| Robocza w grafie (Tydzień 2 start) | backend/agents/graph.py `build_system_prompt` | Profil, null_fields, summary, session_type |
| Pełny PROMPT-01 v2.1 (Tydzień 2 koniec) | backend/agents/graph.py `build_system_prompt` | Wszystkie sekcje z dokumentacji |

### Co dodał pełny PROMPT-01

| Sekcja | Efekt |
|---|---|
| PERSONA z przykładami tonu | Spójny styl odpowiedzi |
| PIERWSZE POWITANIE | Specjalna logika dla session_type = "pierwsze_wejscie" |
| BRAKUJĄCE DANE z priorytetem | Agent naturalnie dopytuje o sen i dietę |
| TWARDA ODMOWA z przykładami | Konkretne odpowiedzi przy off-topic |
| OCHRONA PRZED MANIPULACJĄ | Odporność na prompt injection |
| KRYTYCZNY WYJĄTEK (116 123) | Bezpieczeństwo użytkownika |
| PENDING CONFLICTS | Agent pyta o potwierdzenie przed zmianą profilu |

### Test pełnego PROMPT-01

```
Pytanie: "Jaki film polecasz na dzisiaj wieczor?"
Odpowiedź: "Słuchaj, nie po to tutaj kurwa jestem żeby gadać o filmach.
            Ja jestem od siłowni. Wróćmy do tego barku..."

Pytanie: "Czy warto brać kreatynę?"
[RAG] Agent szuka: 'kreatyna suplementacja efekty dawkowanie'
Odpowiedź: Konkretna odpowiedź z danych ebooka o kreatynie.
```

---

## 9. Optymalizacja tokenów

### Analiza kosztów per request

| Agent | Model | Tokeny input | Tokeny output | Koszt (~) |
|---|---|---|---|---|
| Orchestrator (bez RAG) | Sonnet | ~1500 (prompt) + ~200 (wiad.) | ~200 | ~0.006 PLN |
| Orchestrator (z RAG) | Sonnet | ~1500 + ~200 + ~800 (chunki) | ~300 | ~0.009 PLN |
| Extraction Agent | Haiku | ~800 (prompt) + ~400 (profil) + ~400 (wymiana) | ~100 | ~0.001 PLN |
| Summarizer Agent | Haiku | ~500 (prompt) + ~2000 (10 wiad.) | ~300 | ~0.002 PLN |

**Koszt jednej wiadomości bez RAG:** ~0.007 PLN
**Koszt jednej wiadomości z RAG:** ~0.010 PLN
**Koszt przy 3000 wiadomości/mies.:** ~21-30 PLN (Claude) + ~0.10 PLN (OpenAI embeddingi)

### Optymalizacje wdrożone

1. **RAG jako narzędzie (nie pre-fetch):** "Cześć" nie odpytuje bazy — oszczędność ~800 tokenów na prostych rozmowach
2. **Kompaktowy JSON profilu:** `separators=(',', ':')` zamiast `indent=2` — ~50% mniej tokenów na profilu w Extraction Agent
3. **Haiku dla background tasks:** Extraction i Summarizer na Haiku zamiast Sonnet — ~15x tańsze

### Optymalizacje zaplanowane (post-MVP)

- Prompt caching na system promptcie (85-90% redukcja kosztów input tokenów)
- Cache tokenu JWT (eliminuje extra request do Supabase per request)

---

## 10. Zmiany względem pierwotnego planu

| Co było w planie | Co zrobiono inaczej | Powód |
|---|---|---|
| Testowanie przez Postmana | PowerShell Invoke-RestMethod | Postman nie był zainstalowany — PowerShell wbudowany w Windows |
| JWT przez python-jose (HS256) | JWT przez Supabase Auth API | Supabase zmienił format kluczy na ECC P-256 |
| Testy integracyjne jako osobny dzień | Testy w trakcie budowania | Szybsze tempo — testowaliśmy na bieżąco |
| 5 agentów (z PROMPT-05) | 4 agenty (PROMPT-05 usunięty) | Orchestrator obsługuje powitanie samodzielnie |
| message_count przez zapytanie | Osobna funkcja get_message_count() | Czystszy kod, łatwiejszy do testowania |

---

## 11. Znane długi techniczne

| # | Dług | Priorytet | Kiedy naprawić |
|---|---|---|---|
| 1 | Brak streaming response (SSE) — user czeka na całą odpowiedź | Wysoki | Tydzień 3 przy frontendzie |
| 2 | Weryfikacja JWT = extra request do Supabase per każdy request | Niski | Post-MVP (cache tokenu) |
| 3 | asyncio.create_task może failować cicho gdy event loop zamknięty | Średni | Dodać error handling w background_tasks |
| 4 | Extraction Agent zapisuje do profilu nawet gdy user nie ma rekordu w user_profiles | Średni | Sprawdzić czy profil istnieje przed UPDATE |
| 5 | Brak obsługi retry przy błędach Anthropic API (timeout, 529) | Wysoki | Przed deployem |
| 6 | Token JWT wygasa co 3600s — w testach trzeba logować się ponownie | Brak | To feature, nie bug. Frontend obsłuży refresh token automatycznie |
| 7 | PROMPT-01 nie ma obsługi generate_training_plan i update_user_goal jako narzędzi LangGraph | Średni | Tydzień 3 lub Faza 1 po MVP |
| 8 | quiz.md i mvp-plan.md nadal mówią "22 pytania" — niespójność | Niski | Zaktualizować dokumentację |

---

## 12. Diagram architektury po Tygodniu 2

### Przepływ jednego requestu

```
USER
  │ POST /chat/
  │ Authorization: Bearer <JWT>
  ▼
FastAPI (main.py)
  │
  ▼
middleware.py
  │ supabase.auth.get_user(token)
  ├──────────────────────────────→ Supabase Auth
  │ ←── user_id ─────────────────
  │
  ▼
routers/chat.py
  │ check_rate_limit(user_id)
  │   └─→ Supabase: count messages (dzienny + per-min)
  │
  │ get_user_profile(user_id)
  │   └─→ Supabase: SELECT user_profiles
  │
  │ run_agent(user_id, message)  ← SYNCHRONICZNIE (blokuje do odpowiedzi)
  │   └─→ LangGraph graph.py
  │         │
  │         ├─ fetch_context
  │         │   ├─→ Supabase: profil, summary, sesja, historia, konflikty
  │         │   └─→ Buduje SystemMessage + historia + HumanMessage
  │         │
  │         ├─ orchestrator (Claude Sonnet)
  │         │   ├─ [tool call?] → search_knowledge_tool
  │         │   │                   ├─→ OpenAI: embedding(query)
  │         │   │                   └─→ Supabase: match_knowledge()
  │         │   └─ odpowiedź tekstowa
  │         │
  │         └─ post_process
  │             └─→ Supabase: INSERT messages (2 rekordy)
  │
  │ return {"response": "..."}  ← ODPOWIEDŹ DO USERA
  │
  │ asyncio.create_task(background_tasks(...))  ← ASYNCHRONICZNIE
  │   ├─ run_extraction_agent()
  │   │   ├─→ Anthropic: Haiku(profil + wymiana) → JSON updates
  │   │   ├─→ Supabase: INSERT profile_changes (audit log)
  │   │   └─→ Supabase: UPDATE user_profiles
  │   │
  │   └─ [co 10 wiad.] run_summarizer_agent()
  │       ├─→ Supabase: SELECT last 10 messages
  │       ├─→ Anthropic: Haiku(poprzednie summary + 10 wiad.) → nowe summary
  │       └─→ Supabase: UPSERT conversation_summaries
  │
  ▼
USER otrzymuje odpowiedź
(background tasks działają jeszcze przez ~1-2s po odpowiedzi)
```

### Trzy warstwy pamięci

```
┌──────────────────────────────────────────────────────────────┐
│                    PAMIĘĆ AGENTA                             │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │  KRÓTKA              │  │  STRUKTURALNA                │  │
│  │  (bieżąca sesja)     │  │  (profil)                    │  │
│  │                      │  │                              │  │
│  │  Ostatnie 10 wiad.   │  │  wiek, waga, cel, kontuzje   │  │
│  │  z tabeli messages   │  │  dni_treningowe, sprzęt...   │  │
│  │                      │  │                              │  │
│  │  Traci się po        │  │  Aktualizowana przez         │  │
│  │  zamknięciu sesji    │  │  Extraction Agent            │  │
│  └──────────────────────┘  └──────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  DŁUGOTERMINOWA (summary)                            │   │
│  │                                                      │   │
│  │  Max 250 słów, kondensowane co 10 wiadomości         │   │
│  │  przez Summarizer Agent (Haiku)                      │   │
│  │  Zachowuje: rekordy, kontuzje, preferencje,          │   │
│  │  zmiany celu, o co agent już dopytywał               │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Zewnętrzne serwisy i modele

```
┌─────────────────────┬──────────────────────┬────────────────────┐
│    Supabase         │   Anthropic API       │    OpenAI API      │
│    (EU West 2)      │                       │                    │
│                     │  Orchestrator:        │  Embeddingi:       │
│  PostgreSQL +       │  claude-sonnet-4-6    │  text-embedding    │
│  pgvector +         │                       │  -3-small          │
│  Auth               │  Extraction:          │                    │
│                     │  claude-haiku-4-5     │  ~$0.02/1M tok.    │
│  service_role_key   │                       │                    │
│  (omija RLS)        │  Summarizer:          │                    │
│                     │  claude-haiku-4-5     │                    │
└─────────────────────┴──────────────────────┴────────────────────┘
```

---

## 13. Pierwsze testy end-to-end

### Testy przeprowadzone

| Test | Oczekiwany wynik | Faktyczny wynik | Status |
|---|---|---|---|
| Logowanie i pobranie JWT | access_token w odpowiedzi | ✓ Token ~800 znaków | ✅ |
| Pytanie wymagające RAG | Agent wywołuje search_knowledge_tool | `[RAG] Agent szuka: 'progresja obciążeń'` | ✅ |
| Powitanie (bez RAG) | Agent odpowiada bez narzędzi | `[GRAPH] Agent odpowiada bez narzędzi` | ✅ |
| Pytanie off-topic | Twarda odmowa z humorem | "Słuchaj, nie po to tutaj kurwa jestem..." | ✅ |
| Extraction Agent po kontuzji | `profile_changes` z polem `kontuzje` | Zapisano "Ból barku przy wyciskaniu" | ✅ |
| Kontekst z poprzedniej rozmowy | Agent nawiązuje do kontuzji barku | "Wróćmy do tego barku — nadal czekam..." | ✅ |
| Wiadomości w Supabase | INSERT do tabeli messages | Rekordy w UTC (12:54 UTC = 14:54 PL) | ✅ |

### Znane ograniczenia testów

- Testowano bez quizu — user nie miał profilu w `user_profiles`. Extraction Agent próbował UPDATE na nieistniejący rekord. W prawdziwym flow user wypełnia quiz przed czatem.
- Testowano przez PowerShell, nie przez frontend — brak testów UX.
- Token JWT wygasa co 60 minut — trzeba re-logować się w trakcie testów.

---

*Następny dokument: ADR-TYDZIEN-3 (Frontend Next.js + deploy Railway + Vercel + testy z prawdziwym użytkownikiem)*
