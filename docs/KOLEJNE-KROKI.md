# Kolejne Kroki — po Tygodniu 9

> Aktualne priorytety, techniczny dług i potencjalne bugi do ogarnięcia.
> Ostatnia aktualizacja: 2026-04-25

---

## Priorytety — co robimy następne

### 1. Stripe — płatności (Faza 2 MVP)

Najważniejsza rzecz zanim projekt pójdzie do użytkowników.

**Co trzeba zrobić:**
- Integracja Stripe Checkout (subscription, nie one-time payment)
- Webhook Stripe → backend — obsługa zdarzeń: `checkout.session.completed`, `customer.subscription.deleted`, `invoice.payment_failed`
- Kolumna `subscription_status` w tabeli users (lub osobna tabela)
- Middleware sprawdzający status subskrypcji przed każdym requestem do `/chat/` i `/plan/`
- Frontend: strona cennika → Stripe Checkout → redirect po sukcesie → quiz
- Obsługa wygaśnięcia — co widzi user bez aktywnej subskrypcji?

**Uwagi:**
- Quiz musi być dostępny dopiero po aktywnej subskrypcji (teraz jest dostępny po rejestracji)
- Pamiętaj o RLS — `subscription_status` to dane finansowe, tylko backend może to zapisywać

---

### 2. Strona ustawień — brakujące funkcje

Strona ustawień (`/settings`) istnieje, ale jest okrojona. Do dodania:

- **Zmiana hasła** — formularz email + nowe hasło (przez Supabase Auth)
- **Usunięcie konta** — trwałe usunięcie wszystkich danych (RODO wymaga)
- **Zmiana danych z quizu** — user może edytować wagę, cel itp. bez rozmowy z Pitbulem
- **Status subskrypcji** — data odnowienia, możliwość anulowania

---

### 3. Dłuższy test Pitbula i Szybciora

Po zmianach z Tygodnia 9 (Szybcior → Sonnet, prompt fix) — zrób kilka pełnych sesji:

- Wygeneruj kilka planów i oceń jakość (balans mięśniowy, uwzględnienie sprzętu, kontuzji)
- Sprawdź czy Pitbul przestał rekapitulować poprzednie wiadomości
- Sprawdź czy edit_plan_exercise zapisuje zmiany poprawnie (był cichy bug)
- Sprawdź jak Pitbul radzi sobie z nowymi polami z quizu (sen, stres, dieta)

---

## Do ogarnięcia — techniczny dług

### A. Audit `.update()` bez `.select()` w całym backendzie

Bug naprawiony w `edit_plan_exercise` — ale ten sam wzorzec może istnieć w innych miejscach. Warto przeszukać:

```bash
grep -rn "\.update(" backend/ | grep -v ".select("
```

Supabase-py v2: każde `.update()` bez `.select()` zwraca `data = []`. Jeśli gdzieś sprawdzamy `if not result.data:` po update — mamy potencjalny cichy błąd.

---

### B. Limit historii planów (`plan_history`)

Każda edycja ćwiczenia przez Pitbula zapisuje snapshot planu do `plan_history`. Każde generowanie planu przez Szybciora też. Po dłuższym czasie tabela może urosnąć znacząco.

- `get_plan_history()` pobiera ostatnie 5 — OK
- Ale tabela rośnie bez limitu
- Rozważyć: automatyczne usuwanie wpisów starszych niż X dni lub limit N per user

---

### C. Timeout na wywołania zewnętrzne

Brak timeoutów na:
- Supabase queries (mogą wisieć przy problemach z siecią)
- Tavily web search (zewnętrzne API)
- OpenAI embeddings (RAG)

Jeśli któreś zawiesi, cały request do `/chat/` wisi do limitu Railway (~30s). Dodać `timeout=` przy krytycznych wywołaniach.

---

### D. Rate limiting — weryfikacja

Rate limiter jest w backendzie, ale warto sprawdzić:
- Czy obejmuje `/quiz/submit` (można spamować submitem)
- Czy obejmuje `/plan/generate` (generowanie planu to drogi endpoint)
- Czy limity są sensowne dla normalnego użycia (nie blokują legalnych userów)

---

### E. Monitoring kosztów per user

Teraz LangSmith pokazuje koszty per sesja, ale nie per user_id. Jeśli jeden user generuje 50 planów dziennie — nie ma alertu.

Opcje:
- Kolumna `tokens_used` w tabeli users + increment po każdym request
- Albo n8n cron który sprawdza koszt z LangSmith API i wysyła email gdy przekroczy próg

---

## Potencjalne Bugi Do Obserwowania

### 1. Krok `cel_wagowy` — edge case przy zmianie celu

User wypełnia quiz: wybiera "masa" → wpisuje cel wagowy 95 kg → cofa się → zmienia cel na "siłę". Krok `cel_wagowy` znika z listy kroków. Dane w formularzu zostają (`form.cel_wagowy = "95"`), ale przy submicie sprawdzamy `form.cel === 'masa' || form.cel === 'redukcja'` więc cel wagowy nie trafi do backendU. Powinno być OK — ale warto przetestować ten flow ręcznie.

---

### 2. Blacha — czy triggeruje się poprawnie?

Blacha (summarizer) odpala się przez `beforeunload` (zamknięcie okna) → POST `/chat/session-end`. Na telefonie `beforeunload` bywa zawodny — może nie odpalić przy zamknięciu zakładki przez iOS Safari.

Backup: n8n cron co godzinę szuka sesji bez podsumowania od >2h. Warto sprawdzić czy n8n workflow działa i czy Blacha jest wywoływana regularnie.

---

### 3. Historia rozmów — 6 wiadomości czy to wystarczy?

`get_conversation_history(user_id, limit=6)` — Pitbul widzi tylko 6 ostatnich wiadomości. Przy dłuższych sesjach traci kontekst z początku rozmowy. Blacha ma to kompensować przez summary, ale summary aktualizuje się co 15 wiadomości.

Luka: wiadomości 7-14 w sesji mogą być "zapomniane" jeśli Blacha jeszcze nie uruchomiła się. Czy to problem w praktyce — do obserwacji.

---

### 4. Konflikt: Extraction Agent vs. dane z quizu

Uszatek może nadpisać dane które user właśnie wpisał w quizie. Przykład: user wpisał w quizie `dieta: "pilnuje"`. W rozmowie mówi "dzisiaj zjadłem śmiecia" — Uszatek może zapisać `dieta: "nie pilnuje"`. To jeden epizod, nie regularność.

Uszatek ma instrukcję "nie zapisuj jednorazowych sytuacji" — ale Haiku (który go obsługuje) może to zinterpretować różnie. Warto obserwować pole `dieta` i `jakosc_snu` w profilu po rozmowach.

---

### 5. Supabase anon key vs. service role — RLS

Backend używa dwóch klientów:
- `supabase` (anon key) — zwykłe odczyty, podlega RLS
- `supabase_admin` (service role) — zapisy, omija RLS

Jeśli coś nie zapisuje się bez błędu — sprawdź czy używasz `supabase_admin` do write operations. Cichy błąd z `supabase` (anon) przy zapisie to jeden z częstszych "gdzie dane?" problemów.

---

## Pomysły Na Przyszłość (bez terminu)

| Pomysł | Priorytet | Bloker |
|---|---|---|
| Agent Progresji — śledzenie realizacji planu | Niski | Brak infrastruktury do logowania treningów |
| Push notifications — przypomnienie o treningu | Niski | Wymaga PWA lub aplikacji mobilnej |
| Eksport planu do PDF | Średni | Brak — prosta implementacja |
| Wiele planów — user może mieć plan A i B | Niski | Wymaga refaktoru tabeli training_plans |
| Analiza postępów — wykresy z historii | Niski | Brak danych wejściowych (logowanie treningów) |
| Więcej źródeł w bazie RAG | Średni | Czas na chunking i embedding nowych materiałów |
| A/B test promptu Pitbula | Średni | Potrzeba min. 50 aktywnych userów |
