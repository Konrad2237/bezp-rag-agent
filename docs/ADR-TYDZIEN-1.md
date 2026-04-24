# ADR — Tydzień 1: Fundament (Dane + RAG)

> Dokument decyzji architektonicznych dla Tygodnia 1 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, dlaczego, co odrzucono i co się zmieniło względem pierwotnego planu.
>
> Data: 2026-04-15 | Autor: Konrad | Status: Ukończony

---

## Spis treści

1. [Przegląd tygodnia](#1-przegląd-tygodnia)
2. [Infrastruktura bazy danych](#2-infrastruktura-bazy-danych)
3. [Chunking ebooka](#3-chunking-ebooka)
4. [Pipeline embeddingów i RAG](#4-pipeline-embeddingów-i-rag)
5. [Pierwszy agent terminalowy](#5-pierwszy-agent-terminalowy)
6. [FastAPI i LangGraph — fundament Tygodnia 2](#6-fastapi-i-langgraph--fundament-tygodnia-2)
7. [Decyzje dotyczące promptów](#7-decyzje-dotyczące-promptów)
8. [Zmiany względem pierwotnego planu](#8-zmiany-względem-pierwotnego-planu)
9. [Znane długi techniczne](#9-znane-długi-techniczne)
10. [Diagram architektury po Tygodniu 1](#10-diagram-architektury-po-tygodniu-1)

---

## 1. Przegląd tygodnia

### Co miało powstać (plan)

Działający RAG w terminalu — pytasz pytanie, dostajesz odpowiedź z ebooka. Zero frontendu, zero API.

### Co faktycznie powstało

Więcej niż plan zakładał — gotowy fundament backendu z działającym agentem LangGraph podłączonym do FastAPI. Tydzień 1 skończony w ~3 godziny, fundament Tygodnia 2 zbudowany tego samego dnia.

### Podsumowanie komponentów

| Komponent | Status | Opis |
|---|---|---|
| Supabase — projekt i konfiguracja | ✅ | Region EU (Londyn), free tier |
| pgvector — rozszerzenie | ✅ | Wersja 0.8.0, HNSW index |
| Tabele bazy danych | ✅ | 9 tabel wg schematu z database.md |
| RLS (Row Level Security) | ✅ | Włączone na 8 tabelach, knowledge_embeddings bez RLS |
| Chunking ebooka | ✅ | Agentic chunking przez GPT-4o-mini, 19 chunków |
| Embeddingi | ✅ | text-embedding-3-small, VECTOR(1536) |
| Similarity search | ✅ | Funkcja match_knowledge w PostgreSQL |
| Agent terminalowy | ✅ | scripts/agent.py — działający RAG + Claude |
| FastAPI backend | ✅ | Endpointy auth, quiz, chat |
| LangGraph graf | ✅ | 3 node'y: fetch_context, orchestrator, post_process |

---

## 2. Infrastruktura bazy danych

### Decyzja: Supabase zamiast własnego PostgreSQL

**Kontekst:** Projekt potrzebuje PostgreSQL z pgvector, Auth, storage i REST API.

**Rozważane opcje:**

| Opcja | Zalety | Wady |
|---|---|---|
| Supabase (free tier) | Auth out-of-the-box, pgvector wbudowany, REST API, dashboard | Pauzuje po 7 dniach bez aktywności na free tier |
| Własny PostgreSQL na VPS | Pełna kontrola, brak pauzowania | Wymaga konfiguracji Auth, pgvector osobno, dodatkowy czas |
| Railway PostgreSQL | Prosty deploy | Brak wbudowanego Auth, pgvector trzeba dodać ręcznie |

**Decyzja:** Supabase — wszystko w jednym miejscu, zero konfiguracji Auth, pgvector dostępny jednym togglem.

**Region:** EU West 2 (Londyn) — wybór celowy, wymagany przez RODO. Dane userów (wiek, waga, kontuzje) to dane zdrowotne kategorii art. 9 RODO.

### Tabele — co i dlaczego

```
user_profiles          ← dane z quizu + ekstrakcja z rozmów przez Extraction Agent
conversation_sessions  ← zarządzanie sesjami (nowa sesja po 30 min nieaktywności)
messages               ← historia wiadomości z prompt_version
conversation_summaries ← skrócona pamięć długoterminowa (Summarizer Agent co 10 wiad.)
knowledge_embeddings   ← chunki z ebooka z wektorami
training_plans         ← generowane plany (post-MVP)
subscriptions          ← Stripe (post-MVP)
pending_conflicts      ← konflikty wykryte przez Extraction Agent
profile_changes        ← audit log zmian profilu
```

### Decyzja: prompt_version w tabeli messages

**Kontekst:** Pierwotny schemat w database.md nie miał tej kolumny.

**Powód dodania:** testing-and-ops.md wskazuje że każda wiadomość powinna zapisywać wersję promptu — żeby przy zmianie PROMPT-01 wiedzieć co i kiedy wygenerowało problem. Dodano podczas sesji zanim zaczęto pisać kod backendu.

```sql
ALTER TABLE messages ADD COLUMN prompt_version TEXT;
```

### Decyzja: Trigger updated_at na user_profiles

**Powód:** Pole `updated_at` bez triggera nigdy się nie aktualizuje po pierwszym insercie. Extraction Agent będzie aktualizował profil — bez triggera nie wiadomo kiedy ostatnio zmieniły się dane.

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_profiles_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### RLS — dlaczego knowledge_embeddings bez RLS

Wszystkie tabele z danymi userów mają RLS (`WHERE user_id = auth.uid()`). Wyjątek: `knowledge_embeddings` — to wiedza ogólna z ebooka, nie dane personalne. Każdy zalogowany user musi mieć do niej dostęp żeby RAG działał.

### HNSW Index na embeddingach

```sql
CREATE INDEX ON knowledge_embeddings USING hnsw (embedding vector_cosine_ops);
```

**Dlaczego HNSW a nie IVFFlat:** HNSW (Hierarchical Navigable Small World) to algorytm przybliżonego wyszukiwania najbliższych sąsiadów. Przy kilkudziesięciu chunkach różnica w wydajności jest niezauważalna, ale HNSW jest standardem i nie wymaga wcześniejszego treningu (IVFFlat wymaga `VACUUM ANALYZE` po insercie danych).

---

## 3. Chunking ebooka

### Problem z PDF

**Pierwotny plan:** PDF na chunki przez PyPDF2.

**Co się stało:** PDF ebooka ma niestandardowe fonty — PyPDF2 wyciągał tekst bez spacji (`Dlaczegoogóletopiszę?`). Próba z pdfplumber — ten sam problem.

**Rozwiązanie:** Plik `.docx` (Word) zamiast PDF. docx trzyma tekst jako XML — pełne spacje, prawidłowe kodowanie.

### Problem ze stylami Word

**Pierwotna próba:** Podział po `Heading 1 / Heading 2`.

**Co się stało:** Ebook ma własne style: `kurwo jebana` (tytuł rozdziału), `rozdział` (podrozdział), `cytat`, `zasady`, `Normal`. Żadnego standardowego `Heading`.

**Iteracje:**
1. Podział po `kurwo jebana` + `rozdział` + `cytat` → 15 chunków, cytaty rozbiły tematy
2. Podział po `kurwo jebana` + `rozdział` (bez `cytat`) → 12 chunków po rozdziałach, ale rozdziały ~1500 słów = za duże
3. Podział po podrozdziałach → semantycznie OK strukturą, ale informacje o tym samym temacie rozrzucone po rozdziałach

### Ostateczne rozwiązanie: Agentic Chunking przez GPT-4o-mini

**Decyzja:** Zamiast dzielić mechanicznie po tagach, wysłać całą treść do GPT-4o-mini z instrukcją semantycznego grupowania.

**Dlaczego GPT-4o-mini a nie GPT-4o:**
- Pliki łącznie ~69 KB = ~17 000 tokenów
- GPT-4o-mini wystarczy do zadania grupowania tekstu
- GPT-4o byłoby ~15x droższe bez różnicy w jakości

**Pipeline:**

```
czesc1.txt (rozdz. 1-3)  ┐
czesc2.txt (rozdz. 4-6)  ├─→ GPT-4o-mini (chunking per część) ─→ chunki_czescN.json
czesc3.txt (rozdz. 7-9)  │
czesc4.txt (rozdz. 10-12)┘
                                    ↓
                         GPT-4o-mini (scalanie między częściami)
                                    ↓
                         chunki_finalne.json (19 chunków)
```

**Zabezpieczenie przed limitem tokenów:** Jeśli łączny rozmiar chunków przed scalaniem > 30 000 tokenów → scalanie parami (1+2, 3+4, potem razem). W praktyce nie było potrzebne (~5000 tokenów łącznie).

### Wynik — 19 chunków semantycznych

| # | Temat | Rozdziały źródłowe | Słów |
|---|---|---|---|
| 0 | Progresja obciążeń | 1, 3, 8 | 375 |
| 1 | Plan FBW | 3 | 89 |
| 2 | Rozgrzewka | 3 | 82 |
| 3 | Ćwiczenia podstawowe | 3 | 97 |
| 4 | Bezpieczeństwo w treningu | 3 | 74 |
| 5 | Systemy treningowe | 4 | 121 |
| 6 | Trening kobiet | 4 | 113 |
| 7 | Plany treningowe | 5, 6 | 108 |
| 8 | Plan treningowy w domu | 7 | 182 |
| 9 | Ograniczenia treningu domowego | 7 | 78 |
| 10 | Dieta i suplementy | 9 | 172 |
| 11 | Suplementy | 9 | 126 |
| 12 | Regeneracja i sen | 10 | 201 |
| 13 | Dni wolne i regeneracja | 10 | 69 |
| 14 | Overreaching vs overtraining | 10 | 75 |
| 15 | Mentalność i dyscyplina | 11 | 135 |
| 16 | Nawyki treningowe | 11 | 86 |
| 17 | Plan działania na 12 tygodni | 12 | 117 |
| 18 | Mentalność na lata | 12 | 82 |

**Kluczowa zaleta:** Chunk [0] "Progresja obciążeń" zebrał informacje z rozdziałów 1, 3 i 8 — które w ebooku są rozrzucone. To niemożliwe przy mechanicznym podziale po nagłówkach.

**Skrypty do re-ingestion (gdy dodasz nowe źródła):**
1. Dodaj nowy plik do `ebook-parts/` (np. `artykul1.txt`)
2. Uruchom `python scripts/agentic_chunk.py` — przetworzy nowe pliki
3. Uruchom `python scripts/upload_chunks.py` — wgra do Supabase

Przed re-ingestion istniejącego źródła usuń stare chunki:
```sql
DELETE FROM knowledge_embeddings WHERE source = 'ebook';
```

---

## 4. Pipeline embeddingów i RAG

### Model embeddingów: text-embedding-3-small

**Rozważane opcje:**

| Model | Wymiar | Koszt | Jakość |
|---|---|---|---|
| text-embedding-3-small | 1536 | ~$0.02/1M tokenów | Dobra dla języka polskiego |
| text-embedding-3-large | 3072 | ~$0.13/1M tokenów | Lepsza, ale 6.5x drożej |
| text-embedding-ada-002 | 1536 | ~$0.10/1M tokenów | Stary model, gorszy |

**Decyzja:** text-embedding-3-small — Anthropic nie ma własnych modeli embeddingów, OpenAI small jest tańszy od ada-002 i lepszy jakościowo. Przy ~20 chunkach i kilku tysiącach zapytań miesięcznie koszt embeddingów to grosze (~0.10 PLN/miesiąc).

### Funkcja similarity search

```sql
CREATE OR REPLACE FUNCTION match_knowledge(
  query_embedding VECTOR(1536),
  match_threshold FLOAT,
  match_count INT
)
RETURNS TABLE (id UUID, content TEXT, section_title TEXT, similarity FLOAT)
LANGUAGE SQL STABLE AS $$
  SELECT id, content, section_title,
         1 - (embedding <=> query_embedding) AS similarity
  FROM knowledge_embeddings
  WHERE 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
$$;
```

**Dlaczego `1 - cosine_distance`:** Operator `<=>` w pgvector zwraca cosine **distance** (0 = identyczne, 2 = przeciwne). `1 - distance` konwertuje na **similarity** (1 = identyczne, 0 = brak podobieństwa). Próg 0.3 oznacza "zwróć chunki podobne w co najmniej 30%".

**Parametry:**

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| match_threshold | 0.3 | Niski próg — lepiej zwrócić za dużo niż za mało. Agent sam oceni relevancję. |
| match_count | 3 | Top 3 chunki wystarczą. Więcej = więcej tokenów w prompcie = wyższy koszt. |
| Truncate query | 1000 znaków | Zabezpieczenie przed bardzo długimi pytaniami. |

**Wyniki testów similarity search:**

| Pytanie | Top 1 chunk | Similarity |
|---|---|---|
| "Jak dodawać ciężar na sztandze?" | Progresja obciążeń | 0.495 |
| "Ile serii robić na klatkę?" | Rozgrzewka | 0.521 |
| "Jak spać żeby się regenerować?" | Regeneracja i sen | 0.582 |
| "Ile kosztuje kawalerka w Warszawie?" | Suplementy | 0.394 |

Ostatni wynik pokazuje ograniczenie RAG — przy pytaniach off-topic zwraca "najbardziej podobne" chunki mimo że są totalnie nierelewantne. To celowe — agent (Claude) dostaje te chunki, widzi że są irrelewantne i odmawia odpowiedzi.

---

## 5. Pierwszy agent terminalowy

**Plik:** `scripts/agent.py`

**Architektura (uproszczona, bez LangGraph):**

```
Pytanie usera
     │
     ▼
get_embedding(pytanie)          ← OpenAI API
     │
     ▼
match_knowledge(embedding)      ← Supabase pgvector
     │
     ▼
Zbuduj prompt: system + RAG     ← Python
     │
     ▼
claude.messages.create()        ← Anthropic API
     │
     ▼
Odpowiedź w terminalu
```

**Cel:** Weryfikacja że RAG działa zanim zaczniemy budować backend. Celowo uproszczony — RAG zawsze odpytywany niezależnie od pytania (nie agentic).

**Wynik testu:** Agent poprawnie odpowiedział na pytanie "Jak progresować na ławce?" cytując progresję liniową i podwójną z ebooka, z naturalnym tonem i wulgaryzmami.

---

## 6. FastAPI i LangGraph — fundament Tygodnia 2

Zbudowane w tym samym dniu, ponieważ fundament RAG był gotowy szybciej niż plan zakładał.

### Struktura backendu

```
backend/
├── main.py          ← FastAPI app, CORS, routery
├── config.py        ← klienty Supabase, OpenAI, Anthropic
├── middleware.py    ← weryfikacja JWT przez Supabase Auth
├── routers/
│   ├── auth.py      ← POST /auth/register, POST /auth/login
│   ├── quiz.py      ← POST /quiz/submit
│   └── chat.py      ← POST /chat/
├── services/
│   ├── rag.py       ← get_embedding(), search_knowledge()
│   └── memory.py    ← sesje, historia, profil, zapis wiadomości
└── agents/
    └── graph.py     ← LangGraph graf
```

### LangGraph — graf agenta

**Dlaczego LangGraph a nie zwykłe wywołanie Claude:**

Zwykłe wywołanie (jak w scripts/agent.py) to pipeline — RAG zawsze odpytywany, brak decyzji agenta. LangGraph daje pętlę ReAct:

```
fetch_context → orchestrator ─→ tools (RAG) ─→ orchestrator → post_process
                     └──────────────────────────────┘
                          (pętla gdy agent chce narzędzia)
```

Claude sam decyduje:
- "Cześć co tam?" → brak narzędzi, odpowiedź bezpośrednia
- "Ile białka jeść?" → wywołuje search_knowledge_tool, czyta wyniki, odpowiada

**Dowód z logów:**
```
[AGENT] Wiadomość: 'Cze, co tam?'
[GRAPH] Agent odpowiada bez narzędzi    ← bez RAG

[AGENT] Wiadomość: 'Ile bialka powinienem jesc?'
[RAG] Agent szuka: 'ile białka dziennie zapotrzebowanie gramów na kilogram'
[RAG] Znaleziono 3 chunków
[GRAPH] Agent odpowiada bez narzędzi    ← po przeczytaniu RAG
```

### State LangGraph

```python
class AgentState(TypedDict):
    user_id: str
    session_id: str
    user_message: str
    user_profile: dict
    memory_summary: str
    conversation_history: list
    messages: Annotated[list, operator.add]  # ← akumulacja wiadomości
    agent_response: str
```

`Annotated[list, operator.add]` — kluczowy detail. LangGraph przy każdym przejściu przez node dopisuje do listy zamiast nadpisywać. Dzięki temu historia wiadomości (SystemMessage + HumanMessage + AIMessage + ToolMessage) rośnie prawidłowo w trakcie pętli narzędzi.

### Weryfikacja JWT — ewolucja

**Pierwotna implementacja:** Ręczna weryfikacja przez `python-jose` z Legacy JWT Secret (HS256).

**Problem:** Supabase przeszedł na nowe klucze ECC P-256. Tokeny wystawiane przez nowy system nie pasują do starego HS256 secret.

**Rozwiązanie:** Weryfikacja przez `supabase.auth.get_user(token)` — Supabase sam weryfikuje swój token.

```python
# PRZED (nie działało z nowymi kluczami):
payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])

# PO (działa zawsze):
response = supabase.auth.get_user(token)
user_id = response.user.id
```

**Uwaga:** Ta metoda wykonuje dodatkowy request do Supabase przy każdym requestu API. Przy MVP i małym ruchu to akceptowalne. Post-MVP: cache tokenu po stronie serwera.

### Sesje rozmów — logika 30 minut

```python
diff_minutes = (now - last_activity).total_seconds() / 60
if diff_minutes <= 30:
    return session["id"]   # kontynuuj sesję
else:
    # zamknij starą, stwórz nową
```

**Dlaczego 30 minut:** Za krótko (5 min) = user idzie na kawę, wraca, agent "zapomniał". Za długo (24h) = historia za długa, przepełnienie kontekstu. 30 minut = naturalna przerwa w rozmowie. Opisane w database.md.

---

## 7. Decyzje dotyczące promptów

### Usunięcie PROMPT-05 (wiadomość powitalna)

**Pierwotny plan:** Osobny agent (PROMPT-05) do generowania pierwszej wiadomości po quizie.

**Decyzja:** Usunięto. Orchestrator (PROMPT-01) dostaje `session_type = "pierwsze_wejscie"` i sam generuje powitanie. Jeden agent zamiast dwóch — zero straty jakości.

**Oszczędność:** Jeden mniej call do Claude Sonnet przy onboardingu.

**Zmiana w pliku:** `docs/system-prompt.md` zaktualizowany — PROMPT-05 usunięty z listy, sekcja `PIERWSZE POWITANIE` dodana do PROMPT-01.

### Prompt w graph.py — celowo uproszczony

Aktualny prompt w `backend/agents/graph.py` (`build_system_prompt`) to skrócona wersja robocza. Brakuje:
- Pełnej sekcji OCHRONA PRZED MANIPULACJĄ
- Szczegółowych zasad tonu z przykładami
- Obsługi PENDING_CONFLICTS
- Sekcji TWARDA ODMOWA z przykładami

**To jest celowy dług techniczny** — testowy agent do weryfikacji że graf działa. Pełny PROMPT-01 z `docs/system-prompt.md` zostanie wdrożony w Tygodniu 2 przy finalizacji endpointu `/chat`.

---

## 8. Zmiany względem pierwotnego planu

| Co było w planie | Co zrobiono inaczej | Powód |
|---|---|---|
| PDF jako format ebooka | docx (Word) | PDF miał uszkodzone kodowanie znaków |
| Chunking po nagłówkach | Agentic chunking przez GPT-4o-mini | Informacje o tym samym temacie rozrzucone po rozdziałach |
| Tydzień 1 = tylko RAG w terminalu | Tydzień 1 + fundament Tygodnia 2 | Plan zakończony w ~3h, naturalnie poszliśmy dalej |
| PROMPT-05 jako osobny agent | Sekcja w PROMPT-01 | Zbędna złożoność i koszt |
| Ręczna weryfikacja JWT (python-jose) | Weryfikacja przez Supabase Auth API | Supabase zmienił format kluczy na ECC P-256 |
| Quiz: 22 pytania (mvp-plan.md) | Quiz: 14 pytań + agent dopytuje organicznie | Mniej pytań = mniejszy dropout na mobile |

---

## 9. Znane długi techniczne

| # | Dług | Priorytet | Kiedy naprawić |
|---|---|---|---|
| 1 | Prompt w graph.py to uproszczona wersja robocza | Wysoki | Tydzień 2, przed testami z prawdziwym userem |
| 2 | Brak Extraction Agent (profil nie aktualizuje się z rozmów) | Wysoki | Tydzień 2 |
| 3 | Brak Summarizer Agent (pamięć długoterminowa nie działa) | Wysoki | Tydzień 2 |
| 4 | Brak rate limitera (dzienny + per minutę) | Wysoki | Tydzień 2, przed deployem |
| 5 | Weryfikacja JWT wykonuje dodatkowy request do Supabase per request | Niski | Post-MVP (cache tokenu) |
| 6 | quiz.md i mvp-plan.md mówią "22 pytania" — niespójność z decyzją 14 pytań | Niski | Zaktualizować dokumentację |
| 7 | Supabase free tier pauzuje po 7 dniach bez aktywności | Średni | n8n ping co 6 dni lub upgrade do Pro przed deployem |
| 8 | message_count w conversation_sessions aktualizowany przez osobny SELECT | Niski | Można uprościć do `message_count + 2` bez SELECT |

---

## 10. Diagram architektury po Tygodniu 1

### Przepływ jednego requestu (aktualny stan)

```
                    USER
                      │
                      │ POST /chat/
                      │ Authorization: Bearer <JWT>
                      ▼
              ┌───────────────┐
              │   FastAPI     │
              │   main.py     │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │  middleware   │   supabase.auth.get_user(token)
              │  JWT verify   │ ──────────────────────────────→ Supabase Auth
              └───────┬───────┘ ←── user_id ──────────────────
                      │
                      ▼
              ┌───────────────┐
              │  LangGraph    │
              │  run_agent()  │
              └───────┬───────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    fetch_context  orchestrator  post_process
          │           │               │
          │    ┌──────┴──────┐        │
          │    │  Claude     │        │
          │    │  Sonnet     │        │
          │    └──────┬──────┘        │
          │           │               │
          │    tool_call?             │
          │    ├── TAK → search_rag   │
          │    │         (OpenAI +    │
          │    │          pgvector)   │
          │    └── NIE → odpowiedź   │
          │                           │
          └─────────── Supabase ──────┘
               (profil, sesje,
                historia, zapis)
```

### Komponenty zewnętrzne

```
┌─────────────────────────────────────────────────────────┐
│                    ZEWNĘTRZNE SERWISY                    │
├──────────────────┬──────────────────┬───────────────────┤
│    Supabase      │   Anthropic API  │    OpenAI API     │
│                  │                  │                   │
│  - PostgreSQL    │  - Claude Sonnet │  - text-embedding │
│  - pgvector      │    4.6 (agent)   │    -3-small       │
│  - Auth          │                  │    (embeddingi)   │
│  - REST API      │                  │                   │
│  Region: EU      │                  │                   │
└──────────────────┴──────────────────┴───────────────────┘
```

### Pliki projektu — co robi każdy

```
bezp-rag-agent/
├── .env                          ← klucze API (NIGDY na GitHub)
├── .gitignore                    ← chroni .env, PDF, __pycache__
├── ebook-bezp.docx               ← źródło wiedzy agenta
│
├── ebook-parts/                  ← ebook podzielony na 4 pliki txt
│   ├── czesc1.txt                  (rozdz. 1-3)
│   ├── czesc2.txt                  (rozdz. 4-6)
│   ├── czesc3.txt                  (rozdz. 7-9)
│   └── czesc4.txt                  (rozdz. 10-12)
│
├── chunki/
│   ├── chunki_czesc1-4.json      ← surowe chunki per część
│   └── chunki_finalne.json       ← 19 finalnych chunków po scalaniu
│
├── scripts/
│   ├── agentic_chunk.py          ← KROK 1: chunking przez GPT-4o-mini
│   ├── upload_chunks.py          ← KROK 2: upload do Supabase z embeddingami
│   ├── test_search.py            ← test similarity search (interaktywny)
│   ├── agent.py                  ← prototypowy agent terminalowy (bez LangGraph)
│   ├── check_docx.py             ← diagnostyka struktury pliku Word
│   └── check_pdf.py              ← diagnostyka (nieużywana, PDF odrzucony)
│
├── backend/
│   ├── main.py                   ← FastAPI app
│   ├── config.py                 ← klienty (Supabase, OpenAI, Anthropic)
│   ├── middleware.py             ← weryfikacja JWT
│   ├── routers/
│   │   ├── auth.py               ← /auth/register, /auth/login
│   │   ├── quiz.py               ← /quiz/submit
│   │   └── chat.py               ← /chat/ (wywołuje LangGraph)
│   ├── services/
│   │   ├── rag.py                ← get_embedding(), search_knowledge()
│   │   └── memory.py            ← sesje, historia, profil usera
│   └── agents/
│       └── graph.py              ← LangGraph graf (3 node'y + 1 tool)
│
└── docs/
    ├── database.md               ← schemat bazy, sesje, backup
    ├── architecture.md           ← przegląd architektury
    ├── system-prompt.md          ← PROMPT-01 do 04 (PROMPT-05 usunięty)
    ├── rag-pipeline.md           ← strategia chunkingu i retrievalu
    ├── security.md               ← luki, RODO, checklist przed deployem
    ├── mvp-plan.md               ← plan tygodniowy
    └── ADR-TYDZIEN-1.md          ← ten plik
```

---

*Następny dokument: ADR-TYDZIEN-2 (FastAPI finalizacja + Extraction Agent + Summarizer + testy integracyjne)*
