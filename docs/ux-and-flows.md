# UX i flow użytkownika — onboarding, mobile, sesje rozmów

> Jak użytkownik przechodzi przez system, co widzi na każdym etapie, jak działa czat na telefonie.
>
> Data: 2026-04-14

---

## 1. Pełny flow użytkownika

```
Nowy użytkownik wchodzi na stronę
        │
        ▼
   Landing page (post-MVP)
   "AI trener personalny — spersonalizowany plan treningowy"
        │
        ▼
   ┌─────────────┐
   │  REJESTRACJA │
   │  Email+hasło │
   │  □ Zgoda RODO│
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │    QUIZ     │
   │  22 pytania │
   │  ~3-5 min   │
   └──────┬──────┘
          │
          ▼
   ┌──────────────────┐
   │  PIERWSZA        │
   │  ROZMOWA Z       │
   │  AGENTEM          │
   │  (agent się      │
   │  przedstawia)    │
   └──────┬───────────┘
          │
          ▼
   ┌─────────────┐
   │   CZAT      │
   │  (ongoing)  │
   └─────────────┘
```

---

## 2. Onboarding — pierwsza rozmowa

### Problem

Co się dzieje po quizie? User kliknął "Wyślij quiz" i... co teraz? Puste okno czatu? Wiadomość "Napisz coś"? To słaby UX — user nie wie co robić.

### Rozwiązanie: agent zaczyna pierwszy

Po wypełnieniu quizu agent automatycznie wysyła pierwszą wiadomość. User NIE musi pisać pierwszy.

**Logika:**

Gdy user pierwszy raz otwiera czat (quiz_completed = true, brak sesji):
1. System tworzy nową sesję
2. Agent wysyła wiadomość powitalną opartą na profilu z quizu

**Ton pierwszej wiadomości:**

Agent nawiązuje do konkretnych danych z quizu — user widzi że agent "go zna" od pierwszego kontaktu. To buduje zaufanie.

Przykładowy kierunek (nie dosłowna treść — agent generuje sam na podstawie profilu):
- Zwraca się do usera po danych z quizu
- Nawiązuje do celu (masa/redukcja/siła)
- Komentuje liczbę dni treningowych
- Jeśli user zaznaczył kontuzje — wspomina o nich
- Proponuje co dalej (np. "mogę Ci ułożyć plan" lub "zadaj mi pytanie")
- NIE zadaje pytań które już zna z quizu (to irytujące)

### Implementacja

Pierwsza wiadomość to normalny call do Orchestratora (PROMPT-01), ale z syntetyczną wiadomością usera typu "Cześć, właśnie wypełniłem quiz" (user jej nie widzi — to trigger wewnętrzny). Agent odpowiada naturalnie na podstawie profilu.

Alternatywnie: osobny mini-prompt do wygenerowania powitania, ale to dodatkowa złożoność. Lepiej użyć istniejącego PROMPT-01.

### Co agent NIE powinien robić przy pierwszym kontakcie

- Nie zasypywać usera informacjami (plan, porady, 5 pytań naraz)
- Nie pytać o rzeczy z quizu ("Ile masz lat?" — wie to z profilu)
- Nie pisać ściany tekstu — krótko, konkretnie, z jedną propozycją następnego kroku
- Nie generować od razu planu treningowego — najpierw relacja, potem plan

---

## 3. Zarządzanie sesją z perspektywy UX

### Co widzi user

User widzi JEDEN ciągły czat. Nie widzi podziału na sesje — to logika backendowa (patrz [database.md](database.md)).

Czat wygląda jak:
```
[wiadomości z bieżącej sesji — pełna historia]
```

User NIE widzi wiadomości ze starych sesji w UI. Ale agent "pamięta" je dzięki podsumowaniu (conversation_summaries).

### Dlaczego user nie widzi starych wiadomości

- Prostota UI (MVP)
- Unikanie wrażenia "agent zapomniał" — jeśli user przewinie do starej wiadomości i zada pytanie nawiązujące, agent może nie mieć jej w kontekście (bo ładuje tylko bieżącą sesję + podsumowanie). Lepiej nie pokazywać starej historii niż pokazać i nie pamiętać

### Post-MVP: historia rozmów

Jeśli chcesz dodać dostęp do starych rozmów:
- Osobna zakładka "Historia" z listą sesji (data + krótkie podsumowanie)
- Kliknięcie na sesję → read-only widok starych wiadomości
- Jasne oznaczenie "To jest archiwalna rozmowa. Aktualna rozmowa jest w Czacie."

---

## 4. Mobile — kluczowe decyzje UX

### Dlaczego mobile jest ważny

Grupa docelowa (początkujący na siłowni) będzie korzystać z telefonu:
- Między seriami na siłowni ("co teraz zrobić zamiast tego ćwiczenia?")
- W drodze na siłownię ("pokaż mi dzisiejszy trening")
- Wieczorem w domu ("boli mnie bark po treningu, co robić?")

Desktop to drugorzędny kanał. Mobile-first to nie opcja, to wymóg.

### Wymagania mobile-first

**Okno czatu:**

- Input na dole ekranu (kciuk dosięga)
- Klawiatura nie zasłania ostatniej wiadomości (auto-scroll)
- Przycisk "Wyślij" wystarczająco duży do tapnięcia
- Brak sidebara — pełna szerokość na rozmowę
- "Agent pisze..." widoczne bez scrollowania

**Quiz na mobile:**

- Jedno pytanie na ekranie (nie cały formularz na raz)
- Duże przyciski do wyboru odpowiedzi (radio/select)
- Progress bar (pytanie 5/22)
- Walidacja inline (nie po submicie całego formularza)

**Ogólne:**

- Tailwind CSS z responsive breakpoints (domyślne są dobre)
- Testuj na iPhone SE (mały ekran) i na Androidzie
- Brak hover-only interakcji (na mobile nie ma hover)
- Font minimum 16px na mobile (zapobiega auto-zoomowi w iOS)

### Typowe pułapki mobile na czacie

**Problem: klawiatura zasłania input**

Na iOS i starszych Androidach otwarcie klawiatury przesuwa viewport. Input może zniknąć pod klawiaturą.

Rozwiązanie: CSS `position: fixed` + `bottom: 0` na kontenerze inputa. Lub nowsza metoda: CSS `dvh` (dynamic viewport height) zamiast `vh`.

**Problem: auto-scroll nie działa przy streamingu**

Agent odpowiada streamingowo — tekst pojawia się token po tokenie. Jeśli user jest na dole — powinien widzieć nowe tokeny. Jeśli przewinął do góry — NIE scrolluj automatycznie (to irytujące).

Zasada: auto-scroll TYLKO jeśli user jest na dole czatu (w granicach ~50px od dna).

**Problem: długa odpowiedź agenta na małym ekranie**

Agent czasem pisze 200+ słów. Na małym ekranie to 10+ ekranów tekstu.

Nie ma prostego rozwiązania — ale PROMPT-01 sekcja "FORMAT ODPOWIEDZI" mówi: "Krótkie odpowiedzi na krótkie pytania." To pomaga.

---

## 5. Stany UI i komunikaty błędów

### Stany czatu

| Stan | Co widzi user | Kiedy |
|---|---|---|
| Ładowanie | Spinner lub skeleton | Otwieranie czatu, ładowanie historii |
| Gotowy | Input aktywny, historia widoczna | Po załadowaniu |
| Agent pisze | Animacja "..." pod ostatnią wiadomością, input zablokowany | Podczas streaming response |
| Błąd API | "Coś poszło nie tak. Spróbuj wysłać wiadomość ponownie." | Timeout lub błąd Anthropic |
| Rate limit | "Wysłałeś za dużo wiadomości. Poczekaj chwilę." (per minute) lub "Dzienny limit wyczerpany. Wróć jutro." (per day) | HTTP 429 |
| Brak subskrypcji | "Twoja subskrypcja wygasła. Odnów aby kontynuować." | Post-MVP, po Stripe |
| Serwer niedostępny | "Serwer jest chwilowo niedostępny. Spróbuj za minutę." | Backend timeout (10s) |
| Brak internetu | "Brak połączenia z internetem." | navigator.onLine = false |

### Zasady komunikatów błędów

- Język ludzki, nie techniczny ("Coś poszło nie tak" zamiast "HTTP 500")
- Zawsze powiedz co user może zrobić ("spróbuj ponownie", "wróć jutro")
- Nie pokazuj stack trace'ów, JSON-ów, ani kodów błędów
- Rate limit: powiedz KIEDY user może ponowić (za minutę / jutro)
- Nigdy nie obwiniaj usera ("Twoja wiadomość za długa" → "Wiadomość może mieć max 2000 znaków")

---

## 6. Flow quizu — szczegóły

### Struktura 22 pytań

Pytania pogrupowane tematycznie (user widzi grupy, nie numery):

**Grupa 1: O Tobie (pytania 1-5)**
- Wiek, płeć, wzrost, waga, poziom aktywności

**Grupa 2: Twój trening (pytania 6-12)**
- Doświadczenie (ile trenujesz), obecny plan (jeśli masz), cel, ile dni w tygodniu, ile czasu na trening, preferowane ćwiczenia, dostępny sprzęt

**Grupa 3: Zdrowie i ograniczenia (pytania 13-18)**
- Kontuzje (obecne i przeszłe), dolegliwości, ograniczenia ruchowe, leki wpływające na trening

**Grupa 4: Styl życia (pytania 19-22)**
- Jakość snu, poziom stresu, dieta (ogólnie), praca (siedząca/fizyczna)

### UX quizu

- Jedno pytanie na ekranie (mobile-first)
- Przyciski "Dalej" / "Wstecz" (user może wrócić i zmienić)
- Progress bar na górze
- Pytania zamknięte (select/radio) gdzie to możliwe, wolny tekst tylko dla kontuzji i ograniczeń
- Walidacja inline (podświetl jeśli puste, pokaż min/max dla liczb)
- Na końcu: ekran podsumowania "Sprawdź swoje dane" przed submitem
- Po submicie: automatyczne przekierowanie do czatu (agent się wita)

### Co jeśli user nie skończył quizu

Jeśli user zamknie stronę w połowie quizu:

MVP: musi zacząć od nowa (quiz nie jest zapisywany w trakcie).

Post-MVP: zapis odpowiedzi do localStorage lub do Supabase po każdej grupie pytań. Po powrocie: kontynuacja od miejsca przerwania.

---

## 7. Nawigacja (MVP)

### Struktura stron

```
/login          → logowanie (Supabase Auth UI)
/register       → rejestracja + checkbox RODO
/quiz           → quiz 22 pytania (jeśli quiz_completed = false)
/chat           → czat z agentem (jeśli quiz_completed = true)
```

### Routing logic

```
Niezalogowany → /login
Zalogowany + quiz_completed = false → /quiz
Zalogowany + quiz_completed = true → /chat
```

User nie ma menu nawigacyjnego (MVP). Po zalogowaniu automatycznie trafia we właściwe miejsce.

### Post-MVP: dodatkowe strony

```
/plan           → zakładka z planem treningowym (faza 1)
/settings       → ustawienia konta, usunięcie konta (faza 2)
/billing        → zarządzanie subskrypcją Stripe (faza 2)
```
