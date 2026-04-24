# ADR — Tydzień 7: Strona ustawień + rozbudowa bazy RAG

> Dokument decyzji architektonicznych dla Tygodnia 7 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie decyzje podjęto, jakie błędy popełniono i czego się nauczyliśmy.
>
> Data: 2026-04-22 | Autor: Konrad + Claude | Status: Ukończony

---

## Spis treści

1. [Przegląd tygodnia](#1-przegląd-tygodnia)
2. [Co zbudowaliśmy](#2-co-zbudowaliśmy)
3. [Zmiany w plikach](#3-zmiany-w-plikach)
4. [Decyzje które Konrad podjął](#4-decyzje-które-konrad-podjął)
5. [Błędy które popełniliśmy](#5-błędy-które-popełniliśmy)
6. [Co odkryliśmy po drodze](#6-co-odkryliśmy-po-drodze)
7. [Stan na koniec tygodnia](#7-stan-na-koniec-tygodnia)
8. [Proste wyjaśnienie — bez żargonu](#8-proste-wyjaśnienie--bez-żargonu)

---

## 1. Przegląd tygodnia

### Cel

Dwa niezależne zadania: dać użytkownikowi możliwość zmiany swoich danych bez rozmowy z agentem, oraz znacząco poszerzyć bazę wiedzy z której korzystają agenci.

### Efekt

- Strona ustawień: user może samodzielnie zmienić wagę, cel treningowy, email, hasło i usunąć konto
- Baza RAG: z 19 chunków jednego ebooka do 1364 chunków z 7 anglojęzycznych źródeł naukowych — przetłumaczonych na polski

### Liczby

| Metryka | Przed | Po |
|---|---|---|
| Chunki w bazie RAG | 19 | 1364 |
| Źródła wiedzy | 1 (ebook Konrada) | 8 (ebook + 7 publikacji) |
| Język źródeł | Polski | Polski + angielski (tłumaczony) |
| Endpointy ustawień | 0 | 5 |

---

## 2. Co zbudowaliśmy

### Strona ustawień

**Problem:** Jedynym sposobem na zmianę wagi czy celu treningowego było powiedzenie Pitbulowi w rozmowie — a wtedy Uszatek musiał to wychwycić, zaktualizować profil przez narzędzie, czasem wchodziło w conflict resolution. Niepotrzebnie kosztowne (tokeny) i zawodne.

**Rozwiązanie:** Nowy router `/settings` z 5 endpointami i nowa strona w aplikacji. User wchodzi w zakładkę "Ustawienia", zmienia dane w formularzu, klika "Zapisz" — zmiana ląduje bezpośrednio w bazie, zero AI po drodze.

**Zakresy:**
- Profil treningowy: waga (30-300 kg) i cel (masa / redukcja / siła / kondycja)
- Email: zmiana przez Supabase Admin API
- Hasło: zmiana przez Supabase Admin API (minimum 8 znaków)
- Usunięcie konta: dwuetapowe potwierdzenie — wpisz `USUŃ`, potem drugi przycisk

**Dlaczego dwuetapowe potwierdzenie przy usuwaniu:** Usunięcie konta jest nieodwracalne. Jeden przypadkowy klik nie powinien go wywołać. Wzorzec "wpisz słowo potwierdzające" jest standardem (GitHub, Supabase, Heroku robią to samo).

**Nawigacja:** Zakładka "Ustawienia" dodana do nawa w Chat i Plan. W checie — zablokowana podczas ładowania i wpisywania (tak samo jak zakładka Plan), żeby user nie uciekał w połowie rozmowy.

---

### Pipeline agentic chunking — `ingest_multi.py`

**Problem:** Dotychczasowa baza RAG miała 19 chunków z jednego ebooka (~10 000 słów po polsku). To za mało żeby agent odpowiadał pewnie na szeroki zakres pytań o trening, żywienie i regenerację. Nowe materiały były po angielsku i miały do 1723 KB — za duże żeby wrzucić w jedno wywołanie GPT.

**Rozwiązanie:** Nowy skrypt `scripts/ingest_multi.py` z dwuetapowym pipeline'm:

```
Krok 1 — Mechaniczne cięcie (zero API)
  Plik txt → linia po linii → akumuluj do ~3000 tokenów
  → tnij na granicy pustej linii (koniec akapitu)
  → kawałki po ~2000 słów

Krok 2 — GPT-4o-mini (per kawałek)
  Kawałek → GPT-4o-mini:
    - semantyczne podzielenie na chunki (150-500 tokenów)
    - tłumaczenie na polski
    - tytuł sekcji po polsku
    - topic: trening / zywienie / regeneracja / ogolne
    - 3-5 słów kluczowych po polsku

Krok 3 — Embedding
  Każdy przetłumaczony chunk → text-embedding-3-small → wektor 1536 dim

Krok 4 — Supabase
  chunk + wektor + metadane → INSERT do knowledge_embeddings
```

**Mechaniczne cięcie na granicy akapitu:** Nie tniemy w środku zdania — czekamy na pustą linię. Dzięki temu GPT-mini dostaje spójny tekst, nie urwane zdanie na początku kawałka.

**Dlaczego GPT-4o-mini a nie inny model:** Do tego zadania wystarczy. Tłumaczenie i podział semantyczny to zadania, gdzie nie potrzebujesz Sonnet. GPT-4o-mini jest 50x tańszy od Sonnet i radzi sobie z tym dobrze. Cały pipeline 7 plików kosztował poniżej $0.50.

**Checkpointing:** Po przetworzeniu każdego kawałka skrypt zapisuje postęp do `sources/_progress.json`. Jeśli coś się wysypie — wznawiamy od miejsca gdzie skończyło, nie od początku. Przy 80-120 wywołaniach API to ważne.

**Retry logic:** 3 próby z backoffem (2s, 5s) przy błędach API. GPT-mini czasem timeout'uje przy dużym obciążeniu — bez retry trzeba by ręcznie uruchamiać od nowa.

**Czyszczenie przed re-ingestionem:** Przed wgraniem nowego pliku skrypt usuwa z bazy wszystkie rekordy z tym samym `source`. Zapobiega duplikatom przy ponownym uruchomieniu na tym samym pliku.

**Test przed pełnym uruchomieniem:** Skrypt pyta o potwierdzenie po pierwszym pliku — możesz sprawdzić jakość chunków w Supabase zanim puścisz pozostałe 6 plików.

**Źródła wgrane:**

| Plik | Rozmiar | Kawałki | Chunki |
|---|---|---|---|
| ACSM Complete Guide to Fitness & Health | 1079 KB | 86 | ~402 |
| 5.pdf (fizjologia ćwiczeń) | 1722 KB | 139 | ~695 |
| ACSM Progression Models in Resistance Training | 137 KB | ~20 | ~100 |
| Fundamentals of Resistance Training | 92 KB | ~15 | ~75 |
| ACSM Nutrition & Athletic Performance | 165 KB | ~25 | ~120 |
| The Physiology of Exercise | 488 KB | ~50 | ~250 |
| The Complete Guide to Sports Nutrition | 99 KB | ~15 | ~75 |

---

## 3. Zmiany w plikach

| Plik | Co się zmieniło |
|---|---|
| `backend/routers/settings.py` | Nowy plik — 5 endpointów: GET/PATCH profile, PATCH email, PATCH password, DELETE account |
| `backend/main.py` | Import i rejestracja routera settings |
| `frontend/src/app/settings/page.tsx` | Nowa strona ustawień |
| `frontend/src/app/chat/page.tsx` | Zakładka "Ustawienia" w nawigacji |
| `frontend/src/app/plan/page.tsx` | Zakładka "Ustawienia" w nawigacji |
| `scripts/ingest_multi.py` | Nowy skrypt — pipeline multi-plik z checkpointingiem |

---

## 4. Decyzje które Konrad podjął

### "Ustawienia jako formularz, nie przez Pitbula"

Konrad mógł powiedzieć "zmiana wagi przez Pitbula już działa — Uszatek to ogarnia". Zdecydował że to złe UX i złe pieniądze — po co angażować AI do czegoś co jest zwykłą podmianą wartości w bazie. Formularz jest szybszy, tańszy i przewidywalny.

### "Angielskie źródła zamiast szukać polskich"

Najlepsze publikacje o treningu siłowym są po angielsku (ACSM, NSCA, recenzowane pozycje). Polskich odpowiedników tej jakości praktycznie nie ma. Konrad zdecydował żeby wziąć angielskie i przetłumaczyć przez GPT — zamiast szukać gorszych polskich substytutów.

### "top_k=3 zostawiamy na razie, może później top_k=5"

Retrieval zwraca 3 najbliższe chunki. Przy 1364 chunkach można by podnieść do 5 żeby agent miał szerszą perspektywę. Konrad zdecydował żeby teraz nie ruszać — zmiana jest prosta (jedna liczba w `rag.py`) i można ją zrobić w każdej chwili po obserwacji jak agenci się zachowują z nową bazą.

---

## 5. Błędy które popełniliśmy

### Błąd 1: UnicodeEncodeError przy emoji w terminalu Windows

**Co się stało:** Skrypt `ingest_multi.py` miał w jednej linii znak `⚠` (emoji ostrzeżenia). Windows terminal (cp1250) nie obsługuje tego znaku — skrypt wysypał się przy starcie z `UnicodeEncodeError`.

**Fix:** Usunięcie emoji — zastąpienie zwykłym tekstem.

**Nauka:** Na Windows — żadnych emoji w stringach które idą do `print()`. Albo jawnie ustawić `sys.stdout` na UTF-8 na początku skryptu.

### Błąd 2: `&&` nie działa w PowerShell

**Co się stało:** Podałem komendę `cd ... && python ...` — standardowa składnia bash. Na PowerShell 5.1 (Windows) operator `&&` nie istnieje — syntax error.

**Fix:** Separator `;` zamiast `&&` w PowerShell.

**Nauka:** Na Windows sprawdzaj czy user jest w bash (Git Bash) czy PowerShell — składnia łączenia komend jest inna.

---

## 6. Co odkryliśmy po drodze

### Agentic chunking jest tani

Przetłumaczenie i semantyczne podzielenie 7 plików (łącznie ~3.7 MB tekstu) przez GPT-4o-mini kosztowało poniżej $0.50. Dla porównania — jedna dłuższa rozmowa z Pitbulem na Sonnet kosztuje więcej. To ważna obserwacja: preprocessing danych jest tani, inference w produkcji jest drogi.

### Rozmiar bazy RAG nie spowalnia retrieval

pgvector robi similarity search przez indeks HNSW — czas zapytania jest praktycznie niezależny od liczby rekordów. 19 chunków czy 1364 chunki — retrieval zajmuje tyle samo czasu. Nie ma powodów żeby trzymać małą bazę "dla wydajności".

### PDF→txt zostawia artefakty

Konwertowane pliki PDF miały w txt dużo artefaktów: wyrazy pod sobą (nagłówki, podpisy tabel), numery stron, losowe pojedyncze linie. GPT-4o-mini ignoruje je przy tworzeniu chunków — rozumie kontekst mimo śmieciowego formatowania. Nie trzeba czyścić txt ręcznie przed ingestionem.

### Metadane są w bazie, ale agenci ich nie widzą

Każdy chunk ma pole `source`, `topic`, `keywords`. Są w Supabase. Ale retrieval zwraca agentom tylko `content` i `section_title` — bez informacji o źródle. Pitbul nie powie "to z książki ACSM". Świadoma decyzja — Konrad uznał że na tym etapie wystarczy bogatsza baza, nie potrzeba atrybucji źródeł.

---

## 7. Stan na koniec tygodnia

### Co działa

- Strona ustawień: zmiana wagi, celu, emaila, hasła, usunięcie konta
- Nawigacja: zakładka "Ustawienia" w checie i planie
- Baza RAG: 1364 chunki z 8 źródeł (1 polski ebook + 7 angielskich publikacji naukowych)
- Pipeline ingestion: `ingest_multi.py` z checkpointingiem i retry
- Pitbul i Szybcior automatycznie korzystają z nowej bazy — zero zmian w kodzie agentów

### Znane ograniczenia

- `top_k=3` — retrieval zwraca tylko 3 chunki. Można podnieść do 5 gdy będzie feedback że agenci odpowiadają zbyt wąsko
- Source nazwy w bazie są brzydkie (pełne nazwy plików) — można zmienić SQL-em w dowolnym momencie
- Metadane `topic` i `keywords` są w bazie ale nieużywane — potencjał na filtrowanie retrieval w przyszłości

### Następne kroki

1. Przetestować Pitbula i Szybciora z nową bazą — sprawdzić czy odpowiedzi są konkretniejsze
2. Opcjonalnie: podnieść `top_k` z 3 do 5
3. Stripe — gdy będzie gotowość do sprzedaży
4. Landing page — żeby osoba która dostanie link wiedziała co ogląda

---

## 8. Proste wyjaśnienie — bez żargonu

### Co zbudowaliśmy i po co

**Strona ustawień**

Do tej pory jeśli chciałeś zmienić wagę albo swój cel treningowy, musiałeś napisać to Pitbulowi w rozmowie. Pitbul przekazywał to innemu agentowi który analizował wiadomość i zapisywał zmianę do bazy — cały ten proces kosztował czas i pieniądze. Teraz jest zakładka "Ustawienia" gdzie wpisujesz nową wagę, klikasz "Zapisz" i gotowe — żaden agent nie jest potrzebny, dane zmieniają się natychmiast.

Przy okazji dodaliśmy możliwość zmiany emaila, hasła i usunięcia konta — rzeczy których wcześniej w ogóle nie było w aplikacji.

**Rozbudowa bazy wiedzy**

Wyobraź sobie że Pitbul to mądry asystent, ale może odpowiadać tylko na podstawie książek które przeczytał. Do tej pory miał jedną książkę — ebook który sam napisałeś (~90 stron). Teraz daliśmy mu 7 kolejnych — grube, naukowe pozycje o treningu siłowym, żywieniu sportowym i fizjologii ćwiczeń, łącznie kilka tysięcy stron.

Problem: te książki były po angielsku. Pitbul rozmawia po polsku. Napisaliśmy program który każdą z tych książek pocina na małe kawałki, tłumaczy każdy kawałek na polski i wrzuca do bazy wiedzy. To wszystko zrobiło się automatycznie — bez ręcznego tłumaczenia ani przepisywania.

Efekt: zamiast 19 kawałków wiedzy Pitbul i Szybcior mają teraz do dyspozycji 1364 kawałki. Gdy user pyta o coś konkretnego — agenci znajdą odpowiedź w znacznie bogatszym zasobie i powinni odpowiadać dokładniej i pewniej.

**Ile to kosztowało:** Całe tłumaczenie i przetworzenie siedmiu plików — mniej niż 2 złote. Jedna dłuższa rozmowa z Pitbulem kosztuje więcej.
