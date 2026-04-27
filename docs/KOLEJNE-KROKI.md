# Kolejne Kroki

> Aktualne priorytety, techniczny dług i potencjalne bugi do ogarnięcia.
> Ostatnia aktualizacja: 2026-04-27

---

## Priorytety — co robimy następne

### 1. Sekcja "Subskrypcja" w /settings ✅ częściowo (brak anulowania)

Stripe działa — płatności przechodzą, webhook aktywuje konto, odnowienia automatyczne.

**Co jeszcze brakuje w /settings:**
- Pokazanie aktualnego planu (tygodniowy / miesięczny / kwartalny)
- Pokazanie daty odnowienia (`subscription_end_date` z bazy)
- Przycisk "Anuluj subskrypcję" → wywołuje Stripe API → anuluje na koniec okresu

**Backend do zrobienia:**
- `POST /payments/cancel-subscription` — pobiera `stripe_customer_id` usera, wywołuje `stripe.Subscription.modify(sub_id, cancel_at_period_end=True)` (anuluje na koniec okresu, nie od razu)

**Frontend do zrobienia:**
- Sekcja w `frontend/src/app/settings/page.tsx` — aktualny plan, data ważności, przycisk anulowania z potwierdzeniem

---

### 2. Włączenie weryfikacji email w Supabase (5 minut, bez kodu)

Zrobić zanim projekt idzie do prawdziwych użytkowników.

**Gdzie:** Supabase dashboard → Authentication → Providers → Email → "Confirm email" → włącz → Save

Backend i frontend są już gotowe na ten flow (kod napisany w poprzednich sesjach).

**Uwaga:** Po włączeniu auto-login po rejestracji (`/auth/login` zaraz po `/auth/register`) przestanie działać — user będzie musiał najpierw potwierdzić email. Trzeba przetestować czy `login/page.tsx` obsługuje ten komunikat poprawnie (powinien — backend zwraca "Email nie został potwierdzony — sprawdź skrzynkę").

---

### 3. Testy manualne pełnego flow z nowym kontem

Przed wpuszczeniem pierwszych użytkowników:

- [ ] Nowe konto od zera: rejestracja → /pricing → Stripe → /pricing/success → /quiz → /chat
- [ ] Sprawdź czy `subscription_end_date` zapisuje się poprawnie w Supabase (po ostatnim fixie)
- [ ] Powracający user z aktywną subskrypcją: /login → /chat (bez przechodzenia przez /pricing)
- [ ] Wygeneruj plan jako nowy user, potem poproś o nowy plan (był bug z `.update()` — sprawdź czy naprawiony)
- [ ] Sprawdź czy Pitbul przestał rekapitulować poprzednie wiadomości
- [ ] Na iOS Safari — czy Blacha odpala się po zamknięciu okna

---

### 4. Monitoring i alerty (przed pierwszymi użytkownikami)

Teraz gdy jest płatny dostęp — błędy kosztują (dosłownie, ktoś zapłacił i nie może wejść).

**Minimum do zrobienia:**
- Sentry lub podobne na backendzie — alert gdy 500 na `/payments/webhook`
- Sprawdzić Railway logi po każdej płatności przez pierwsze tygodnie

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
