# Quiz — pytania, profil użytkownika, strategia zbierania danych

> 14 pytań w quizie + dane zbierane organicznie przez Extraction Agent w rozmowach.
>
> Data: 2026-04-14

---

## 1. Filozofia: quiz vs rozmowa

W quizie pytamy TYLKO o rzeczy bez których agent nie może zacząć rozmowy. Resztę agent wyciąga w naturalnej rozmowie dzięki Extraction Agent.

**Dlaczego nie 22 pytania:**
- 22 pytania na mobile = 5-7 minut = wysoki dropout
- Początkujący chcą szybko zacząć, nie wypełniać ankietę
- Dane o śnie, diecie, stresie lepiej zbierać w kontekście rozmowy (naturalniej)

**Dlaczego nie 5 pytań:**
- Agent MUSI znać parametry ciała, cel, doświadczenie, kontuzje i sprzęt od startu
- Bez tych danych pierwsza rozmowa jest generyczna i bezwartościowa

**14 pytań = ~2 minuty na mobile. Kompromis między szybkością a pełnością profilu.**

---

## 2. Pytania w quizie

### Grupa 1: O Tobie (4 pytania)

| # | Pytanie | Typ odpowiedzi | Pole w profilu | Walidacja |
|---|---|---|---|---|
| 1 | Ile masz lat? | Number input | wiek | 12-100 |
| 2 | Płeć | Select: Mężczyzna / Kobieta | plec | Wymagane |
| 3 | Wzrost (cm) | Number input | wzrost | 100-250 |
| 4 | Waga (kg) | Number input | waga | 30-300 |

### Grupa 2: Twój trening (6 pytań)

| # | Pytanie | Typ odpowiedzi | Pole w profilu | Walidacja |
|---|---|---|---|---|
| 5 | Jakie masz doświadczenie z siłownią? | Select: Nigdy nie trenowałem / Mniej niż 3 miesiące / 3-12 miesięcy / 1-3 lata / Ponad 3 lata | poziom | Wymagane |
| 6 | Jaki jest Twój główny cel? | Select: Masa mięśniowa / Redukcja tkanki tłuszczowej / Siła / Ogólna kondycja | cel | Wymagane |
| 7 | Ile dni w tygodniu możesz trenować? | Select: 2 / 3 / 4 / 5 / 6 | dni_treningowe | Wymagane |
| 8 | Ile czasu możesz poświęcić na jeden trening? | Select: 30-45 min / 45-60 min / 60-90 min / Ponad 90 min | czas_treningu | Wymagane |
| 9 | Gdzie trenujesz? | Select: Siłownia komercyjna / Siłownia domowa / Mieszanko | miejsce_treningu | Wymagane |
| 10 | Jaki sprzęt masz dostępny? | Multi-select: Sztanga + obciążenia / Hantle / Maszyny / Wyciąg bramkowy / Drążek do podciągania / Ławka | dostepny_sprzet | Min 1 zaznaczony |

**Uwaga do pytania 7:** Zaczyna się od 2, nie od 1. Trening raz w tygodniu to za mało na sensowny plan. Jeśli ktoś może tylko 1 dzień — agent omówi to w rozmowie i zaproponuje dodatkową aktywność w domu.

**Uwaga do pytania 10:** Jeśli user wybrał "Siłownia komercyjna" w pytaniu 9, można pre-zaznaczyć wszystkie opcje (siłownie komercyjne mają wszystko) i pozwolić userowi odznaczyć jeśli czegoś brakuje. Oszczędza klikanie na mobile.

### Grupa 3: Zdrowie (3 pytania)

| # | Pytanie | Typ odpowiedzi | Pole w profilu | Walidacja |
|---|---|---|---|---|
| 11 | Czy masz aktualnie jakieś kontuzje lub bóle? | Select: Nie / Tak | (warunkowe — pokazuje #12) | Wymagane |
| 12 | Jeśli tak — opisz krótko co i gdzie | Textarea (widoczne tylko jeśli #11 = Tak) | kontuzje | Max 500 znaków |
| 13 | Czy masz ograniczenia które powinniśmy uwzględnić? (np. nie mogę podnosić rąk powyżej głowy, praca zmianowa, brak czasu rano) | Select: Nie / Tak → Textarea | ograniczenia | Max 500 znaków |

Kontuzje i ograniczenia to jedyne pytania zdrowotne w quizie. Leki, przeszłe kontuzje, choroby — agent dopyta w rozmowie gdy będzie relevantne. Mniej pytań = mniejsze wrażenie "ankiety medycznej" (co może odstraszać).

### Grupa 4: Ostatnie pytanie (1 pytanie)

| # | Pytanie | Typ odpowiedzi | Pole w profilu | Walidacja |
|---|---|---|---|---|
| 14 | Coś jeszcze co powinienem o Tobie wiedzieć? | Textarea (opcjonalne) | notatki_quiz | Max 500 znaków |

Łapie wszystko czego nie przewidzieliśmy. User może napisać "jestem weganinem", "pracuję na nocki", "mam 2-miesięczne dziecko i mało sypiam" — agent to przeczyta i uwzględni.

---

## 3. Mapowanie odpowiedzi na profil

### Pytanie 5: doświadczenie → poziom

| Odpowiedź usera | Wartość w profilu |
|---|---|
| Nigdy nie trenowałem | poczatkujacy |
| Mniej niż 3 miesiące | poczatkujacy |
| 3-12 miesięcy | srednio |
| 1-3 lata | srednio |
| Ponad 3 lata | zaawansowany |

### Pytanie 10: sprzęt → tablica

Zapisywane jako tablica tekstów (TEXT[] w PostgreSQL). Przykład: `['sztanga', 'hantle', 'maszyny']`.

---

## 4. Dane zbierane z rozmów (przez Extraction Agent)

Te pola NIE są w quizie. Startują jako NULL i zapełniają się organicznie z rozmów.

| Pole | Typ | Kiedy Extraction zapisuje | Przykład |
|---|---|---|---|
| jakosc_snu | TEXT | User wspomni o śnie | "śpi 6h, średnio" |
| poziom_stresu | TEXT | User wspomni o stresie | "wysoki, praca" |
| dieta | TEXT | User wspomni o jedzeniu | "nie pilnuje, je co popadnie" |
| aktywnosc_codzienna | TEXT | User opisze swój dzień | "siedząca, biurko 8h" |
| kontuzje_przeszle | TEXT | User wspomni o przeszłych urazach | "ACL kolano prawe, 2023" |
| leki | TEXT | User wspomni o lekach | "beta-blokery" |
| osiagniecia | TEXT | User powie o rekordzie | "ławka 80kg, przysiad 100kg" |
| notatki | TEXT | Inne ważne informacje | "preferuje trening rano" |

### Jak agent dopytuje o brakujące dane

PROMPT-01 dostaje informację o polach które są NULL w profilu. Instrukcja:

> "Jeśli widzisz puste pola w profilu — przy naturalnej okazji dopytaj o nie. Nie pytaj o więcej niż jedną brakującą rzecz na rozmowę. Nie pytaj na siłę — jeśli temat rozmowy nie pasuje, poczekaj na lepszy moment."

Przykładowy flow:

**Rozmowa 1 (po quizie):**
- Agent wita się, nawiązuje do profilu
- Przy okazji pyta: "A jak u Ciebie ze snem? Bo to ważne dla regeneracji"
- Extraction zapisuje: jakosc_snu = "7h, dobrze"

**Rozmowa 2:**
- User pyta o jedzenie po treningu
- Agent odpowiada, przy okazji pyta: "A ogólnie — pilnujesz diety czy jesz co popadnie?"
- Extraction zapisuje: dieta = "stara się jeść zdrowo"

**Rozmowa 3:**
- Temat nie pasuje do żadnego brakującego pola → agent nie dopytuje

Po 3-5 rozmowach profil jest pełny — naturalnie, bez ankiety. To jest pokaz siły Extraction Agent w portfolio.

---

## 5. Pełny schemat user_profiles

### Pola z quizu (wypełniane przy rejestracji)

| Pole | Typ | Źródło | Walidacja |
|---|---|---|---|
| id | UUID (PK) | Auto | — |
| user_id | UUID (FK → users) | Auth | UNIQUE, NOT NULL |
| wiek | INTEGER | Quiz #1 | CHECK 12-100 |
| plec | TEXT | Quiz #2 | CHECK IN ('mezczyzna', 'kobieta') |
| wzrost | INTEGER | Quiz #3 | CHECK 100-250 |
| waga | REAL | Quiz #4 | CHECK 30-300 |
| poziom | TEXT | Quiz #5 | CHECK IN ('poczatkujacy', 'srednio', 'zaawansowany') |
| cel | TEXT | Quiz #6 | CHECK IN ('masa', 'redukcja', 'sila', 'kondycja') |
| dni_treningowe | INTEGER | Quiz #7 | CHECK 2-6 |
| czas_treningu | TEXT | Quiz #8 | CHECK IN ('30-45', '45-60', '60-90', '90+') |
| miejsce_treningu | TEXT | Quiz #9 | CHECK IN ('silownia', 'dom', 'mieszanko') |
| dostepny_sprzet | TEXT[] | Quiz #10 | Array, min 1 element |
| kontuzje | TEXT | Quiz #12 | Nullable |
| ograniczenia | TEXT | Quiz #13 | Nullable |
| notatki_quiz | TEXT | Quiz #14 | Nullable |

### Pola z rozmów (wypełniane przez Extraction Agent)

| Pole | Typ | Źródło | Domyślnie |
|---|---|---|---|
| jakosc_snu | TEXT | Extraction | NULL |
| poziom_stresu | TEXT | Extraction | NULL |
| dieta | TEXT | Extraction | NULL |
| aktywnosc_codzienna | TEXT | Extraction | NULL |
| kontuzje_przeszle | TEXT | Extraction | NULL |
| leki | TEXT | Extraction | NULL |
| osiagniecia | TEXT | Extraction | NULL |
| notatki | TEXT | Extraction | NULL |

### Pola systemowe

| Pole | Typ | Opis |
|---|---|---|
| quiz_completed | BOOLEAN | DEFAULT false, true po wysłaniu quizu |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | Trigger on update |

---

## 6. UX quizu (podsumowanie)

- Jedno pytanie na ekranie (mobile-first)
- Progress bar na górze (np. "5 / 14")
- Przyciski "Dalej" / "Wstecz"
- Walidacja inline (podświetlenie błędu od razu, nie po submicie)
- Pytania warunkowe (#12 widoczne tylko jeśli #11 = Tak)
- Na końcu: ekran podsumowania "Sprawdź swoje dane" → przycisk "Zaczynamy"
- Po submicie: automatyczne przekierowanie do czatu (agent się wita)

Szacowany czas wypełnienia: ~2 minuty.

Szczegóły UX: patrz [ux-and-flows.md](ux-and-flows.md).
