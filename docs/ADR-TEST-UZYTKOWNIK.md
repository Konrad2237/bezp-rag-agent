# ADR — Test z użytkownikiem (2026-04-18)

## Kontekst

Pierwszy test z prawdziwymi użytkownikami (kolega + brat Konrada) przed startem multi-agent refaktoru. Celem było sprawdzenie czy rejestracja, quiz i generowanie planu treningowego działają end-to-end na produkcji (Railway + Supabase).

---

## Błędy które znaleźliśmy i jak naprawiliśmy

### 1. Rejestracja — RLS na `user_profiles`

**Błąd:** `new row violates row-level security policy for table "user_profiles"` (kod 42501)

**Przyczyna:** Klient Supabase (`supabase`) był używany zarówno do `auth.sign_up()` jak i do zapisu do bazy. Po wywołaniu `sign_up()` klient podmieniał swój wewnętrzny token z service role na token nowego usera. Nowy user nie miał potwierdzonego emaila, więc sesja była null — kolejny insert szedł z anon key i RLS go blokował.

**Decyzja:** Stworzono drugi klient `supabase_admin` w `config.py` (ten sam service role key, ale nigdy nie używany do operacji auth). Wszystkie zapisy do bazy przełączono na `supabase_admin`.

---

### 2. Email rate limit przy rejestracji

**Błąd:** `email rate limit exceeded`

**Przyczyna:** Darmowy plan Supabase pozwala na max 3 emaile potwierdzające na godzinę. Podczas testów przekroczono limit.

**Decyzja:** Na czas testów wyłączono "Enable email confirmations" w Supabase Dashboard → Authentication → Settings. Na produkcję z prawdziwymi userami trzeba będzie włączyć lub przejść na płatny plan Supabase.

---

### 3. Generowanie planu — RLS na `training_plans` i urwany JSON

**Błąd 1:** `new row violates row-level security policy for table "training_plans"` — ten sam problem co przy rejestracji, `plan_generator.py` używał `supabase` zamiast `supabase_admin`.

**Błąd 2:** `json.decoder.JSONDecodeError: Unterminated string` — plan treningowy generowany przez Claude był zbyt długi i ucinał się przy limicie `max_tokens=2048`.

**Decyzja:** Zamieniono `supabase` na `supabase_admin` w `plan_generator.py`. Zwiększono `max_tokens` z 2048 do 4096.

---

### 4. RLS w pozostałych plikach

Po audycie całego backendu okazało się, że ten sam problem (użycie `supabase` zamiast `supabase_admin` do zapisów) występował we wszystkich plikach:

- `backend/services/memory.py` — `conversation_sessions`, `messages`
- `backend/routers/quiz.py` — `user_profiles`
- `backend/agents/summarizer.py` — `conversation_summaries`
- `backend/agents/extraction.py` — `pending_conflicts`, `profile_changes`
- `backend/agents/graph.py` — `training_plans`

Wszystkie przełączono na `supabase_admin`.

---

### 5. Fałszywe błędy w Railway Deploy Logs

**Obserwacja:** Railway podświetla standardowe logi startowe Uvicorn (`INFO: Application startup complete` itp.) na czerwono, co wygląda jak błędy.

**Decyzja:** Ignorować — to kosmetyka Railway, nie rzeczywiste błędy.

---

## Wynik testu

Po wszystkich poprawkach: rejestracja, quiz, rozmowa z Pitbulem i generowanie planu treningowego działają poprawnie dla nowych użytkowników.

## Co dalej

Multi-agent refaktor — Szybcior, Uszatek i Blacha jako prawdziwe agenty LangGraph z własnymi narzędziami (supervisor pattern).
