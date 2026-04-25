# ADR — Tydzień 9: Bugfixy, Rozbudowa Quizu, Optymalizacje Agentów

> Dokument decyzji architektonicznych dla Tygodnia 9 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie decyzje podjęto, jakie błędy naprawiono i dlaczego.

---

## Co zrobiliśmy

### 1. Scalenie zmian z Tygodnia 8 na `main`

Na początku sesji okazało się że zmiany z poprzedniego tygodnia (refactor agentów, optymalizacja kosztów) leżały na branchu `feature/prompt-refactor-cost-opt` i nigdy nie zostały zmergowane na `main`. Scalone ręcznie.

**Zawartość merge'a (6 commitów):**

| Commit | Co |
|---|---|
| `44bc6b6` | Refactor promptu, Sonnet 4.6, równoległe zapytania Supabase |
| `39183b5` | Szybcior bez tool calls — RAG pre-injected, Haiku, 1 LLM call |
| `9e4153f` | Uszatek i Blacha — LangGraph → chain (1 LLM call każdy) |
| `c774150` | Fix formatu planu — nawiasy przy seriach/powtórzeniach |
| `1a50938` | Szybcior max_tokens 2048 → 4096 (JSON urywał się) |
| `0dd5ae2` | Uszatek JSON fallback — raw_decode zamiast crash przy Extra data |

---

### 2. Fix — `edit_plan_exercise` cicho nie zapisywał zmian

**Plik:** `backend/agents/graph.py:141`

**Problem:** Narzędzie Pitbula do edycji ćwiczeń w planie zwracało string `"BŁĄD: Zapis do bazy nie powiódł się"` — ale Pitbul ignorował ten komunikat i mówił userowi `"zmiana zrobiona"`. W logach zero błędów, user odświeżał zakładkę Plan i nie widział zmian.

**Przyczyna:** W `supabase-py` v2.x metoda `.update()` bez `.select()` zwraca `data = []`. Kod sprawdzał `if not update_res.data:` — zawsze True, zawsze BŁĄD — ale model językowy nie reagował na błąd narzędzia poprawnie.

```python
# PRZED (bug):
update_res = _supabase.table("training_plans").update({"plan_data": plan}).eq("id", plan_id).execute()

# PO (fix):
update_res = _supabase.table("training_plans").update({"plan_data": plan}).eq("id", plan_id).select("id").execute()
```

`.select("id")` wymusza zwrot wiersza po update — jeśli pusty, update naprawdę się nie udał.

---

### 3. Szybcior: Haiku → Sonnet 4.6

**Plik:** `backend/agents/plan_generator.py`

**Problem:** Plany generowane przez Szybciora były złej jakości — zły balans grup mięśniowych, ignorowanie sprzętu i kontuzji, ogólnikowość. Haiku (najtańszy model) był za słaby do złożonego wnioskowania o planach treningowych.

**Decyzja:** Przejście na `claude-sonnet-4-6`. Szybcior odpala się rzadko (tylko gdy user prosi o plan), więc różnica kosztu jest pomijalna (kilka groszy za generowanie), a różnica jakości — wyraźna.

```python
# PRZED:
model="claude-haiku-4-5-20251001"

# PO:
model="claude-sonnet-4-6"
```

---

### 4. Rozbudowa Quizu — 3 kroki → 16/17 kroków

**Plik:** `frontend/src/app/quiz/page.tsx` + `backend/routers/quiz.py`

**Kontekst decyzji:** Pierwotnie quiz był krótki celowo — żeby użytkownicy z TikToka nie odpadli przy rejestracji. Zmiana modelu biznesowego: quiz wypełnia się DOPIERO po wykupieniu subskrypcji, więc user który zapłacił jest zmotywowany i gotowy podać więcej informacji.

**Architektura kroków:**

Zamiast `TOTAL_STEPS = stała liczba` — system oparty na liście ID kroków (`StepId[]`) generowanej dynamicznie z aktualnego stanu formularza. Dzięki temu krok `cel_wagowy` może pojawiać się lub znikać bez resetowania postępu.

```typescript
function getStepList(cel: string): StepId[] {
  const steps = ['wiek_plec', 'wzrost_waga', 'doswiadczenie', 'cel']
  if (cel === 'masa' || cel === 'redukcja') steps.push('cel_wagowy') // warunkowy
  steps.push('dni', 'czas', 'miejsce', 'sprzet', 'kontuzje',
             'ograniczenia', 'sen', 'aktywnosc', 'stres', 'dieta',
             'osiagniecia', 'notatki')
  return steps
}
```

**Nowe ekrany i pytania:**

| Krok | Pytanie | Nowe? |
|---|---|---|
| wiek_plec | Wiek + płeć | — (było w 1 ekranie, teraz osobno) |
| wzrost_waga | Wzrost + aktualna waga | — (osobno) |
| doswiadczenie | Poziom (3 opcje) | — |
| cel | Cel treningowy (4 opcje) | — |
| **cel_wagowy** | Docelowa waga (conditional) | **NOWE** |
| dni | Ile dni w tygodniu | — (osobno) |
| czas | Czas treningu | — (osobno) |
| miejsce | Siłownia / dom / mieszanko | — |
| sprzet | Multi-select sprzętu | rozszerzony |
| kontuzje | Tak/nie + textarea | — |
| ograniczenia | Tak/nie + textarea | — |
| **sen** | Jakość snu (4 opcje) | **NOWE** |
| **aktywnosc** | Aktywność codzienna (3 opcje) | **NOWE** |
| **stres** | Poziom stresu (4 opcje) | **NOWE** |
| **dieta** | Podejście do diety (4 opcje) | **NOWE** |
| **osiagniecia** | Wyniki/rekordy (textarea, opcjon.) | **NOWE** |
| notatki | Wolne pole (opcjon.) | — |

**Nowy sprzęt w multi-select:**
- Wyciąg (kablowy) — był brak
- Ławka pozioma — był brak
- Ławka skośna — był brak

**Logika "brak sprzętu":** Wybór "Własna masa ciała" automatycznie odznacza resztę opcji i odwrotnie.

**Fix walidacji kontuzji/ograniczeń:** Gdy user zaznaczy "Tak" przy kontuzjach lub ograniczeniach, textarea jest obowiązkowa. Poprzednio można było kliknąć "tak" i przejść dalej bez wpisania niczego — Pitbul widział że ktoś ma kontuzję ale nie wiedział jaką.

**Pola nowe w backendzie** (`backend/routers/quiz.py`):
```python
jakosc_snu: Optional[str] = None
aktywnosc_codzienna: Optional[str] = None
poziom_stresu: Optional[str] = None
dieta: Optional[str] = None
osiagniecia: Optional[str] = None
```

Cel wagowy trafia do `notatki_quiz` jako tekst ("Cel redukcji: 80 kg") — nie wymaga nowej kolumny w bazie.

**UX — mobile-first:**
- Każdy krok to jeden temat, jeden ekran — nie ma scrollowania przez listę pytań
- Card buttons zamiast `<select>` — klikalny kafelek z podtytułem i zielonym checkmarkiem
- Progress bar neon green (`#00FF88`) z procentem
- `active:scale-[0.98]` na przyciskach — haptyczny tap feedback na telefonie

---

### 5. Fix Promptu Pitbula — Rekapitulacja Poprzedniej Wiadomości

**Plik:** `backend/agents/graph.py` — sekcja `PITBUL_STATIC_PROMPT`, sekcja FORMAT

**Problem (zidentyfikowany ze screenshota):** User zapytał "skąd bierzesz wiedzę?" → Pitbul odpowiedział. Następnie user zapytał "a robisz coś poza planem?" — Pitbul w odpowiedzi najpierw powtórzył całą poprzednią odpowiedź o źródłach wiedzy (z bulletami, nagłówkami), a dopiero potem odpowiedział na nowe pytanie. Zbędne tokeny, zbędna latencja, wygląda jakby nie widział historii rozmowy.

**Przyczyna:** Model domyślnie "recapuje" kontekst gdy nowe pytanie jest krótkie i zaczyna się od "a" (sugeruje kontynuację). Nie ma instrukcji która by to blokowało.

**Fix:** Jedno zdanie do sekcji FORMAT — zasada zamiast reguły:

```
Zakładaj że user przeczytał Twoją ostatnią wiadomość — nie wracaj do niej chyba że musisz coś skorygować.
```

Nie "nigdy nie powtarzaj" (za ostre — blokuje naturalne dopowiedzenia), ale zmiana domyślnego założenia: user wie co Pitbul napisał, nie trzeba mu tego przypominać.

---

## Zmiany Plików i Folderów

### Pliki zmienione

| Plik | Co się zmieniło |
|---|---|
| `backend/agents/graph.py` | Fix `.select("id")` w edit_plan_exercise; prompt: dodano zdanie o rekapitulacji |
| `backend/agents/plan_generator.py` | Szybcior: model Haiku → Sonnet 4.6 |
| `backend/agents/extraction.py` | Uszatek: JSON fallback (raw_decode) zamiast crash |
| `backend/routers/quiz.py` | +5 nowych opcjonalnych pól w QuizRequest + upsert |
| `frontend/src/app/quiz/page.tsx` | Pełny rewrite — 3 kroki → 16/17, card buttons, mobile-first |
| `docs/ADR-n8n-automatyzacje.md` | Dopisano bugfix duplikatu filtra dat |

### Pliki usunięte

| Plik | Dlaczego |
|---|---|
| `docs/KOLEJNE-KROKI.md` | Zastąpiony przez CLAUDE.md + system memory |
| `docs/PROMPT-STARTOWY.md` | Nieaktualny, zastąpiony przez CLAUDE.md |

### Struktura branchów (dzisiaj)

```
main
├── merge: feature/prompt-refactor-cost-opt  (zaległe z tyg. 8)
│   ├── refactor agentów (Uszatek, Blacha → chain)
│   ├── Szybcior bez tool calls
│   └── Uszatek JSON fix
├── fix: edit_plan_exercise .select("id") + Szybcior Sonnet
├── merge: feature/quiz-expanded
│   ├── quiz 3 → 12 kroków (wersja 1)
│   ├── quiz 12 → 17 kroków, mobile splits
│   └── fix: cel_wagowy, walidacja kontuzji, usunięcie pory treningu
└── fix: prompt — nie rekapituluje poprzedniej wiadomości
```

---

## Decyzje Podjęte Przez Ciebie i Dlaczego

| Decyzja | Powód |
|---|---|
| Rozbudować quiz z 3 do 16/17 kroków | Model biznesowy się zmienił — quiz wypełnia się po płatności, więc user który zapłacił jest zmotywowany. Więcej danych od startu = lepsza pierwsza odpowiedź Pitbula |
| Szybcior: Haiku → Sonnet 4.6 | Plan generujesz rzadko (nie każda wiadomość), więc koszt pomijalny. Haiku robił słabe, ogólnikowe plany — nie o to chodzi w produkcie który ma być spersonalizowany |
| Nie dodawać semantic cache RAG | Główny koszt to call Sonnet (LLM), nie RAG. Embedding jest śmiesznie tani (~$0.00002). Cache LLM niemożliwy bo odpowiedzi są spersonalizowane — cache RAG oszczędziłby poniżej 1% całkowitego kosztu |
| Nie dać Pitbulowi twardej reguły "nigdy nie powtarzaj" | Zbyt restrykcyjne — blokowałoby naturalne dopowiedzenia i korekty. Zamiast reguły — zmiana założenia: "zakładaj że user przeczytał poprzednią wiadomość" |
| Usunąć pytanie o porę treningu | Zbędna informacja dla generowania planu — Extraction Agent może to zebrać w rozmowie jeśli będzie relevantne |
| Cel wagowy jako warunkowy krok (tylko masa/redukcja) | Dla siły i kondycji konkretna waga docelowa nie ma sensu. Conditional step czystszy UX niż opcjonalne pole które większość ignoruje |
| Cel wagowy do notatki_quiz zamiast nowej kolumny DB | Nie chcemy migracji bazy dla jednego pola tekstowego. Pitbul i Szybcior widzą notatki, więc informacja trafia do systemu |

---

## Błędy Które Popełniliśmy / Znaleźliśmy

**Błąd 1: edit_plan_exercise — cicha porażka zapisu**

Supabase-py v2 zmienił zachowanie `.update()` — bez `.select()` zwraca pustą listę zamiast zaktualizowanych wierszy. Kod sprawdzał `if not update_res.data` jako sygnał błędu, więc zawsze zwracał BŁĄD. Pitbul jednak ignorował komunikat błędu z narzędzia i mówił userowi że zmiana się udała. User musiał 3 razy prosić o to samo zanim zadziałało (za trzecim razem poprosił o wygenerowanie planu od nowa). Żadnych śladów w logach.

**Wniosek:** Przy upgrade bibliotek zawsze sprawdź breaking changes w metodach które zwracają dane. `.select()` po `.update()` to teraz wymóg w supabase-py v2.

**Błąd 2: Szybcior na Haiku — plan złej jakości**

Przejście na Haiku było decyzją kosztową z poprzedniego tygodnia. Okazało się że Haiku jest za słaby do wnioskowania wymaganego przy generowaniu planów — nie radził sobie z balansem grup mięśniowych, nie uwzględniał poprawnie sprzętu ani kontuzji. Wykryto dopiero po teście rozmowy.

**Wniosek:** Haiku nadaje się do ekstraktu/klasyfikacji (Uszatek, Blacha) — prostych, dobrze określonych zadań. Generowanie złożonego, spersonalizowanego dokumentu (plan treningowy) wymaga silniejszego modelu.

**Błąd 3: Walidacja kontuzji/ograniczeń w quizie**

User mógł zaznaczyć "Mam kontuzje" i przejść dalej bez opisania jakiej. Pitbul widział w profilu `kontuzje: [nie null]` ale bez treści — generował plan "uwzględniający kontuzje" nie wiedząc o co chodzi. Wykryto podczas przeglądu kodu.

**Wniosek:** Pola warunkowe (pojawiające się po "tak/nie") muszą mieć własną walidację gdy są widoczne.

**Błąd 4: Zaległe zmiany nigdy nie zmergowane na main**

Cała praca z poprzedniego tygodnia leżała na feature branchu. Projekt na Railway działał ze starego kodu. Odkryto na początku sesji po sprawdzeniu `git log`.

**Wniosek:** Merge na main = obowiązkowy etap kończący każdą sesję, nie opcjonalny.

---

## Cachowanie — Stan Wiedzy

Temat poruszony dzisiaj, ważny dla kolejnych sesji.

**Co już działa (prompt caching Anthropic):**
```python
SystemMessage(content=[
    {
        "type": "text",
        "text": PITBUL_STATIC_PROMPT,
        "cache_control": {"type": "ephemeral"},  # ← cachuje 5 min
    },
    ...
])
```
Statyczny prompt Pitbula (~600 tokenów) i statyczny prompt Szybciora są cachowane przez Anthropic. Każdy request w ciągu 5 minut od poprzedniego nie płaci za te tokeny. Działa.

**Czego NIE robimy i dlaczego:**
- **Semantic cache odpowiedzi LLM** — niemożliwy, odpowiedzi są spersonalizowane (profil, historia, plan)
- **Cache RAG queries** — oszczędność <1% kosztu, embedding to ~$0.00002, główny koszt to Sonnet

---

## Co Tu Się Zadziało — Prosto (bez żargonu)

### Naprawiliśmy trzy bugi

**Bug 1:** Pitbul mówił "zmiana zrobiona" gdy zmiana wcale nie była zrobiona. Działo się to przy edycji ćwiczeń w planie — Pitbul próbował zapisać zmianę do bazy, biblioteka zwracała pustą odpowiedź (co w tej wersji oznacza sukces), ale nasz kod interpretował to jako błąd. Pitbul widział błąd, ale zamiast powiedzieć userowi "coś poszło nie tak", odpowiadał "gotowe". Naprawiliśmy sprawdzanie czy zapis się udał.

**Bug 2:** Pitbul powtarzał całą poprzednią wiadomość na początku każdej odpowiedzi gdy pytanie było krótkie. Jak kumpel który co chwilę powtarza "no jak mówiłem..." — irytujące i kosztuje dodatkowy czas ładowania. Dodaliśmy jedno zdanie do instrukcji: zakładaj że user przeczytał co napisałeś, nie streszczaj tego ponownie.

**Bug 3:** W quizie można było zaznaczyć "mam kontuzję" i przejść dalej bez napisania jaką. Pitbul potem dostosowywał plan "do kontuzji" nie wiedząc do jakiej. Teraz jak zaznaczysz "tak" — musisz wpisać szczegóły, inaczej nie przejdziesz.

### Poprawiliśmy jakość planów treningowych

Poprzednio plany generował najtańszy i najsłabszy model AI (Haiku). Oszczędność kosztów była sensowna gdy każda wiadomość kosztuje — ale plan generujesz raz na jakiś czas. Przeszliśmy na mocniejszy model (Sonnet) do samego generowania planu. Koszt prawie bez zmian, jakość wyraźnie lepsza.

### Rozbudowaliśmy quiz

Quiz przed płatnością mógł być krótki — użytkownicy z TikToka mają krótką uwagę i musisz ich złapać szybko. Ale teraz quiz wypełnia się dopiero gdy ktoś już zapłacił. Taka osoba jest zaangażowana i warto zebrać od niej więcej informacji — bo więcej danych = lepszy plan i lepsza pierwsza rozmowa z Pitbulem.

Quiz urósł z 3 ekranów do 16-17 (zależnie od celu). Każdy ekran ma jedno pytanie. Na telefonie to jest wygodniejsze niż jeden długi formularz. Dodaliśmy pytania których wcześniej nie było: jak śpisz, jak wygląda Twój dzień, jak radzisz sobie ze stresem, co jesz. To wszystko wpływa na trening — teraz Pitbul wie to od razu, zamiast dopytywać przez kilka rozmów.

Dodaliśmy też pytanie o docelową wagę (ale tylko dla osób które chcą schudnąć lub przybrać). Dla kogoś kto trenuje na siłę — to pytanie nie ma sensu, więc go nie pokazujemy.

---

## Następne Kroki

- Stripe — płatności (Faza 2 MVP)
- Strona ustawień — zmiana danych konta, usunięcie konta
- Dłuższy test Pitbula z nowym promptem i Szybciorem na Sonnet
- Rozważyć Agent Progresji (śledzenie realizacji planu) — Faza 3-4
