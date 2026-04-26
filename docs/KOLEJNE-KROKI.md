# Kolejne Kroki

> Aktualne priorytety, techniczny dług i potencjalne bugi do ogarnięcia.
> Ostatnia aktualizacja: 2026-04-26

---

## Priorytety — co robimy następne

### 1. Stripe — płatności (Faza 2 MVP)

Najważniejsza rzecz zanim projekt pójdzie do użytkowników.

**Cennik (3 plany):**
- 19 zł / tydzień
- 69 zł / miesiąc
- 189 zł / 3 miesiące

**Konto Stripe:**
- Użytkownik ma już konto Stripe z innym projektem.
- Przed startem sprawdzić czy dodać nowy produkt w tym samym koncie (Stripe pozwala mieć wiele produktów/projektów), czy lepiej założyć osobne konto.
- Zaczynamy od Test mode — można testować bez prawdziwych kart.

**Flow użytkownika po wdrożeniu:**
```
LP → "Zacznij teraz" → /login (zakładka Rejestracja)
→ po rejestracji: redirect → /pricing
→ wybór planu → Stripe Checkout
→ webhook → subscription_status = 'active'
→ redirect → /quiz → /chat
```

**Po zalogowaniu (istniejący user):**
```
/login → has_subscription?
  tak + has_profile → /chat
  tak + brak profilu → /quiz
  nie → /pricing
```

**Co trzeba zrobić — backend:**
- [ ] Kolumna `subscription_status` w `user_profiles` (wartości: `null`, `'active'`, `'cancelled'`, `'past_due'`)
- [ ] Kolumna `subscription_end_date` — kiedy wygasa
- [ ] Kolumna `stripe_customer_id` — żeby łączyć webhooki z userem
- [ ] Endpoint `POST /payments/create-checkout-session` → tworzy sesję Stripe Checkout
- [ ] Endpoint `POST /payments/webhook` → obsługuje zdarzenia Stripe:
  - `checkout.session.completed` → ustaw `subscription_status = 'active'`
  - `customer.subscription.deleted` → ustaw `subscription_status = 'cancelled'`
  - `invoice.payment_failed` → ustaw `subscription_status = 'past_due'`
- [ ] Middleware/guard na `/chat/` i `/quiz/submit` sprawdzający `subscription_status`
- [ ] RLS — `subscription_status` może zapisywać tylko backend (service role), nie user

**Co trzeba zrobić — frontend:**
- [ ] Strona `/pricing` — 3 kafelki z planami, przyciski "Wybierz"
- [ ] Po rejestracji redirect do `/pricing` zamiast tylko komunikatu
- [ ] Po logowaniu: sprawdzenie subskrypcji przed przekierowaniem
- [ ] Strona `/pricing/success` — ekran potwierdzenia po zapłacie
- [ ] W `/settings` — sekcja "Subskrypcja": aktualny plan, data odnowienia, przycisk anulowania

**Co trzeba zrobić — Stripe dashboard:**
- [ ] Stworzyć 3 produkty (lub 1 produkt z 3 cenami)
- [ ] Skopiować Price IDs do `.env`
- [ ] Skonfigurować webhook URL: `https://twoja-domena/payments/webhook`
- [ ] Skopiować Webhook Secret do `.env`

**Zmienne środowiskowe do dodania:**
```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_WEEK=price_...
STRIPE_PRICE_MONTH=price_...
STRIPE_PRICE_QUARTER=price_...
```

**Uwagi:**
- Quiz dostępny dopiero po aktywnej subskrypcji
- Co z userami którzy już mają profil (testy)? Można im ręcznie ustawić `subscription_status = 'active'` w Supabase
- Przy anulowaniu: dostęp do końca okresu rozliczeniowego (nie od razu wycinać)

---

### 2. Włączenie weryfikacji email w Supabase (5 minut, bez kodu)

Zrobić zanim projekt idzie do prawdziwych użytkowników.

**Gdzie:** Supabase dashboard → Authentication → Providers → Email → "Confirm email" → włącz → Save

Backend i frontend są już gotowe na ten flow (kod napisany, przetestowany).

---

### 3. Testy manualne Pitbula i Szybciora

Po wszystkich zmianach z Tygodnia 9 + bugfixach warto zrobić kilka pełnych sesji:

- Wygeneruj plan jako nowy user i jako user który już ma plan (był bug z `.update()` — właśnie naprawiony)
- Sprawdź czy Pitbul przestał rekapitulować poprzednie wiadomości
- Sprawdź jak reaguje na nowe pola quizu (sen, stres, dieta)
- Sprawdź czy Blacha odpala się po zamknięciu okna (na desktop)
- Na iOS Safari — Blacha może nie odpalić przez `beforeunload`; backup: n8n cron co godzinę szuka sesji bez podsumowania od >2h — sprawdzić czy workflow działa

---

## Do ogarnięcia — techniczny dług

### A. Timeouty na wywołania zewnętrzne

Brak timeoutów na:
- Supabase queries (mogą wisieć przy problemach z siecią)
- Tavily web search (zewnętrzne API)
- OpenAI embeddings (RAG)

Jeśli któreś zawiesi, cały request do `/chat/` wisi do limitu Railway (~30s). Dodać `timeout=` przy krytycznych wywołaniach.

---

### B. Rate limiting — weryfikacja

Rate limiter jest w backendzie, ale warto sprawdzić:
- Czy obejmuje `/quiz/submit` (można spamować submitem)
- Czy obejmuje `/plan/generate` (generowanie planu to drogi endpoint)
- Czy limity są sensowne dla normalnego użycia (nie blokują legalnych userów)

---

### C. Limit historii planów (`plan_history`)

Każda edycja i generowanie zapisuje snapshot do `plan_history`. Po dłuższym czasie tabela rośnie bez limitu.

- `get_plan_history()` pobiera ostatnie 5 — OK
- Rozważyć: automatyczne usuwanie wpisów starszych niż X dni lub limit N per user

---

### D. Monitoring kosztów per user

LangSmith pokazuje koszty per sesja, ale nie per user_id. Opcje:
- Kolumna `tokens_used` w tabeli users + increment po każdym request
- n8n cron sprawdzający koszt z LangSmith API, email-alert gdy przekroczy próg

---

## Potencjalne Bugi Do Obserwowania

### 1. Krok `cel_wagowy` — edge case przy zmianie celu

User wybiera "masa" → wpisuje cel wagowy → cofa się → zmienia cel na "siłę". Dane w formularzu zostają, ale przy submicie nie trafiają do backendu (warunek `form.cel === 'masa' || form.cel === 'redukcja'`). Powinno być OK — ale warto przetestować ten flow ręcznie.

---

### 2. Historia rozmów — 6 wiadomości

`get_conversation_history(limit=6)` — przy dłuższych sesjach wiadomości 7-14 mogą być "zapomniane" zanim Blacha uruchomi się po raz pierwszy (co 15 wiadomości). Do obserwacji w praktyce.

---

### 3. Konflikt: Extraction Agent vs. dane z quizu

Uszatek może nadpisać dane wpisane w quizie na podstawie jednorazowej wzmianki w rozmowie. Instrukcja "nie zapisuj jednorazowych sytuacji" — ale Haiku może to interpretować różnie. Obserwować pola `dieta` i `jakosc_snu` po rozmowach.

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
