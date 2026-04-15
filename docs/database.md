# Baza danych — schemat, sesje, backup

> Schemat tabel w Supabase, strategia zarządzania sesjami rozmów i plan backupu danych.
>
> Data: 2026-04-14

---

## 1. Schemat bazy danych

### Przegląd tabel

```
┌──────────────────┐     ┌──────────────────┐
│      users       │────→│  user_profiles   │
│  (Supabase Auth) │     │                  │
└──────────────────┘     └──────────────────┘
         │                        │
         │                        ▼
         │               ┌──────────────────┐
         │               │ profile_changes  │
         │               │  (audit log)     │
         │               └──────────────────┘
         │
         ├───────────────────────────────────┐
         │                                   │
         ▼                                   ▼
┌──────────────────┐              ┌──────────────────┐
│ conversation_    │              │  subscriptions   │
│ sessions         │              │                  │
└────────┬─────────┘              └──────────────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│    messages      │     │ conversation_    │
│                  │     │ summaries        │
└──────────────────┘     └──────────────────┘

┌──────────────────┐     ┌──────────────────┐
│   knowledge_     │     │ training_plans   │
│   embeddings     │     │                  │
└──────────────────┘     └──────────────────┘

┌──────────────────┐
│ pending_conflicts│
└──────────────────┘
```

### Tabela: users

Zarządzana automatycznie przez Supabase Auth. Nie tworzymy jej ręcznie.

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | Generowane przez Supabase Auth |
| email | TEXT | Email użytkownika |
| created_at | TIMESTAMPTZ | Data rejestracji |
| (inne pola auth) | — | Zarządzane przez Supabase |

### Tabela: user_profiles

Profil użytkownika wypełniany z quizu (14 pytań) i aktualizowany przez Extraction Agent. Pełny opis pytań i logiki: patrz [quiz.md](quiz.md).

**Pola z quizu (wypełniane przy rejestracji):**

| Kolumna | Typ | Opis | Walidacja |
|---|---|---|---|
| id | UUID (PK) | Generowane automatycznie | — |
| user_id | UUID (FK → users.id) | Powiązanie z kontem | UNIQUE, NOT NULL |
| wiek | INTEGER | Wiek (Quiz #1) | CHECK 12-100 |
| plec | TEXT | Płeć (Quiz #2) | CHECK IN ('mezczyzna', 'kobieta') |
| wzrost | INTEGER | Wzrost w cm (Quiz #3) | CHECK 100-250 |
| waga | REAL | Waga w kg (Quiz #4) | CHECK 30-300 |
| poziom | TEXT | Poziom zaawansowania (Quiz #5) | CHECK IN ('poczatkujacy', 'srednio', 'zaawansowany') |
| cel | TEXT | Cel treningowy (Quiz #6) | CHECK IN ('masa', 'redukcja', 'sila', 'kondycja') |
| dni_treningowe | INTEGER | Dni treningowe w tygodniu (Quiz #7) | CHECK 2-6 |
| czas_treningu | TEXT | Czas na jeden trening (Quiz #8) | CHECK IN ('30-45', '45-60', '60-90', '90+') |
| miejsce_treningu | TEXT | Gdzie trenuje (Quiz #9) | CHECK IN ('silownia', 'dom', 'mieszanko') |
| dostepny_sprzet | TEXT[] | Dostępny sprzęt (Quiz #10) | Array, min 1 element |
| kontuzje | TEXT | Aktualne kontuzje (Quiz #12) | Nullable |
| ograniczenia | TEXT | Ograniczenia (Quiz #13) | Nullable |
| notatki_quiz | TEXT | Dodatkowe info od usera (Quiz #14) | Nullable |

**Pola z rozmów (wypełniane przez Extraction Agent, startują jako NULL):**

| Kolumna | Typ | Opis |
|---|---|---|
| jakosc_snu | TEXT | Wyekstrahowane gdy user wspomni o śnie |
| poziom_stresu | TEXT | Wyekstrahowane gdy user wspomni o stresie |
| dieta | TEXT | Wyekstrahowane gdy user wspomni o jedzeniu |
| aktywnosc_codzienna | TEXT | Wyekstrahowane gdy user opisze swój dzień |
| kontuzje_przeszle | TEXT | Wyekstrahowane gdy user wspomni o przeszłych urazach |
| leki | TEXT | Wyekstrahowane gdy user wspomni o lekach |
| osiagniecia | TEXT | Rekordy, postępy treningowe |
| notatki | TEXT | Inne ważne informacje z rozmów |

**Pola systemowe:**

| Kolumna | Typ | Opis |
|---|---|---|
| quiz_completed | BOOLEAN | DEFAULT false, true po wysłaniu quizu |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | Trigger on update |

### Tabela: conversation_sessions

Zarządzanie sesjami rozmów (patrz sekcja 2).

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | ID sesji |
| user_id | UUID (FK → users.id) | Właściciel sesji |
| started_at | TIMESTAMPTZ | Początek sesji |
| last_activity_at | TIMESTAMPTZ | Ostatnia aktywność |
| message_count | INTEGER | Liczba wiadomości w sesji |
| is_active | BOOLEAN | Czy sesja jest aktywna |

### Tabela: messages

Wiadomości w rozmowach.

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | ID wiadomości |
| user_id | UUID (FK → users.id) | Właściciel |
| session_id | UUID (FK → sessions.id) | Sesja rozmowy |
| role | TEXT | 'user' lub 'assistant' |
| content | TEXT | Treść wiadomości |
| created_at | TIMESTAMPTZ | Czas wysłania |

Ograniczenie: content max 2000 znaków dla roli 'user' (walidacja na backendzie, nie w bazie — agent może pisać dłużej).

### Tabela: conversation_summaries

Podsumowania historii rozmów tworzone przez Summarizer Agent.

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | — |
| user_id | UUID (FK → users.id) | UNIQUE — jedno podsumowanie per user |
| summary_text | TEXT | Treść podsumowania (max 250 słów) |
| messages_summarized | INTEGER | Ile wiadomości zostało podsumowanych łącznie |
| updated_at | TIMESTAMPTZ | Ostatnia aktualizacja |

### Tabela: knowledge_embeddings

Chunki z bazy wiedzy (RAG).

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | — |
| content | TEXT | Treść chunka |
| embedding | VECTOR(1536) | Wektor embeddingu (wymiar dla text-embedding-3-small) |
| source | TEXT | Źródło: 'ebook', 'notatki', 'artykul' |
| source_page | INTEGER | Numer strony (dla PDF) |
| section_title | TEXT | Tytuł sekcji/rozdziału |
| chunk_index | INTEGER | Kolejność chunka w dokumencie |
| created_at | TIMESTAMPTZ | Data ingestion |

### Tabela: training_plans

Plany treningowe generowane przez Plan Generator (post-MVP).

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | — |
| user_id | UUID (FK → users.id) | Właściciel |
| plan_data | JSONB | Cały plan w formacie JSON (z PROMPT-04) |
| generation_reason | TEXT | Powód wygenerowania |
| is_active | BOOLEAN | Czy aktualnie używany |
| created_at | TIMESTAMPTZ | Data wygenerowania |

### Tabela: subscriptions

Status subskrypcji Stripe (post-MVP).

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | — |
| user_id | UUID (FK → users.id) | UNIQUE |
| stripe_subscription_id | TEXT | ID subskrypcji w Stripe |
| status | TEXT | 'active', 'canceled', 'past_due' |
| valid_until | TIMESTAMPTZ | Ważność subskrypcji |
| created_at | TIMESTAMPTZ | — |
| updated_at | TIMESTAMPTZ | — |

### Tabela: pending_conflicts

Konflikty wykryte przez Extraction Agent czekające na potwierdzenie usera.

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | — |
| user_id | UUID (FK → users.id) | — |
| field | TEXT | Pole w profilu którego dotyczy |
| old_value | TEXT | Obecna wartość w profilu |
| new_value | TEXT | Nowa proponowana wartość |
| description | TEXT | Opis konfliktu z Extraction Agent |
| resolved | BOOLEAN | Czy rozwiązany |
| created_at | TIMESTAMPTZ | — |

### Tabela: profile_changes

Audit log zmian profilu — umożliwia cofnięcie błędnej ekstrakcji.

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | — |
| user_id | UUID (FK → users.id) | — |
| field | TEXT | Zmienione pole |
| old_value | TEXT | Wartość przed zmianą |
| new_value | TEXT | Wartość po zmianie |
| source | TEXT | 'quiz', 'extraction_agent', 'manual' |
| created_at | TIMESTAMPTZ | — |

### Row Level Security (RLS)

**KRYTYCZNE:** RLS musi być włączony na KAŻDEJ tabeli. Bez tego anon key daje dostęp do wszystkich danych.

Zasada ogólna: user może czytać i pisać TYLKO swoje dane (WHERE user_id = auth.uid()).

Tabele z RLS:
- user_profiles — SELECT, UPDATE: user_id = auth.uid()
- messages — SELECT, INSERT: user_id = auth.uid()
- conversation_sessions — SELECT, INSERT, UPDATE: user_id = auth.uid()
- conversation_summaries — SELECT: user_id = auth.uid()
- training_plans — SELECT: user_id = auth.uid()
- subscriptions — SELECT: user_id = auth.uid()
- pending_conflicts — SELECT: user_id = auth.uid()
- profile_changes — SELECT: user_id = auth.uid()

Tabele BEZ RLS (bo nie zawierają danych userów):
- knowledge_embeddings — dostępne dla wszystkich zalogowanych (to wiedza ogólna)

**Ważne:** Backend używa `service_role_key` do operacji zapisu w background tasks (extraction, summarization). Service key omija RLS. Anon key (frontend) jest ograniczony przez RLS.

---

## 2. Zarządzanie sesjami rozmów

### Problem

Kiedy "rozmowa" się kończy a nowa zaczyna? Jeśli user ma jedną nieskończoną rozmowę, historia rośnie w nieskończoność. Jeśli agent ładuje WSZYSTKIE wiadomości — context window się przepełni i koszty rosną.

### Rozwiązanie: sesje z automatycznym zamykaniem

**Zasada:** Nowa sesja startuje automatycznie gdy od ostatniej wiadomości usera minęło więcej niż 30 minut.

**Flow:**

1. User wysyła wiadomość
2. Backend sprawdza: czy jest aktywna sesja dla tego usera?
   - Jeśli TAK i `last_activity_at` było mniej niż 30 minut temu → kontynuuj sesję
   - Jeśli TAK ale `last_activity_at` było ponad 30 minut temu → zamknij starą sesję (is_active = false), utwórz nową
   - Jeśli NIE → utwórz nową sesję
3. Wiadomość zapisywana z session_id bieżącej sesji
4. Aktualizuj `last_activity_at` i `message_count`

**Co to zmienia dla agenta:**

- Orchestrator ładuje ostatnie 10 wiadomości Z BIEŻĄCEJ SESJI (nie globalnie)
- Podsumowanie (`conversation_summaries`) obejmuje WSZYSTKIE sesje — to pamięć długoterminowa
- Summarizer triggeruje się co 10 wiadomości GLOBALNIE (nie per sesja)

**Dlaczego 30 minut:**

- Za krótko (5 min) → user idzie na kawę, wraca, nowa sesja, agent "zapomniał" co ustalili
- Za długo (24h) → user wraca następnego dnia, historia jest gigantyczna
- 30 minut to kompromis — naturalna przerwa w rozmowie

**User NIE widzi sesji w UI.** To wewnętrzna logika backendu. Czat wygląda jak jedna ciągła rozmowa, ale backend ładuje ograniczony kontekst.

### Diagram

```
User wraca po 2 godzinach
        │
        ▼
   Sprawdź last_activity_at
        │
        ├── > 30 min temu → NOWA SESJA
        │     │
        │     ├── Orchestrator ładuje:
        │     │     summary (pamięć długoterminowa)
        │     │     + profil
        │     │     + RAG
        │     │     + 0 wiadomości z historii (nowa sesja)
        │     │
        │     └── Agent "pamięta" usera przez summary i profil
        │         ale nie pamięta detali ostatniej rozmowy
        │         (chyba że Summarizer je zapisał)
        │
        └── < 30 min temu → KONTYNUUJ SESJĘ
              │
              └── Orchestrator ładuje:
                    summary + profil + RAG
                    + ostatnie 10 msg z tej sesji
```

---

## 3. Strategia backupu danych

### Problem

Supabase free tier może spauzować po 7 dniach nieaktywności. Jeśli coś pójdzie nie tak — dane userów (profile, historie rozmów) są utracone. Na etapie MVP z 10 userami to irytujące. Na etapie produkcji z płacącymi userami to katastrofa.

### Poziomy ochrony

#### Poziom 1: Zapobieganie pauzowaniu (MVP)

Supabase free tier pauzuje po 7 dniach bez aktywności.

Rozwiązanie: cron job w n8n wysyłający prosty SELECT co 6 dni. Albo upgrade do Supabase Pro ($25/mies.) — brak pauzowania.

#### Poziom 2: Regularne backupy (post-MVP)

Supabase Pro ma automatyczne backupy (Point-in-Time Recovery). Na free tier — brak.

Rozwiązanie na free tier: skrypt w n8n eksportujący dane raz dziennie/tygodniowo.

Co eksportować:
- user_profiles — najważniejsze, to jest stan profilu usera
- conversation_summaries — pamięć długoterminowa
- training_plans — wygenerowane plany

Czego NIE trzeba backupować:
- messages — rosną szybko, a podsumowanie jest w summaries. Utrata historii wiadomości jest akceptowalna jeśli summary jest aktualna
- knowledge_embeddings — odtwarzane przez re-ingestion (skrypt)

Gdzie trzymać backup:
- JSON export do pliku na lokalnym dysku lub Google Drive
- Proste i darmowe

#### Poziom 3: Redundancja (przyszłość)

Jeśli system urośnie do setek płacących userów — rozważ replikę bazy lub backup do osobnego serwisu. Na etapie MVP to overkill.

### Usuwanie danych (RODO)

Gdy user żąda usunięcia konta, musisz usunąć WSZYSTKO:

1. messages (WHERE user_id = X)
2. conversation_sessions (WHERE user_id = X)
3. conversation_summaries (WHERE user_id = X)
4. user_profiles (WHERE user_id = X)
5. training_plans (WHERE user_id = X)
6. pending_conflicts (WHERE user_id = X)
7. profile_changes (WHERE user_id = X)
8. subscriptions (WHERE user_id = X) + cancel w Stripe
9. users (Supabase Auth delete user)

Kolejność ma znaczenie — najpierw tabele zależne (foreign keys), potem users.

MVP: robisz to ręcznie w Supabase dashboard.
Post-MVP: endpoint DELETE /account z kaskadowym usuwaniem.
