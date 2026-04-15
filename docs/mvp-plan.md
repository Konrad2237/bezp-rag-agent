# MVP — Plan i roadmap

> Definicja Minimum Viable Product, plan tygodniowy, kryteria sukcesu i ścieżka rozbudowy.
>
> Data: 2026-04-14

---

## 1. Komponenty w MVP

### Wchodzą do MVP

| # | Komponent | Uproszczenia vs pełna wersja |
|---|---|---|
| 1 | Auth & Rejestracja | Supabase Auth "z pudełka" — email + hasło, bez OAuth |
| 2 | Quiz | 22 pytania, prosty formularz, bez animacji, bez zapisywania postępu |
| 3 | User Profile Store | Bez zmian |
| 4 | RAG Ingestion | Jednorazowy skrypt ręcznie. Tylko ebook PDF, bez dodatkowych źródeł |
| 5 | RAG Retrieval | Bez zmian |
| 6 | Conversation Store | Zapis wiadomości + jedno pole summary na usera. Bez paginacji |
| 7 | Orchestrator Agent | Bez zmian — PROMPT-01 gotowy |
| 8 | Extraction Agent | Bez zmian — PROMPT-02 gotowy |
| 9 | Summarizer Agent | Bez zmian — PROMPT-03 gotowy |
| 11 | Chat API | Bez zmian |
| 12 | Frontend | Tylko 3 strony: login, quiz, chat. Bez landing page, bez zakładki planu |
| 14 | Rate Limiter | Prosty licznik: max 30/dzień + max 5/minutę |

### Pominięte w MVP

| # | Komponent | Dlaczego | Konsekwencja |
|---|---|---|---|
| 10 | Training Plan Generator | Agent doradzaje w czacie — formalna zakładka to feature, nie core | Porady w rozmowie zamiast tabelki |
| 13 | Stripe Payments | Testujesz system, nie zarabiasz | Dostęp dla zaproszonych (invite code) |
| 15 | Monitoring | Na 10 userów ręcznie przeglądasz logi | Tabela `messages` w Supabase raz dziennie |
| 16 | n8n Automations | Niepotrzebne przy 10 userach | Reindexing ręcznie |

---

## 2. Plan tygodniowy

### Tydzień 1: Fundament (dane + RAG)

**Cel: działający RAG w terminalu — pytasz pytanie, dostajesz odpowiedź z ebooka.**

- **Dzień 1-2: Supabase setup**
  - Założenie projektu w Supabase (region EU!)
  - Włączenie pgvector
  - Stworzenie tabel: user_profiles, messages, conversation_summaries, knowledge_embeddings, conversation_sessions
  - Test ręcznego insert/select

- **Dzień 3-4: RAG Ingestion**
  - Skrypt Python: PDF na chunki (patrz [rag-pipeline.md](rag-pipeline.md) — strategia chunkingu)
  - Chunki na embeddingi (OpenAI text-embedding-3-small)
  - Embeddingi do Supabase pgvector
  - Test: similarity search w SQL

- **Dzień 5: RAG Retrieval + pierwszy test agenta**
  - Funkcja: pytanie na embedding na top 3 chunki
  - Prosty skrypt: pytanie + chunki + PROMPT-01 = odpowiedź
  - Test w terminalu: "Jaki plan dla początkującego?"

**Deliverable:** Skrypt w terminalu. Żadnego frontendu, żadnego API.

### Tydzień 2: Backend API + pamięć

**Cel: działające API — czat z agentem przez Postmana, agent pamięta kontekst.**

- **Dzień 1-2: FastAPI setup**
  - Projekt FastAPI (localhost, potem Railway)
  - Endpointy: POST /auth/register, POST /auth/login, POST /quiz, POST /chat (placeholder)
  - Middleware: user_id z JWT (nie z body!)

- **Dzień 3-4: Chat endpoint (pełny pipeline)**
  - Rate limit check (dzienny + per minutę)
  - Równoległe pobranie kontekstu (profil + summary + RAG)
  - System prompt (PROMPT-01) + streaming response
  - Zapis wiadomości + zarządzanie sesjami
  - Background: Extraction Agent (PROMPT-02) + Summarizer (PROMPT-03)
  - Test: 15 wiadomości, sprawdzenie aktualizacji profilu i summary

- **Dzień 5: Testy integracyjne**
  - Nowy user: quiz, 10 wiadomości, zamknięcie, powrót po 24h — agent pamięta?
  - "Zmieniłem cel na redukcję" — Extraction wyłapuje?
  - Pytanie spoza bazy — agent mówi "nie wiem"?

**Deliverable:** API na Railway. Rejestracja, quiz, czat z pamięcią.

### Tydzień 3: Frontend + deploy + testy

**Cel: działająca strona na Vercel.**

- **Dzień 1-3: Frontend Next.js**
  - Logowanie/rejestracja (Supabase Auth UI — gotowy komponent)
  - Quiz (22 pytania, formularz z walidacją zakresów)
  - Czat (streaming, "agent pisze...", scroll to bottom, disable po wysłaniu)
  - Routing: niezalogowany na login, brak quizu na quiz, else na chat

- **Dzień 4: Deploy + integracja**
  - Frontend na Vercel (GitHub connect)
  - Backend na Railway
  - Zmienne środowiskowe, CORS
  - Test end-to-end na produkcji

- **Dzień 5: Testy z prawdziwym użytkownikiem**
  - Sam przejdź cały flow jako nowy user
  - 2-3 znajomych — link bez instrukcji
  - Feedback + hotfixy

**Deliverable:** Link który możesz wysłać komuś i powiedzieć "zarejestruj się i pogadaj z agentem."

---

## 3. Kryteria sukcesu MVP

| # | Kryterium | Jak mierzysz | Próg sukcesu |
|---|---|---|---|
| 1 | Agent odpowiada z wiedzy, nie halucynuje | 10 pytań z ebooka + 5 spoza. Poprawne / "nie wiem" | 13/15 lub więcej |
| 2 | Pamięć działa między sesjami | Quiz, rozmowa, zamknięcie, powrót po 24h, pytanie nawiązujące | 4/5 przypadków |
| 3 | Extraction aktualizuje profil | "Zmieniłem cel na redukcję" — check w Supabase | Aktualizacja w 10 sekund |
| 4 | Czas odpowiedzi | Czas do pierwszego tokenu (streaming) | Poniżej 3 sekund |
| 5 | Ktoś obcy przechodzi cały flow | 3 znajomych bez instrukcji | 2/3 dochodzą do czatu |

---

## 4. Ścieżka od MVP do pełnego systemu

```
MVP (tydzień 1-3)
 │  Masz: auth, quiz, RAG, chat z pamięcią, deploy
 │
 ▼
FAZA 1: Training Plan Generator (~1 tydzień)
 │  PROMPT-04 + endpoint + zakładka "Plan" w frontend
 │  Główny feature — user chce plan, nie tylko porady
 │
 ▼
FAZA 2: Stripe + dostęp (~1 tydzień)
 │  Checkout, webhook, middleware subskrypcji
 │  Bez tego nie zarobisz
 │
 ▼
FAZA 3: Monitoring (~1 tydzień)
 │  Logowanie rozmów, dashboard kosztów, alerty
 │  Przed skalowaniem musisz widzieć co się dzieje
 │
 ▼
FAZA 4: n8n Automations (~1 tydzień)
 │  Przypomnienia, reindexing RAG, raport kosztów
 │  Przy >10 userów ręczne zarządzanie nie skaluje się
 │
 ▼
FAZA 5: Polerowanie (ongoing)
 │  Landing page, lepszy UX, dark mode, zdjęcia, głos
 │
 ▼
SYSTEM PEŁNY
```

---

## 5. Szacunkowy koszt utrzymania

### MVP (10 userów)

| Pozycja | Koszt miesięczny |
|---|---|
| Anthropic API (Sonnet + Haiku) | ~170 PLN |
| OpenAI Embeddings | ~0.10 PLN |
| Railway (backend) | ~15-25 PLN |
| Supabase (free tier lub Pro) | 0 lub ~100 PLN |
| Vercel (free tier) | 0 PLN |
| **Razem** | **~185-295 PLN** |

### Przy 10x (100 userów)

| Pozycja | Koszt miesięczny |
|---|---|
| Anthropic API | ~1700 PLN |
| Reszta infrastruktury | ~125 PLN |
| **Razem** | **~1825 PLN** |

Przy 100 userach koszt API przekracza budżet — wymaga podniesienia ceny subskrypcji lub routera modeli (proste pytania na Haiku, złożone na Sonnet).
