# ADR — Stripe: Poprawki i Debugowanie Integracji

> Dokument decyzji architektonicznych — sesja debugowania i uproszczenia integracji Stripe.
> Data: 2026-04-27

---

## Co zrobiliśmy — technicznie

### 1. Uproszczenie flow płatności — usunięcie guest checkout

**Problem:** Poprzednia implementacja miała dwa równoległe flow:
- **Guest checkout** (`POST /payments/create-checkout-session-guest`) — płatność bez konta, potem rejestracja. Wymagał tabeli `pending_subscriptions` w Supabase i matchowania emaili między płatnością a rejestracją.
- **Authenticated checkout** (`POST /payments/create-checkout-session`) — płatność po zalogowaniu.

Oba flow wchodziły w konflikty. Guest checkout wymagał tabeli `pending_subscriptions` której prawdopodobnie nie było, a aktywacja subskrypcji zachodziła dopiero przy pierwszym wywołaniu `/auth/me` — które nigdzie nie było wywoływane po przekierowaniu na `/pricing`.

**Decyzja:** Usunąć guest checkout. Jeden flow: **rejestracja → /pricing → Stripe → /pricing/success (polling) → /quiz**.

**Zmiany plików:**

| Plik | Co się zmieniło |
|---|---|
| `backend/routers/payments.py` | Usunięto endpoint `POST /payments/create-checkout-session-guest` i całą logikę `pending_subscriptions` w handlerze webhooka |
| `backend/routers/auth.py` | Usunięto z endpointu `GET /auth/me` lookup do tabeli `pending_subscriptions` i logikę aktywacji po emailu |
| `frontend/src/app/login/page.tsx` | Usunięto całą logikę `?paid=1` (parametr query blokujący dostęp do zakładki Rejestracja), obie zakładki Logowanie/Rejestracja zawsze widoczne, usunięto `useSearchParams` i związane stany |
| `frontend/src/app/pricing/page.tsx` | Pełny rewrite — usunięto ścieżkę guest checkout, brak tokenu → `router.push('/login')`, zawsze wywołuje authenticated endpoint z JWT |

---

### 2. Diagnoza i fix — `subscription_status: 'ACTIVE'` vs `'active'`

**Problem:** Po ręcznym ustawieniu `subscription_status = 'ACTIVE'` w Supabase (wielkie litery) user po zalogowaniu trafiał na `/pricing` zamiast `/chat`.

**Przyczyna:** Kod w `login/page.tsx` (`routeAfterLogin`) i w `chat/page.tsx` (`checkAuth`) porównuje `=== 'active'` (małe litery). Ręczny wpis 'ACTIVE' nie pasuje.

**Rozwiązanie:** Nie zmiana kodu, a poprawka danych testowych w Supabase:
```sql
UPDATE user_profiles SET subscription_status = 'active' WHERE subscription_status = 'ACTIVE';
```
Webhook zawsze zapisuje małe litery (`"subscription_status": "active"`) — problem dotyczy tylko ręcznych wpisów testowych. Produkcja nie jest zagrożona.

---

### 3. Fix krytyczny — `AttributeError: get` na `StripeObject` w webhoku

**Problem:** Webhook `POST /payments/webhook` zwracał 500 Internal Server Error dla każdego eventu `checkout.session.completed`. Railway logi pokazywały:
```
File "/app/routers/payments.py", line 85, in stripe_webhook
    user_id = data.get("client_reference_id") or data.get("metadata", {}).get("user_id")
AttributeError: get
```

**Przyczyna:** `stripe.Webhook.construct_event()` zwraca obiekt `StripeObject` (własny typ stripe-python). W stripe-python v5+ `StripeObject` nie wspiera metody `.get()` — próba wywołania `data.get(...)` powoduje `AttributeError` bo `__getattr__` próbuje znaleźć klucz `'get'` w danych obiektu.

**Fix:** Po weryfikacji podpisu parsujemy `payload` jako zwykły Python dict przez `json.loads()`. Weryfikacja kryptograficzna nadal odbywa się przez `stripe.Webhook.construct_event()` (to jest poprawne), a do czytania danych używamy zwykłego słownika.

```python
# PRZED (bug):
event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
data = event["data"]["object"]  # StripeObject — .get() nie działa
user_id = data.get("client_reference_id")  # AttributeError

# PO (fix):
event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
event_dict = json.loads(payload)  # plain Python dict
data = event_dict["data"]["object"]
user_id = data.get("client_reference_id")  # działa
```

**Plik:** `backend/routers/payments.py` — dodano `import json`, zmieniono linię `event_type = event["type"]` i `data = event["data"]["object"]` na wersję z `event_dict`.

---

### 4. Fix — `subscription_end_date` nie zapisywało się do Supabase

**Problem:** Po naprawieniu webhooka subskrypcja aktywowała się poprawnie (`subscription_status = 'active'`), ale `subscription_end_date` pozostawało `null`.

**Przyczyna:** `stripe.Subscription.retrieve(subscription_id)` zwraca `StripeObject`. W bloku try/except kod wywołuje `sub.get("current_period_end")` — ta sama sytuacja co wyżej, `.get()` rzuca wyjątek, except łapie go i `end_dt = None`. Subskrypcja aktywuje się (bo `update_data` z `subscription_status` jest poza try/except), ale data końca nie.

Dodatkowo Stripe API `2026-04-22.dahlia` przeniosło `current_period_end` z poziomu subskrypcji do `items.data[0].current_period_end`.

**Fix:** Zamiast `.get()` używamy dict-style access `sub["current_period_end"]` z try/except, z fallbackiem na nową lokalizację w API:

```python
try:
    end_timestamp = sub["current_period_end"]
except (KeyError, TypeError):
    end_timestamp = None
if not end_timestamp:
    try:
        end_timestamp = sub["items"]["data"][0]["current_period_end"]
    except (KeyError, TypeError, IndexError):
        end_timestamp = None
```

**Plik:** `backend/routers/payments.py` — blok `if subscription_id and user_id`.

---

### 5. Merge na main i deployment

Wszystkie commity z brancha `feature/stripe-frontend-flow` zmergowane na `main` (fast-forward, bez merge commitów). Railway śledziło `main` — branch nigdy nie był na remote, więc poprzednie kody nie dochodziły do produkcji.

Kolejność commitów na main po sesji:
- `refactor: uprość flow Stripe — rejestracja przed płatnością`
- `fix: webhook — parsuj payload jako JSON dict zamiast StripeObject`
- `fix: subscription_end_date — użyj dict-style access na StripeObject`

---

## Aktualny flow użytkownika (po poprawkach)

```
Nowy user:
LP → /pricing → (brak tokenu?) → /login → Rejestracja → auto-login → /pricing
  → Wybierz plan → POST /payments/create-checkout-session (JWT)
  → Stripe Checkout → zapłać
  → /pricing/success (polling /auth/me co 1s, max 15s)
  → webhook: subscription_status = 'active', subscription_end_date = ISO datetime
  → /quiz → /chat

Powracający user:
  /login → POST /auth/login → GET /auth/me → routeAfterLogin:
    active + quiz_completed=true  → /chat
    active + quiz_completed=false → /quiz
    null / cancelled / past_due   → /pricing

Odnowienie subskrypcji (automatyczne):
  Stripe pobiera kartę → invoice.payment_succeeded → subskrypcja trwa
  Stripe nie może pobrać → invoice.payment_failed → subscription_status = 'past_due'
  Stripe anuluje po próbach → customer.subscription.deleted → subscription_status = 'cancelled'
```

---

## Decyzje techniczne

| Decyzja | Powód |
|---|---|
| Rejestracja przed płatnością (nie odwrotnie) | Guest checkout wymagał `pending_subscriptions` + matchowania emaili + timing webhooka — zbyt wiele ruchomych części. Każdy normalny SaaS rejestruje najpierw. Prawdziwy paywall to backend guard, nie brama rejestracji. |
| `json.loads(payload)` zamiast `event["data"]["object"]` | `StripeObject` w stripe-python v5+ nie wspiera `.get()`. `json.loads` daje zwykły dict, nie traci się weryfikacji podpisu (ta odbywa się przez `construct_event`). |
| Dict-style access `sub["key"]` zamiast `.get()` na Subscription | Ten sam powód — `stripe.Subscription.retrieve()` też zwraca `StripeObject`. Używamy `[]` z try/except zamiast `.get()`. |
| Brak tabeli `pending_subscriptions` w nowym flow | Tabela była potrzebna tylko dla guest checkout — po usunięciu go jest zbędna. Aktywacja subskrypcji zawsze przez `client_reference_id = user_id` w sesji Checkout. |

---

## Błędy które popełniliśmy / znaleźliśmy

**Błąd 1: Dwutorowe flow płatności**
Poprzednia implementacja próbowała obsługiwać "zapłać przed rejestracją" przez osobny endpoint i tabelę `pending_subscriptions`. Efekt: user płacił, rejestrował się, trafiał na `/pricing` ze statusem null i mógł zapłacić drugi raz. Aktywacja nigdy nie zachodziła bo `/pricing` nie woła `/auth/me`.

**Wniosek:** "Zapłać przed rejestracją" wymaga race condition handling (co jeśli webhook dotrze przed rejestracją?), matchowania emaili i dodatkowych tabel. Standardowe "zarejestruj się, potem zapłać" eliminuje wszystkie te problemy.

**Błąd 2: Brak sprawdzenia `meRes.ok` po `/auth/me` w login**
`handleLogin` w `login/page.tsx` wołał `/auth/me` ale nie sprawdzał `res.ok`. Jeśli request się nie powiódł, `meData.subscription_status` było `undefined` i user zawsze trafiał na `/pricing`.

**Wniosek:** Zawsze sprawdzaj `res.ok` przed czytaniem `res.json()` w fetch calls.

**Błąd 3: `StripeObject.get()` — breaking change w stripe-python v5+**
Poprzedni kod używał `.get()` na obiektach zwróconych przez stripe library. W v5+ `StripeObject` nie jest dict-like — `.get()` nie istnieje jako metoda. Błąd był cichy w jednym miejscu (try/except łapał, `end_dt = None`), krytyczny w innym (webhook crashował z 500).

**Wniosek:** Przy upgrade stripe-python (albo dowolnej zewnętrznej biblioteki) sprawdź czy obiekty zwrócone przez API nadal wspierają operacje słownikowe. Użyj `sub["key"]` lub `getattr(sub, "key", None)` zamiast `sub.get("key")`.

**Błąd 4: Feature branch nigdy nie był na remote**
Przez całą sesję Railway deployowało stary kod z `main`. Wszystkie poprawki były lokalne. Każdy "Resend" webhooka w Stripe uderzał w stary kod.

**Wniosek:** Po każdym commicie który ma trafić na produkcję — sprawdź czy branch jest na remote i czy Railway go śledzi. `git push origin <branch>` to osobny krok od `git commit`.

---

## Co tu się zadziało — prostym językiem

### Dlaczego Stripe nie działał

Poprzednia wersja próbowała zrobić coś ambitnego: żebyś płacił **zanim** założysz konto. W teorii fajne, w praktyce — koszmar logistyczny. System musiał "zapamiętać" że zapłaciłeś, potem gdy się rejestrowałeś — dopasować Twój email do płatności i aktywować konto. Każdy krok mógł się nie powieść i żaden błąd nie był widoczny — system po prostu wracał Cię do cennika.

### Co zmieniliśmy

Uprościliśmy do czegoś oczywistego: **najpierw zakładasz konto, potem płacisz**. Tak działa Spotify, Netflix, każdy normalny serwis. Twoje konto istnieje zanim Stripe o nim wie — więc gdy płatność przechodzi, Stripe dokładnie wie komu aktywować dostęp.

### Dlaczego dalej nie działało (trzy bugfixy)

Po uproszczeniu flow były trzy osobne bugi:

**Bug 1 — wielkie vs małe litery.** Ręcznie wpisałeś `ACTIVE` w bazie danych, a kod sprawdza `active`. Literówka. Produkcja (przez normalny flow płatności) zawsze wpisuje małe litery automatycznie.

**Bug 2 — biblioteka Stripe zmieniła API.** Nowa wersja biblioteki Stripe dla Pythona zmieniła sposób w jaki można czytać dane z obiektów które zwraca. Stary kod używał `.get()` — nowa wersja tego nie obsługuje i crashowała z błędem 500 (czyli serwer padał) przy każdej próbie potwierdzenia płatności. Naprawiliśmy przez samodzielne parsowanie danych ze Stripe zamiast polegania na ich obiekcie.

**Bug 3 — data ważności subskrypcji.** Ten sam problem co wyżej, ale w innym miejscu — pobieranie daty do kiedy masz subskrypcję używało tego samego złego sposobu. Naprawiliśmy, teraz `subscription_end_date` zapisuje się poprawnie.

### Jak to teraz działa

1. Wchodzisz na stronę → **Wybierz plan** → jeśli nie masz konta → formularz rejestracji
2. Rejestrujesz się → automatycznie się logujesz → wracasz do cennika
3. Klikasz "Wybierz" → Stripe Checkout (bezpieczna strona płatności Stripe)
4. Płacisz → Stripe informuje nasz serwer o udanej płatności (webhook)
5. Serwer zapisuje w bazie że masz aktywną subskrypcję
6. Strona ładowania sprawdza co chwilę czy subskrypcja jest aktywna → gdy tak → wchodzisz do quizu

### Jak działa odnawianie i anulowanie

Stripe robi wszystko automatycznie — Ty nic nie musisz robić. Co tydzień/miesiąc/kwartał Stripe sam pobiera pieniądze z karty. Jak mu się uda — subskrypcja trwa. Jak nie — kilka prób, potem anulowanie. Nasz serwer dostaje informację o każdym zdarzeniu i aktualizuje bazę.
