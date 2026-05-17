# Kolejne Kroki

> Aktualne priorytety, techniczny dług i potencjalne bugi do ogarnięcia.
> Ostatnia aktualizacja: 2026-04-27

---

## Co zostało zrobione (gotowe ✅)

- ✅ Sekcja "Subskrypcja" w `/settings` — status, data ważności, anulowanie z potwierdzeniem
- ✅ Endpoint `POST /payments/cancel-subscription`
- ✅ LP "Zacznij teraz" → otwiera zakładkę Rejestracja (nie Logowanie)
- ✅ Baner informacyjny w formularzu rejestracji ("Po rejestracji przejdziesz do płatności")
- ✅ Usunięty mylący komunikat o potwierdzeniu emaila
- ✅ Weryfikacja emaila — decyzja: **nie włączamy** (złamałoby auto-login po rejestracji)

---

## Priorytety — co robimy następne

### 1. Edge case'y do przetestowania ręcznie — WAŻNE ⚠️

Przed wpuszczeniem pierwszych użytkowników przetestuj te scenariusze:

**Flow podstawowy (nowe konto):**
- [ ] Rejestracja od zera → `/pricing` → Stripe Checkout → `/pricing/success` → `/quiz` → `/chat`
- [ ] Sprawdź czy `subscription_end_date` zapisuje się w Supabase po płatności
- [ ] Powracający user z aktywną subskrypcją: `/login` → `/chat` (bez `/pricing`)

**Anulowanie subskrypcji:**
- [ ] Anuluj subskrypcję w Ustawieniach → komunikat "zostanie anulowana po zakończeniu okresu" ✓ (przetestowane)
- [ ] **Co się dzieje gdy subskrypcja wygaśnie po anulowaniu** — przy kolejnym logowaniu user powinien trafić na `/pricing`
- [ ] **Czy user z `cancelled` ale wciąż w trakcie okresu** widzi coś sensownego w Ustawieniach (badge, data)
- [ ] **Podwójne kliknięcie "Anuluj"** — backend powinien zwrócić 400, nie crashować
- [ ] **Nowa subskrypcja po anulowaniu** — czy cały flow od `/pricing` działa po raz drugi na tym samym koncie

**Inne edge case'y:**
- [ ] Plan generuje się jako nowy user → potem poproś o nowy plan (był bug z `.update()` przy generowaniu)
- [ ] Wygeneruj plan, potem edytuj go w `/settings` — sprawdź czy zapis działa
- [ ] Na iOS Safari — czy Blacha odpala się po zamknięciu okna czatu

---

### 2. Monitoring i alerty (przed pierwszymi użytkownikami)

Teraz gdy jest płatny dostęp — błędy kosztują (dosłownie, ktoś zapłacił i nie może wejść).

**Minimum do zrobienia:**
- Sentry lub podobne na backendzie — alert gdy 500 na `/payments/webhook`
- Sprawdzać Railway logi po każdej płatności przez pierwsze tygodnie

---

### 3. Testy manualne pozostałe

- [ ] Sprawdź czy Pitbul przestał rekapitulować poprzednie wiadomości
- [ ] Wygeneruj kilka planów z różnymi profilami — sprawdź jakość odpowiedzi

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

### 4. Subskrypcja — badge po wygaśnięciu

Po tym jak Stripe wyśle `customer.subscription.deleted` i webhook ustawi `subscription_status = 'cancelled'` — user widzący `/settings` zobaczy badge "Anulowana". Sprawdzić czy badge i data wyświetlają się sensownie w tym stanie (a nie pusty ekran czy błąd).

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
