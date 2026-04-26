# ADR — Tydzień 10: Strona Ustawień, Bugfixy, Mobile UX

> Dokument decyzji architektonicznych dla Tygodnia 10 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie decyzje podjęto, jakie błędy naprawiono i dlaczego.

---

## Co zrobiliśmy

### 1. Pełny rewrite strony `/settings`

**Pliki:** `frontend/src/app/settings/page.tsx`, `backend/routers/settings.py`

**Stan przed:** Strona ustawień istniała ale była okrojona — tylko zmiana wagi i celu. Brak zmiany hasła, emaila, usunięcia konta, edycji danych z quizu.

**Stan po:** Pełna strona ustawień z dwoma sekcjami:

**Sekcja "Informacje o Tobie"** — statyczna karta z awatarem (pierwsza litera imienia), imieniem, nazwiskiem, emailem. Read-only, żeby user widział co Pitbul o nim wie.

**Sekcja "Dane z quizu"** — 14 akordeoni (jeden per pole quizowe). Każdy akordeon:
- W nagłówku pokazuje aktualną wartość pola
- Po kliknięciu rozwija formularz edycji
- Po zapisaniu zamyka się automatycznie (po 900ms, żeby user widział "Zapisano")
- Tylko jeden akordeon może być otwarty naraz (`openId: string | null`)

**Sekcja "Konto"** — 3 akcje:
- Zmiana emaila (wymaga podania obecnego hasła)
- Zmiana hasła (wymaga podania starego hasła, walidacja min. 8 znaków, stare ≠ nowe)
- Usuń konto (wymaga hasła + wpisania słowa "USUŃ", RODO art. 17)

**UX pattern — AccordionItem:**
```typescript
function AccordionItem({ id, label, currentValue, open, onToggle, children }) {
  // nagłówek klikany → toggle openId
  // currentValue widoczne w nagłówku gdy zamknięty
  // children = formularz edycji
}
```

**SaveBar** — pasek akcji pod każdym formularzem, 3 stany:
```
idle    → przycisk "Zapisz"
saving  → "Zapisuję..."
saved   → "✓ Zapisano" (zielony) → auto-zamknięcie po 900ms
error   → komunikat błędu (czerwony)
```

---

### 2. Backend settings.py — pełny rewrite

**Plik:** `backend/routers/settings.py`

**Stan przed:** Kilka endpointów, częściowa walidacja, brak tłumaczenia błędów, brak weryfikacji hasła przy zmianie emaila.

**Nowe funkcje:**

**`_verify_password(user_id, password) → bool`** — weryfikuje hasło przez bezpośredni call do Supabase REST API:
```python
res = httpx.post(
    f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
    json={"email": email, "password": password},
    headers={"apikey": SUPABASE_ANON_KEY, ...},
    timeout=10.0,
)
return res.status_code == 200
```

Dlaczego httpx zamiast supabase-py SDK? — patrz sekcja Błędy.

**`_translate_supabase_error(msg) → str`** — tłumaczy angielskie błędy gotrue na polski:
```python
if "already in use" in m or "already registered" in m:
    return "Ten adres email jest już zajęty przez inne konto"
if "weak password" in m:
    return "Hasło jest zbyt słabe — użyj min. 8 znaków"
# itd.
```

**`PATCH /settings/profile`** — obsługuje wszystkie 18 pól quizowych z walidacją zakresów i enum values. Fix supabase-py v2: `.update().select("user_id")` zamiast `.update()`.

**`DELETE /settings/account`** — usuwa dane z 8 tabel w określonej kolejności, potem usuwa auth user:
```python
for table in (
    "plan_history", "training_plans", "profile_changes",
    "pending_conflicts", "conversation_summaries",
    "messages", "conversation_sessions", "user_profiles",
):
    supabase_admin.table(table).delete().eq("user_id", user_id).execute()
supabase_admin.auth.admin.delete_user(user_id)
```

**Dlaczego kolejność ma znaczenie:** Foreign key constraints — tabele zależne muszą być usunięte przed tabelami bazowymi. `user_profiles` na końcu bo inne tabele mogą do niej referować.

**Dane po zmianie emaila:** Wszystkie tabele trzymają `user_id` (UUID), nie email. Zmiana emaila w Supabase Auth nie zmienia UUID. Dane (historia, plan, profil) zostają przypisane do tego samego konta.

---

### 3. Fix — weryfikacja hasła zawsze zwracała błąd

**Plik:** `backend/routers/settings.py`

**Problem:** User wpisywał poprawne hasło przy zmianie emaila/hasła → dostawał błąd "Nieprawidłowe hasło" mimo że hasło było identyczne jak to którego używał do logowania.

**Przyczyna:** Pierwsza wersja `_verify_password` używała `supabase.auth.sign_in_with_password()` przez SDK. Klient supabase-py ma wewnętrzny stan sesji — po wywołaniu `sign_in_with_password` w serwisie backendowym (który ma już własny token admina), SDK wchodził w konflikty stanu i rzucał wyjątek niezwiązany z credentials. Każde wywołanie kończyło się wyjątkiem → `return False`.

**Fix:** Bezpośredni call HTTP przez `httpx` do endpointu Supabase Auth REST API z ominięciem SDK:
```python
httpx.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password", ...)
```
Status 200 = hasło poprawne. Wszystko inne = błędne.

**Dlaczego to działa:** Pomijamy stan wewnętrzny SDK, rozmawiamy bezpośrednio z API. Supabase Auth REST API jest publiczne i stabilne.

---

### 4. Fix — angielskie komunikaty błędów przy zmianie emaila

**Plik:** `backend/routers/settings.py`, `backend/routers/auth.py`

**Problem:** Gdy user próbował zmienić email na już zajęty adres, dostawał surowy angielski błąd z gotrue: `"AuthApiError('Email address already in use', ...)"`.

**Przyczyna:** `raise HTTPException(400, str(e))` — `str()` na obiekcie `AuthApiError` zwraca pełny repr Pythona, nie sam tekst błędu.

**Fix w settings.py:** Filtrowanie przez `_translate_supabase_error()` przed każdym `raise`.

**Fix w auth.py — endpoint logowania:**
```python
except Exception as e:
    msg = str(e).lower()
    if "email not confirmed" in msg:
        raise HTTPException(401, "Email nie został potwierdzony — sprawdź skrzynkę...")
    if "invalid login credentials" in msg:
        raise HTTPException(401, "Błędny email lub hasło")
    raise HTTPException(401, "Błąd logowania — spróbuj ponownie")
```
Używamy `.lower()` + `in` zamiast porównania równości — działa niezależnie od formatu repr.

---

### 5. Fix — plan_generator cichy błąd przy ponownym generowaniu planu

**Plik:** `backend/agents/plan_generator.py:205`

**Problem:** Generowanie planu działało przy pierwszym użyciu. Przy każdym kolejnym (update istniejącego planu) zwracało `"Zapis planu nie powiódł się"` — mimo że plan był zapisywany do historii.

**Przyczyna:** Ten sam wzorzec co `edit_plan_exercise` z Tygodnia 9 — supabase-py v2 `.update()` bez `.select()` zwraca `data = []`. Kod sprawdzał `if not save_res.data:` → zawsze True na ścieżce update.

```python
# PRZED (bug):
save_res = supabase_admin.table("training_plans").update({...}).eq("user_id", user_id).execute()

# PO (fix):
save_res = supabase_admin.table("training_plans").update({...}).eq("user_id", user_id).select("id").execute()
```

**Zasięg buga:** Dotykał każdego użytkownika który miał już wygenerowany plan i prosił o nowy. Pierwszy plan zawsze działał (ścieżka `insert`). Dopiero drugi generował błąd.

**Audit:** Sprawdzono wszystkie 7 miejsc w backendzie z `.update()`. Tylko `plan_generator.py` miało check `if not result.data` po update. Pozostałe 6 to fire-and-forget (brak sprawdzania wyniku) — nie są bugiem.

---

### 6. Fix mobilny — nagłówek czatu

**Pliki:** `frontend/src/app/chat/page.tsx`, `frontend/src/app/plan/page.tsx`, `frontend/src/app/settings/page.tsx`

**Problem:** Na telefonie tekst "● online 24/7" pod nazwą "Pitbul" łamał się na 3 osobne wiersze (●, online, 24/7 każde w osobnej linii), bo flexbox ściskał lewą kolumnę nagłówka żeby zmieścić prawą (Chat | Plan | Ustawienia).

**Przyczyna:** Div z tekstem "Pitbul / ● online 24/7" nie miał `flex-shrink: 0` — flexbox zmniejszał jego szerokość do minimum, a tekst łamał się na każdym słowie.

**Fix:**
```tsx
// PRZED:
<div>
  <p>Pitbul</p>
  <p className="text-xs">● online 24/7</p>
</div>

// PO:
<div className="shrink-0">
  <p>Pitbul</p>
  <p className="text-xs whitespace-nowrap">● online 24/7</p>
</div>
```

`shrink-0` = div nie może być ściskany przez flex. `whitespace-nowrap` = tekst nie łamie się mid-word.

**Efekt uboczny:** Prawy side (nav + Wyloguj) zaczął być ucinany bo suma szerokości przekraczała ekran. Rozwiązanie w punkcie 7.

---

### 7. Wyloguj przeniesiony do treści strony Ustawień

**Pliki:** `frontend/src/app/chat/page.tsx`, `frontend/src/app/plan/page.tsx`, `frontend/src/app/settings/page.tsx`

**Ewolucja:**
1. Pierwotnie: Wyloguj w headerze obok Chat/Plan/Ustawienia
2. Próba 1: `hidden sm:inline` — ukrycie na mobile → zniszczono dostęp do wylogowania na telefonie
3. Próba 2: Wyloguj w headerze tylko na desktop + w settings content tylko na mobile
4. **Finalne rozwiązanie (decyzja użytkownika):** Wyloguj wyłącznie w treści strony Ustawień, zawsze widoczny, usunięty z headerów zupełnie

**Dlaczego to dobre rozwiązanie:**
- Header jest czytelny na każdym urządzeniu (tylko logo + 3 zakładki)
- Wyloguj jest w logicznym miejscu — "ustawienia konta" to właściwy kontekst
- Nie ma problemu z szerokością na mobile

---

### 8. LP — korekta liczby pytań

**Plik:** `frontend/src/app/page.tsx:189`

```tsx
// PRZED:
title: 'Odpowiadasz na 7 pytań',

// PO:
title: 'Odpowiadasz na kilkanaście pytań',
```

Quiz po rozbudowie w Tygodniu 9 ma 15-17 kroków. "7 pytań" było nieaktualne od Tygodnia 9 — przeoczono w LP.

---

## Zmiany Plików i Folderów

### Pliki zmienione

| Plik | Co się zmieniło |
|---|---|
| `backend/routers/settings.py` | Pełny rewrite: 18 pól profilowych, httpx verify password, tłumaczenie błędów, RODO delete |
| `backend/routers/auth.py` | Polskie komunikaty błędów logowania, obsługa "email not confirmed" |
| `backend/agents/plan_generator.py` | Fix: `.update().select("id")` — cichy błąd przy ponownym generowaniu planu |
| `frontend/src/app/settings/page.tsx` | Pełny rewrite: akordeony, Informacje o Tobie, zmiana emaila/hasła, usunięcie konta |
| `frontend/src/app/chat/page.tsx` | Fix header mobile: `shrink-0` + `whitespace-nowrap`; usunięcie Wyloguj |
| `frontend/src/app/plan/page.tsx` | Fix header mobile: `shrink-0` + `whitespace-nowrap`; usunięcie Wyloguj |
| `frontend/src/app/page.tsx` | LP: "7 pytań" → "kilkanaście pytań" |
| `docs/KOLEJNE-KROKI.md` | Aktualizacja: Stripe z cennikiem i checklistą, usunięcie zrobionych zadań |

### Struktura branchów (ten tydzień)

```
main
├── merge: feature/settings-redesign
│   ├── backend settings.py — pełny rewrite
│   ├── frontend settings/page.tsx — akordeony, mobile-first
│   └── fix auth.py — polskie błędy logowania
├── fix: mobile-header-quiz-count
│   ├── shrink-0 + whitespace-nowrap w 3 headerach
│   └── LP: 7 → kilkanaście pytań
├── fix: mobile-header-wyloguj
│   └── hidden sm:inline na Wyloguj + Wyloguj w settings content
├── fix: wyloguj-settings-only
│   └── Wyloguj wyłącznie w /settings, usunięty z headerów
└── fix: plan-generator-update-select
    └── .update().select("id") w plan_generator
```

---

## Decyzje Podjęte Przez Ciebie i Dlaczego

| Decyzja | Powód |
|---|---|
| Accordion zamiast osobnych stron dla edycji ustawień | Mobile-first — przewijasz listę nagłówków, rozwijasz tylko to co chcesz zmienić. Jedna strona zamiast 14 osobnych widoków |
| Pokazywać aktualną wartość w nagłówku akordeonu | User widzi co jest ustawione bez otwierania — np. "Waga — 82 kg" zamiast tylko "Waga" |
| Auto-zamknięcie akordeonu po zapisie (900ms) | UX feedback — user widzi "Zapisano" i wraca do widoku listy bez dodatkowego kliknięcia |
| Zmiana emaila wymaga potwierdzenia hasłem | Bezpieczeństwo — bez tego ktoś kto ma dostęp do odblokowanego telefonu może przejąć konto |
| Wyloguj tylko w Ustawieniach | Header na mobile jest wąski — 3 zakładki + logo to maksimum. Wyloguj logicznie pasuje do "ustawień konta", użytkownicy tego oczekują (wzorzec z większości aplikacji) |
| RODO delete usuwa dane z 8 tabel + auth user | Art. 17 RODO ("prawo do bycia zapomnianym") wymaga usunięcia wszystkich danych, nie tylko konta auth |
| Weryfikacja hasła przez httpx, nie supabase-py SDK | SDK ma problemy ze stanem sesji gdy wywołujesz sign_in w kontekście gdzie admin token jest już aktywny — httpx jest deterministyczny |

---

## Błędy Które Popełniliśmy / Znaleźliśmy

**Błąd 1: Weryfikacja hasła zawsze zwracała "złe hasło"**

Pierwsza implementacja używała supabase-py SDK do weryfikacji hasła. SDK w kontekście backendu z admin tokenem zachowywał się nieprzewidywalnie — rzucał wyjątkiem przy każdym wywołaniu `sign_in_with_password`, niezależnie od tego czy hasło było poprawne. User zgłosił że nie może zmienić emaila mimo że wpisuje dobre hasło. Debugowanie przez sprawdzenie co dokładnie SDK robi pod spodem.

**Wniosek:** Gdy SDK daje nieoczekiwane wyniki — zejdź poziom niżej i użyj REST API bezpośrednio. httpx jest prostszy do debugowania niż stan wewnętrzny klienta gotrue.

---

**Błąd 2: plan_generator — ten sam bug co edit_plan_exercise tydzień wcześniej**

Bug z `.update()` bez `.select()` w supabase-py v2 pojawił się po raz drugi w innym pliku. Tydzień wcześniej naprawiliśmy go w `edit_plan_exercise` ale nie zrobiliśmy audytu całego backendu od razu. Przez tydzień każdy user który miał już plan i generował nowy dostawał błąd "Zapis planu nie powiódł się".

**Wniosek:** Gdy znajdziesz bug wynikający z breaking change biblioteki — natychmiast wyszukaj ten wzorzec w całym projekcie (`grep -rn ".update(" backend/ | grep -v ".select("`), nie tylko naprawiaj konkretne miejsce. Zrobiliśmy to dopiero tydzień później.

---

**Błąd 3: Naprawa mobila zniszczyła przycisk Wyloguj**

Pierwsza wersja fixu nagłówka mobilnego: dodano `shrink-0` do lewej kolumny (Pitbul + status). Efekt uboczny: prawa kolumna (nav + Wyloguj) straciła miejsce i Wyloguj był ucinany. Naprawiliśmy w następnym commicie.

**Wniosek:** Przy zmianach layoutu flexbox — zawsze sprawdź co się dzieje z elementami po drugiej stronie, nie tylko tym który naprawiasz. Rozwiązanie iteracyjne: mobile → desktop → mobile, i tak kilka razy.

---

**Błąd 4: "7 pytań" na LP nieaktualne od tygodnia**

LP mówiła "Odpowiadasz na 7 pytań" mimo że quiz rozrósł się do 15-17 kroków tydzień wcześniej. Przeoczono bo LP i quiz były zmieniane w różnych sesjach, nie było "checklisty spójności" między stronami.

**Wniosek:** Po każdej zmianie flow lub zawartości (quiz, liczba kroków, cennik) — sprawdzić czy LP i strony marketingowe nie mają nieaktualnych danych.

---

## Kontekst Bezpieczeństwa — Weryfikacja Emaila

Sesja ujawniła lukę: przy rejestracji można wpisać dowolny (nieistniejący) email i od razu korzystać z aplikacji. Supabase ma opcję "Confirm email" — ale była wyłączona.

**Co jest gotowe:**
- Backend `auth.py` — zwraca polskie "Email nie został potwierdzony — sprawdź skrzynkę i kliknij link aktywacyjny" gdy gotrue zwróci "email not confirmed"
- Frontend `/login` — obsługuje ten komunikat
- Backend `/register` — zwraca "Wysłaliśmy link aktywacyjny..."

**Co wymaga ręcznej akcji (bez kodu):**
Supabase dashboard → Authentication → Providers → Email → "Confirm email" → włącz → Save

Decyzja: włączyć to dopiero gdy projekt idzie do prawdziwych użytkowników (razem ze Stripe), żeby nie blokować testowania.

---

## Co Tu Się Zadziało — Prosto (bez żargonu)

### Naprawiliśmy kilka cichych bugów

**Bug 1 — wygenerowanie nowego planu nie działało dla stałych użytkowników.** Pierwsze wygenerowanie planu zawsze działało. Ale gdy prosiłeś o nowy plan (np. po tygodniu treningów) — aplikacja mówiła "coś poszło nie tak" mimo że plan gdzieś tam się zapisał. Przyczyna: techniczna pomyłka z biblioteką bazy danych, która po aktualizacji zmieniła zachowanie jednej funkcji. Ten sam błąd naprawiliśmy tydzień wcześniej w innym miejscu — przeoczenie że ten sam wzorzec wystąpił dwukrotnie.

**Bug 2 — hasło zawsze "błędne" mimo że wpisywałeś poprawne.** Na stronie ustawień, przy próbie zmiany emaila lub hasła, aplikacja odrzucała prawidłowe hasło. Biblioteka do obsługi autoryzacji zachowywała się nieprzewidywalnie gdy pracowała równocześnie z kluczem administratora. Obeszliśmy to rozmawiając bezpośrednio z API zamiast przez bibliotekę.

**Bug 3 — angielskie komunikaty błędów.** Gdy próbowałeś zmienić email na już zajęty adres, pojawiał się angielski techniczny komunikat zamiast polskiego. Teraz wszystkie komunikaty są po polsku.

### Zbudowaliśmy stronę ustawień od nowa

Poprzednia strona ustawień miała tylko zmianę wagi i celu. Teraz masz dostęp do wszystkich danych które wpisałeś w quizie — możesz je zmienić bez ponownego przechodzenia quizu.

Wygląda to jak lista nagłówków (Waga, Cel, Sprzęt itp.). Każdy nagłówek pokazuje aktualną wartość. Klikasz → formularz się rozkłada → zmieniasz → zapisujesz → zamyka się samo. Na telefonie to jest wygodne — nie ma długich formularzy do scrollowania.

Dodaliśmy też zmianę emaila i hasła z potwierdzeniem (wymagane obecne hasło — żeby ktoś kto znajdzie odblokowany telefon nie mógł przejąć konta) oraz usunięcie konta z kompletnym czyszczeniem danych (wymagane przez RODO — każdy ma prawo do usunięcia wszystkich swoich danych).

### Naprawiliśmy wygląd na telefonie

Górny pasek nawigacji (z Pitbulem, zakładkami Chat/Plan/Ustawienia i statusem "online 24/7") wyglądał źle na małych ekranach — tekst "online 24/7" łamał się na trzy osobne wiersze przez brak miejsca. Naprawiliśmy rozkład elementów w pasku.

Przy okazji przenieśliśmy przycisk "Wyloguj" z nagłówka do strony Ustawień — to logiczniejsze miejsce i rozwiązuje problem ciasnoty na telefonie. Większość aplikacji (Spotify, Instagram itp.) też tam trzyma wylogowanie.

---

## Następne Kroki

- **Stripe — płatności** (priorytet #1 przed wdrożeniem dla użytkowników)
  - 3 plany: 19 zł/tydzień, 69 zł/miesiąc, 189 zł/3 miesiące
  - Flow: rejestracja → /pricing → Stripe Checkout → quiz → czat
- **Włączyć "Confirm email" w Supabase** (5 minut, bez kodu, razem ze Stripe)
- **Testy manualne** Pitbula i generowania planów po wszystkich zmianach
