# ADR — Tydzień 5: Multi-Agent Refaktor

> Dokument decyzji architektonicznych dla Tygodnia 5 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie decyzje podjęto, jakie błędy popełniono i czego się nauczyliśmy.
>
> Data: 2026-04-20 | Autor: Konrad + Claude | Status: Ukończony

---

## Spis treści

1. [Przegląd tygodnia](#1-przegląd-tygodnia)
2. [Co zbudowaliśmy](#2-co-zbudowaliśmy)
3. [Narzędzia agentów](#3-narzędzia-agentów)
4. [Zmiany w plikach](#4-zmiany-w-plikach)
5. [Decyzje które Konrad podjął](#5-decyzje-które-konrad-podjął)
6. [Błędy które popełniliśmy](#6-błędy-które-popełniliśmy)
7. [Co odkryliśmy po drodze](#7-co-odkryliśmy-po-drodze)
8. [Stan na koniec tygodnia](#8-stan-na-koniec-tygodnia)

---

## 1. Przegląd tygodnia

### Cel

Zamienić trzy "funkcje z AI w środku" (Szybcior, Uszatek, Blacha) w prawdziwych agentów — takich, które same decydują co zrobić, używają narzędzi i działają autonomicznie. Plus dodać zewnętrzne wyszukiwanie przez internet.

### Efekt

Przed tygodniem 5: tylko Pitbul był prawdziwym agentem. Pozostałe trzy dostawały gotowe dane i zwracały gotowy wynik — zero decyzji po drodze.

Po tygodniu 5: każdy z czterech agentów ma własną pętlę decyzyjną i własne narzędzia. System można uczciwie nazwać multi-agent.

### Liczby

- 4 agenty z własnymi pętlami ReAct
- 14 narzędzi łącznie
- 1 zewnętrzne API (Tavily — wyszukiwanie w internecie)
- 1 nowa tabela w bazie (historia planów)

---

## 2. Co zbudowaliśmy

### Szybcior — generator planów

**Przed:** Szybcior dostawał profil użytkownika i od razu generował plan. Jedno wywołanie AI, zero decyzji.

**Po:** Szybcior najpierw sprawdza historię poprzednich planów (żeby nie robić kopii), potem szuka wiedzy w bazie, jeśli baza nie wystarczy — szuka w internecie. Dopiero gdy ma wszystkie informacje, generuje plan. Może wykonać kilka kroków zanim odpowie.

**Dlaczego ważne:** Plany nie powtarzają już tych samych ćwiczeń. Szybcior wie co już było proponowane i robi coś innego.

### Uszatek — agent aktualizacji profilu

**Przed:** Uszatek zwracał JSON z informacjami o użytkowniku. Zewnętrzny kod czytał ten JSON i zapisywał do bazy. Uszatek nie miał żadnej sprawczości.

**Po:** Uszatek sam decyduje co zrobić i sam to wykonuje. Może zaktualizować profil bezpośrednio, oznaczyć konflikt gdy informacja się nie zgadza z profilem, albo sprawdzić w bazie wiedzy czy to co user mówi jest realistyczne.

**Przykład z testów:** User napisał że ma kontuzję barku. Uszatek sam zapisał to do profilu. Pitbul przy następnej wiadomości widział kontuzję i sam zamienił ćwiczenie obciążające bark na bezpieczną alternatywę.

### Blacha — agent pamięci

**Przed:** Blacha dostawała wiadomości z zewnątrz i zwracała podsumowanie. Ktoś inny to zapisywał.

**Po:** Blacha sama pobiera wiadomości z bazy, sama sprawdza co Uszatek ostatnio zmienił w profilu, sama zapisuje podsumowanie. Zero zależności od zewnętrznego kodu.

### Pitbul — nowe narzędzia

Pitbul dostał dwa nowe narzędzia:

- **Wyszukiwanie w internecie** — gdy baza wiedzy z ebooka nie ma odpowiedzi, Pitbul szuka na bieżąco w sieci
- **Rozwiązywanie konfliktów** — wcześniej Pitbul widział konflikty w profilu (np. "user mówi że waży 85kg ale w profilu mam 75kg") ale nie miał jak ich zamknąć. Teraz może zapytać usera, dostać potwierdzenie i zaktualizować profil jednym narzędziem

### Historia planów

Dodaliśmy tabelę w bazie która przechowuje wszystkie poprzednie plany — zarówno te wygenerowane przez Szybciora jak i każdą edycję zrobioną przez Pitbula. Dzięki temu Szybcior przy generowaniu nowego planu widzi całą historię i nie powtarza tych samych ćwiczeń.

---

## 3. Narzędzia agentów

| Agent | Model | Narzędzia | Tryb wywołania |
|---|---|---|---|
| **Pitbul** | Sonnet | `search_knowledge_tool`, `edit_plan_exercise`, `generate_training_plan`, `search_web_tool`, `resolve_conflict` | Blokujący — user czeka na odpowiedź |
| **Szybcior** | Sonnet | `search_knowledge`, `search_web`, `get_plan_history` | Blokujący — wywołany przez Pitbula przez `generate_training_plan` |
| **Uszatek** | Haiku | `update_user_profile`, `create_conflict`, `verify_with_knowledge` | Tło — user nie czeka |
| **Blacha** | Haiku | `get_recent_messages`, `get_profile_changes`, `update_summary` | Tło — co 15 wiadomości |

**Classifier:** Haiku (osobne wywołanie, ~5 tokenów) decyduje czy odpalić Uszatka — tak/nie na podstawie treści wiadomości.

---

## 4. Zmiany w plikach

| Plik | Status | Co robi |
|---|---|---|
| `backend/agents/plan_generator.py` | ✅ Przepisany | Szybcior jako LangGraph agent — graph: setup→agent→tools→finalize, retry node gdy pusta odpowiedź |
| `backend/agents/extraction.py` | ✅ Przepisany | Uszatek jako LangGraph agent — sam zapisuje do bazy, flaguje konflikty |
| `backend/agents/summarizer.py` | ✅ Przepisany | Blacha jako LangGraph agent — sama pobiera wiadomości i zmiany profilu, sama zapisuje summary |
| `backend/agents/graph.py` | ✅ Rozszerzony | Pitbul: +2 narzędzia (search_web, resolve_conflict), obsługa błędu gdy Szybcior zawiedzie, zapis edycji do plan_history |
| `backend/routers/chat.py` | ✅ Rozszerzony | Haiku classifier (`_should_run_extraction`), `background_tasks` — Uszatek i Blacha w tle |
| `backend/services/search.py` | ✅ Nowy | Wrapper na Tavily API — `search_web(query)` zwraca sformatowane wyniki |
| `backend/services/memory.py` | ✅ Rozszerzony | +5 funkcji: `get_plan_history`, `save_to_plan_history`, `get_unsummarized_count`, `get_profile_changes` |
| `backend/config.py` | ✅ Rozszerzony | `TAVILY_API_KEY` z env |
| `backend/requirements.txt` | ✅ Rozszerzony | `tavily-python` |

**Nowa tabela w bazie:** `plan_history` — przechowuje każdy wygenerowany plan i każdą edycję Pitbula (`source`: `szybcior` / `pitbul_edit`).

---

## 5. Decyzje które Konrad podjął

To są decyzje architektoniczne gdzie Konrad miał wybór i wybrał konkretne podejście. Ważne na rozmowie rekrutacyjnej bo pokazują myślenie o systemie, nie tylko wykonanie.

### "Uszatek i Blacha chodzą w tle, user nie czeka"

Były dwie opcje: albo Pitbul czeka na zakończenie Uszatka i Blachy zanim odpowie userowi, albo oni działają w tle a user dostaje odpowiedź od razu.

Konrad wybrał tło. Uzasadnienie: user zadał pytanie Pitbulowi, nie Uszatkowi. Uszatek i Blacha robią robotę administracyjną — zapisywanie profilu, aktualizowanie podsumowania. To nie powinno blokować rozmowy. Szybcior natomiast jest blokujący, bo user czeka na gotowy plan.

### "Haiku ocenia czy Uszatek ma co robić"

Uszatek działał przy każdej wiadomości. Konrad zaproponował żeby nie wywoływać go na każde "cześć" albo "ile serii na klatkę" — bo to marnowanie pieniędzy i zasobów.

Pomysł był żeby Pitbul to oceniał. Claude zaproponował listę słów kluczowych. Konrad odrzucił słowa kluczowe i powiedział: niech mały model AI (Haiku) sam oceni czy w wiadomości jest coś wartego zapisania. To bardziej niezawodne niż szukanie słów i kosztuje grosze.

Efekt: Uszatek odpala się tylko gdy wiadomość faktycznie zawiera informacje o użytkowniku.

### "Szybcior musi widzieć historię planów"

Do wyboru było: Szybcior sprawdza tylko aktualny plan (jeden rekord w bazie) albo widzi całą historię — wszystkie poprzednie plany i edycje.

Konrad wybrał pełną historię. Powód: jak user prosi o trzeci plan z rzędu, Szybcior musi wiedzieć co było w pierwszym i drugim żeby nie robić kopii. A Pitbul często edytuje konkretne ćwiczenia — Szybcior powinien też widzieć te drobne zmiany, nie tylko całe plany.

To wymagało nowej tabeli w bazie i zmiany w tym jak zapisujemy plany, ale było warte zachodu.

### "Nie robimy Agenta Progresji teraz"

Padł pomysł agenta który śledziłby czy user realizuje plan, czy robi postępy, czy jest stagnacja.

Konrad zdecydował: nie teraz. Powód: żeby taki agent miał co analizować, user musiałby raportować treningi w jakiś ustrukturyzowany sposób (formularz, komendy, cokolwiek). Tego nie ma. Agent analizowałby głównie ciszę. Wrócimy do tego gdy będzie feedback od użytkowników czy w ogóle chcą tak szczegółowo raportować.

---

## 6. Błędy które popełniliśmy

To jest sekcja której nie ma w poprzednich ADR-ach. Uczciwa lista rzeczy które zrobiliśmy źle — opisana tak żeby rozumieć dlaczego, nie tylko co.

### Błąd 1: Zapomniano dodać node do grafu

**Co się stało:** Dodaliśmy ścieżkę "retry" w grafie Szybciora (na wypadek gdyby Claude zwrócił pustą odpowiedź) ale zapomniano zarejestrować sam node. Serwer odmówił startu z błędem "unknown node 'retry'".

**Dlaczego:** Przy dodawaniu nowej ścieżki w LangGraph trzeba zrobić dwie rzeczy: dodać node i dodać edge. Zrobiliśmy tylko edge. Prosta pomyłka z nieuwagi.

**Nauka:** Przy każdej nowej ścieżce w grafie: node + edge, zawsze razem.

### Błąd 2: Nie sprawdzono ograniczeń bazy przed zmianą nazwy

**Co się stało:** Uszatek zapisywał do tabeli `profile_changes` z wartością `"uszatek"` w polu source. Baza danych miała ukryte ograniczenie (CHECK constraint) które dopuszczało tylko `"extraction_agent"`. Wywołanie się wysypało.

**Dlaczego:** Zmieniliśmy nazwę wartości w kodzie nie sprawdzając co baza danych akceptuje. Stara nazwa była `"extraction_agent"`, zmieniliśmy na `"uszatek"` bo bardziej logiczne — ale baza o tym nie wiedziała.

**Nauka:** Przed zmianą nazwy czegokolwiek co trafia do bazy — sprawdź czy baza nie ma na to ograniczenia.

### Błąd 3: Brak obsługi błędu gdy Szybcior zawiedzie

**Co się stało:** Pitbul wywoływał Szybciora i zakładał że dostanie plan. Gdy Szybcior zwrócił błąd zamiast planu, kod Pitbula próbował odczytać `result["plan"]` i crashował — bo klucz "plan" nie istniał, był tylko klucz "error".

**Dlaczego:** Pisząc kod "szczęśliwej ścieżki" nie pomyśleliśmy o tym co się stanie gdy Szybcior się nie powiedzie. Każde wywołanie zewnętrznego agenta może się nie udać — to powinno być od razu obsłużone.

**Nauka:** Zawsze zakładaj że zewnętrzne wywołanie może zwrócić błąd. Obsłuż to od razu, nie po fakcie.

### Błąd 4: Pitbul halucynował ID konfliktu

**Co się stało:** Pitbul dostał narzędzie `resolve_conflict` które wymaga podania ID konfliktu. ID to prawdziwy UUID z bazy (np. `75c63f79-448c-44e9-9c6c-e9f2dfc105cd`). Pitbul zamiast użyć tego UUID wymyślił własny: `"waga_user"`. Baza oczywiście tego nie znalazła i wywołanie crashowało.

**Dlaczego:** Claude wie że ma rozwiązać konflikt dotyczący wagi użytkownika, więc wymyślił "logiczną" nazwę `"waga_user"` zamiast skopiować prawdziwy UUID z system promptu. To klasyczna halucynacja — model rozumie intencję ale generuje coś wygodnego zamiast dokładnego.

**Rozwiązanie:** Gdy Pitbul poda zły ID, narzędzie teraz zwraca mu listę prawdziwych UUID z bazy i Pitbul robi poprawne wywołanie w następnej rundzie.

**Nauka:** Gdy narzędzie wymaga dokładnych identyfikatorów (UUID, ID z bazy), zawsze dodaj fallback który zwraca użytkownikowi prawidłowe wartości. Nigdy nie zakładaj że model skopiuje je idealnie.

### Błąd 5: Szybcior czasem zwracał pustą odpowiedź

**Co się stało:** Po kilku wywołaniach narzędzi Szybcior czasem zwracał pustą odpowiedź zamiast JSON z planem. Pętla się kończyła, plan się nie generował.

**Dlaczego:** Claude po zebraniu dużej ilości informacji (3 wyniki z bazy wiedzy) czasem "zapomina" co ma zrobić na końcu i zwraca pusty tekst zamiast wymaganego JSON. To zachowanie LLM przy dużym kontekście — model traci focus na oryginalnym zadaniu.

**Rozwiązanie:** Dodaliśmy node "retry" — jeśli odpowiedź jest pusta, agent dostaje krótką wiadomość "masz wszystkie dane, teraz daj mi JSON" i zazwyczaj przy drugim podejściu działa.

**Nauka:** W długich pętlach ReAct warto mieć mechanizm recovery. LLM może stracić focus po wielu krokach — krótkie przypomnienie zadania wystarczy żeby wróciło na właściwy tor.

---

## 7. Co odkryliśmy po drodze

Rzeczy które nie były planowane ale wyszły przy okazji.

### Luka w systemie konfliktów (istniejąca od tygodnia 2)

Odkryliśmy że od samego początku projektu system miał dziurę: Uszatek wykrywał konflikty i zapisywał je do bazy, Pitbul widział konflikty i pytał usera o potwierdzenie, ale nie było żadnego mechanizmu który zamykał tę pętlę. Konflikty siedziały w bazie z flagą `resolved: false` na zawsze bo Pitbul nie miał jak ich rozwiązać.

Naprawiliśmy to przy okazji: Pitbul dostał narzędzie `resolve_conflict` które po potwierdzeniu przez usera aktualizuje profil i zamyka konflikt.

### Classifier jako lepsza alternatywa dla słów kluczowych

Pierwotny pomysł na filtrowanie wiadomości dla Uszatka to była lista słów kluczowych ("kg", "boli", "kontuzja" itp.). To działa ale jest kruche — user może napisać "od miesiąca mam problem z kolanem" bez żadnego ze słów kluczowych.

Haiku jako classifier okazał się lepszy: rozumie intencję, nie szuka słów. Kosztuje tyle samo co kilka tokenów.

---

## 8. Stan na koniec tygodnia

### Co działa

- Cztery agenty z własną pętlą decyzyjną i narzędziami
- Szybcior generuje plany nie powtarzając poprzednich
- Uszatek autonomicznie aktualizuje profil, flaguje konflikty
- Pitbul zamyka konflikty po potwierdzeniu przez usera
- Blacha sama pobiera dane i aktualizuje pamięć
- Web search przez Tavily gdy baza wiedzy nie wystarczy
- Historia wszystkich planów i edycji w bazie

### Znane ograniczenia

- Szybcior po wielu wyszukiwaniach czasem potrzebuje "przypomnienia" żeby wygenerować JSON — retry node to łata, nie naprawia
- Blacha triggeruje co 15 wiadomości, nie per sesja — może summaryzować w środku aktywnej rozmowy
- Brak śledzenia realizacji planu (Agent Progresji) — odkładamy do Fazy 3

### Następne kroki

1. Stripe — płatności (Faza 2 z mvp-plan.md)
2. Strona ustawień (zmiana danych, usunięcie konta)
3. Agent Progresji — gdy będzie feedback od userów o logowaniu treningów
