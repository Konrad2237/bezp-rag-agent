# Architektura systemu — AI Personal Trainer

> Przegląd architektury: problem, komponenty, tech stack, diagramy.
> Szczegóły poszczególnych obszarów w osobnych dokumentach.
>
> Data: 2026-04-14 | Status: Faza planowania

---

## Powiązane dokumenty

| Dokument | Zawartość |
|---|---|
| [mvp-plan.md](mvp-plan.md) | Definicja MVP, plan tygodniowy, kryteria sukcesu, roadmap |
| [adr.md](adr.md) | Architecture Decision Records (3 decyzje) |
| [database.md](database.md) | Schemat bazy danych, zarządzanie sesjami, backup |
| [rag-pipeline.md](rag-pipeline.md) | Strategia chunkingu, ingestion, retrieval |
| [security.md](security.md) | Bezpieczeństwo, RODO, stress-test, przypadki testowe, checklista |
| [ux-and-flows.md](ux-and-flows.md) | Onboarding, mobile, flow rozmów |
| [testing-and-ops.md](testing-and-ops.md) | Testowanie promptów, wersjonowanie, monitoring |
| [langgraph.md](langgraph.md) | Architektura grafu agentów, narzędzia, state, flow |
| [quiz.md](quiz.md) | 14 pytań quizu, schemat profilu, strategia zbierania danych |
| [env-variables.md](env-variables.md) | Lista zmiennych środowiskowych (backend + frontend) |
| [system-prompt.md](../system-prompt.md) | Prompty agentów (PROMPT-01 do 04) |
| [tech-stack.md](../tech-stack.md) | Szczegóły technologii |

---

## 1. Analiza problemu

### 1.1 Opis problemu

Osoby początkujące na siłowni (w tym kobiety) stają przed chaosem informacyjnym — dziesiątki sprzecznych porad od pseudotrenerów w internecie, brak personalizacji w gotowych planach treningowych i brak ciągłości w prowadzeniu (zaczynają, porzucają, zaczynają od nowa). Prowadzenie online przez prawdziwego trenera jest drogie.

### 1.2 Proponowane rozwiązanie

Autonomiczny agent AI pełniący rolę trenera personalnego, dostępny przez stronę internetową w modelu subskrypcyjnym. Agent:

- Zna użytkownika (profil z quizu + aktualizacje z rozmów)
- Pamięta kontekst między sesjami (nie zaczyna od zera po każdym wejściu)
- Odpowiada na podstawie zweryfikowanej bazy wiedzy (RAG), nie halucynuje
- Reaguje na bieżące sytuacje (ból, zmęczenie, zmiana celu)
- Układa spersonalizowane plany treningowe

### 1.3 Grupa docelowa

- Osoby początkujące na siłowni (główna grupa)
- Kobiety zaczynające trening siłowy
- Osoby wracające do treningu po dłuższej przerwie

Wykluczeni: osoby po kontuzjach wymagających rehabilitacji (ryzyko prawne).

### 1.4 Kluczowe dane liczbowe

| Parametr | Wartość |
|---|---|
| Użytkownicy na start | ~10 |
| Docelowo | ~100 |
| Częstotliwość interakcji | Kilka razy dziennie, nie codziennie |
| Baza wiedzy | Ebook PDF (~90 stron, ~10 000 słów) + notatki + linki |
| Budżet miesięczny | ~300 PLN |
| Czas na MVP | 3 tygodnie (1 osoba, z pomocą AI) |
| Monetyzacja | Subskrypcja (Stripe) |
| Język | Polski |

### 1.5 Cel projektu

Projekt portfoliowy/CV demonstrujący umiejętność budowania systemu end-to-end z RAG i agentami AI. Komercyjny sukces drugorzędny — priorytet: niezawodność i działający deploy.

---

## 2. Dekompozycja systemu

### 2.1 Lista komponentów

#### Komponent 1: Auth & Rejestracja

- **Odpowiedzialność:** Rejestracja, logowanie, zarządzanie sesją użytkownika
- **Wejście:** Email + hasło (frontend)
- **Wyjście:** JWT token sesji do frontendu; rekord użytkownika do Supabase
- **Wymaga AI:** Nie
- **Zależności:** Supabase Auth

#### Komponent 2: Quiz (zbieranie profilu)

- **Odpowiedzialność:** Zebranie 22 odpowiedzi i zapis jako strukturyzowany profil
- **Wejście:** Odpowiedzi z formularza (frontend)
- **Wyjście:** Rekord w tabeli `user_profiles`
- **Wymaga AI:** Nie
- **Zależności:** Auth

#### Komponent 3: User Profile Store

- **Odpowiedzialność:** Przechowywanie i aktualizacja danych o użytkowniku
- **Wejście:** Dane z Quizu; aktualizacje z Extraction Agent (komp. 8)
- **Wyjście:** Profil do Orchestratora i Generatora planu
- **Wymaga AI:** Nie
- **Zależności:** Supabase

#### Komponent 4: RAG Knowledge Ingestion

- **Odpowiedzialność:** Przetworzenie źródeł wiedzy na chunki z embeddingami
- **Wejście:** PDF ebooka, notatki, URL-e
- **Wyjście:** Chunki z embeddingami w tabeli `knowledge_embeddings`
- **Wymaga AI:** Tak — `text-embedding-3-small` (OpenAI)
- **Zależności:** Supabase z pgvector
- **Szczegóły:** patrz [rag-pipeline.md](rag-pipeline.md)

#### Komponent 5: RAG Retrieval

- **Odpowiedzialność:** Wyszukanie najrelevantniejszych fragmentów wiedzy dla pytania usera
- **Wejście:** Tekst wiadomości użytkownika
- **Wyjście:** Top 3-5 chunków do Orchestratora
- **Wymaga AI:** Tak — `text-embedding-3-small` (OpenAI)
- **Zależności:** RAG Ingestion (komp. 4), Supabase pgvector
- **Szczegóły:** patrz [rag-pipeline.md](rag-pipeline.md)

#### Komponent 6: Conversation Store

- **Odpowiedzialność:** Zapis wiadomości + przechowywanie podsumowań starszych rozmów
- **Wejście:** Wiadomości user/agent; podsumowania z Summarizera
- **Wyjście:** Ostatnie N wiadomości + podsumowanie do Orchestratora
- **Wymaga AI:** Nie
- **Zależności:** Supabase
- **Szczegóły:** patrz [database.md](database.md) (zarządzanie sesjami)

#### Komponent 7: Orchestrator Agent (główny agent)

- **Odpowiedzialność:** Prowadzenie rozmowy z użytkownikiem
- **Wejście:** Wiadomość usera + profil + pamięć + RAG chunki + historia
- **Wyjście:** Streaming response do usera; trigger background tasks
- **Wymaga AI:** Tak — `claude-sonnet-4-6`
- **Zależności:** Komp. 3, 5, 6

#### Komponent 8: Extraction Agent

- **Odpowiedzialność:** Ekstrakcja ważnych informacji z rozmowy do profilu
- **Wejście:** Ostatnia wymiana (user + agent) + aktualny profil
- **Wyjście:** JSON z aktualizacjami do profilu; flaga konfliktu
- **Wymaga AI:** Tak — `claude-haiku-4-5`
- **Zależności:** Komp. 3, 7 (background)

#### Komponent 9: Summarizer Agent

- **Odpowiedzialność:** Kondensacja historii rozmów co 10 wiadomości (max 250 słów)
- **Wejście:** Ostatnie 10 wiadomości + poprzednie podsumowanie
- **Wyjście:** Nowe podsumowanie do Conversation Store
- **Wymaga AI:** Tak — `claude-haiku-4-5`
- **Zależności:** Komp. 6

#### Komponent 10: Training Plan Generator

- **Odpowiedzialność:** Generowanie spersonalizowanego planu treningowego (JSON)
- **Wejście:** Profil + pamięć + RAG chunki + powód generowania
- **Wyjście:** Plan treningowy do tabeli `training_plans` i frontendu
- **Wymaga AI:** Tak — `claude-sonnet-4-6`
- **Zależności:** Komp. 3, 5, 6

#### Komponent 11: Chat API

- **Odpowiedzialność:** Orkiestracja pipeline'u, endpoint `/chat`
- **Wejście:** HTTP request z wiadomością + user_id z JWT
- **Wyjście:** SSE/streaming response; trigger background tasks
- **Wymaga AI:** Nie — koordynacja (FastAPI)
- **Zależności:** Komp. 3, 5, 6, 7, 8, 9

#### Komponent 12: Frontend (Next.js)

- **Odpowiedzialność:** UI — login, quiz, czat, plan treningowy
- **Wejście:** Dane z API
- **Wyjście:** Akcje użytkownika do backendu
- **Wymaga AI:** Nie
- **Zależności:** Auth, Chat API

#### Komponent 13: Stripe Payments

- **Odpowiedzialność:** Subskrypcje — checkout, webhook, status
- **Wejście:** Redirect na checkout; webhook z potwierdzeniem
- **Wyjście:** Status subskrypcji do middleware
- **Wymaga AI:** Nie
- **Zależności:** Auth

#### Komponent 14: Rate Limiter

- **Odpowiedzialność:** Ograniczenie wiadomości per user (dziennie + per minutę)
- **Wejście:** Request do `/chat`
- **Wyjście:** Przepuszczenie lub HTTP 429
- **Wymaga AI:** Nie
- **Zależności:** Chat API

#### Komponent 15: Monitoring & Logging

- **Odpowiedzialność:** Logowanie rozmów, kosztów API, błędów
- **Wymaga AI:** Nie
- **Szczegóły:** patrz [testing-and-ops.md](testing-and-ops.md)

#### Komponent 16: n8n Automations

- **Odpowiedzialność:** Przypomnienia, batch reindexing, alerty
- **Wymaga AI:** Nie
- **Zależności:** Supabase, komp. 4

### 2.2 Tech stack

| Warstwa | Technologia | Hosting |
|---|---|---|
| Frontend | Next.js + Tailwind CSS | Vercel (darmowy) |
| Backend | Python + FastAPI + LangGraph | Railway (~15-25 PLN/mies.) |
| Baza danych | Supabase (PostgreSQL + pgvector + Auth) | Supabase |
| Modele AI | Claude Sonnet 4.6 + Haiku 4.5 | Anthropic API |
| Embeddingi | text-embedding-3-small | OpenAI API |
| Płatności | Stripe | SaaS |
| Automatyzacja | n8n | Self-hosted |

### 2.3 Przydział modeli AI

| Zadanie | Model | Uzasadnienie |
|---|---|---|
| Orchestrator | `claude-sonnet-4-6` | Ton, personalizacja, rozumowanie |
| Extraction | `claude-haiku-4-5` | Proste zadanie, 15x tańszy |
| Summarizer | `claude-haiku-4-5` | Streszczenie, Haiku wystarczy |
| Plan Generator | `claude-sonnet-4-6` | Złożone, ale rzadkie |
| Embeddingi | `text-embedding-3-small` | Anthropic nie ma embeddingów |

### 2.4 Diagram przepływu danych

```
                         ┌─────────────┐
                         │  UŻYTKOWNIK │
                         └──────┬──────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────┐
│                   FRONTEND (Next.js / Vercel)        │
│                                                      │
│   ┌──────────┐  ┌──────────┐  ┌───────┐  ┌───────┐  │
│   │ Login/   │  │  Quiz    │  │  Chat │  │ Plan  │  │
│   │ Register │  │  Form    │  │  UI   │  │ View  │  │
│   └────┬─────┘  └────┬─────┘  └───┬───┘  └───┬───┘  │
└────────┼─────────────┼────────────┼───────────┼──────┘
         │             │            │           │
         ▼             ▼            ▼           │
┌──────────────────────────────────────────────────────┐
│              BACKEND (FastAPI / Railway)              │
│                                                      │
│  ┌─────────┐  ┌─────────┐  ┌──────────────────────┐ │
│  │Supabase │  │  Quiz   │  │    Chat API          │ │
│  │  Auth   │  │Endpoint │  │    /chat              │ │
│  └────┬────┘  └────┬────┘  └──────────┬───────────┘ │
│       │            │                  │              │
│       │            │         ┌────────┼─────────┐   │
│       │            │         ▼        ▼         ▼   │
│       │            │    ┌────────┐┌───────┐┌──────┐ │
│       │            │    │Profile ││  RAG  ││Conv. │ │
│       │            │    │ Store  ││Retriev││Store │ │
│       │            │    └───┬────┘└───┬───┘└──┬───┘ │
│       │            │        │         │       │     │
│       │            │        ▼         ▼       ▼     │
│       │            │   ┌────────────────────────┐   │
│       │            │   │   ORCHESTRATOR AGENT   │   │
│       │            │   │   claude-sonnet-4-6    │   │
│       │            │   └───────────┬────────────┘   │
│       │            │               │                │
│       │            │        ┌──────┴──────┐         │
│       │            │        ▼             ▼         │
│       │            │  ┌───────────┐ ┌───────────┐   │
│       │            │  │ EXTRACTION│ │ SUMMARIZER│   │
│       │            │  │  haiku    │ │  haiku    │   │
│       │            │  └─────┬─────┘ └─────┬─────┘   │
│       │            │        │             │         │
│       │            │        ▼             ▼         │
│  ┌────┴────────────┴────────────────────────────┐   │
│  │           SUPABASE                           │   │
│  │  ┌───────┐┌────────┐┌────────┐┌───────────┐  │   │
│  │  │users  ││profiles││messages││knowledge  │  │   │
│  │  │       ││        ││summary ││_embeddings│  │   │
│  │  └───────┘└────────┘└────────┘└───────────┘  │   │
│  │  ┌────────────┐  ┌──────────────┐            │   │
│  │  │training    │  │subscriptions │            │   │
│  │  │_plans      │  │              │            │   │
│  │  └────────────┘  └──────────────┘            │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐       │
│  │  STRIPE  │  │ RATE LIMITER │  │MONITORING│       │
│  └──────────┘  └──────────────┘  └──────────┘       │
└──────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│   n8n            │
│  - przypomnienia │
│  - re-indexing   │
│  - alerty        │
└──────────────────┘
```

### 2.5 Przepływ jednej wiadomości (happy path)

```
User wpisuje wiadomość
        │
        ▼
   Rate Limiter ──── limit? ──→ HTTP 429
        │ ok
        ▼
   Subscription check ──── brak? ──→ "Wykup subskrypcję"
        │ aktywna
        ▼
   ┌─────────────────────────────────────┐
   │  RÓWNOLEGLE pobierz kontekst:       │
   │                                     │
   │  1. Profile Store → user_profile    │
   │  2. RAG Retrieval → rag_chunks      │
   │  3. Conv. Store   → history+summary │
   └──────────────┬──────────────────────┘
                  │
                  ▼
         Orchestrator Agent
         (system prompt + kontekst + wiadomość)
                  │
                  ├──→ streaming response → user
                  │
                  ▼
          Zapis wiadomości do Conv. Store
                  │
                  ▼
   ┌─────────────────────────────────────┐
   │  BACKGROUND (nie blokuje usera):    │
   │                                     │
   │  1. Extraction Agent → update profil│
   │  2. if msg_count % 10 == 0:         │
   │     Summarizer → update summary     │
   │  3. Logging → monitoring            │
   └─────────────────────────────────────┘
```

### 2.6 Ścieżka krytyczna vs rozszerzenia

#### Ścieżka krytyczna (bez tego system nie działa)

| # | Komponent | Dlaczego |
|---|---|---|
| 1 | Auth & Rejestracja | Bez konta nie ma użytkownika |
| 2 | Quiz | Bez profilu agent nie ma danych |
| 3 | User Profile Store | Fundament — wszystko czyta profil |
| 4 | RAG Ingestion | Bez zaindeksowanej wiedzy nie ma RAG |
| 5 | RAG Retrieval | Bez retrievalu agent halucynuje |
| 6 | Conversation Store | Bez historii agent nie pamięta nic |
| 7 | Orchestrator Agent | To jest agent — bez niego nie ma produktu |
| 11 | Chat API | Łączy frontend z agentem |
| 12 | Frontend | Bez UI user nie ma jak rozmawiać |

#### Rozszerzenia (system działa bez nich, ale gorzej)

| # | Komponent | Co tracimy |
|---|---|---|
| 8 | Extraction Agent | Profil się nie aktualizuje automatycznie |
| 9 | Summarizer Agent | Historia rośnie w nieskończoność lub agent traci pamięć |
| 10 | Training Plan Generator | Brak formalnego planu w zakładce |
| 13 | Stripe Payments | System działa, tylko nie zarabia |
| 14 | Rate Limiter | Jeden user może wypalić budżet API |
| 15 | Monitoring | Nie wiesz czy agent gada głupoty |
| 16 | n8n Automations | Brak przypomnień, ręczny reindexing |

---

*Szczegóły poszczególnych obszarów w powiązanych dokumentach (patrz tabela na początku).*
