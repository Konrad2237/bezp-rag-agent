# RAG Pipeline — chunking, ingestion, retrieval

> Strategia przetwarzania bazy wiedzy: jak dzielimy tekst, jak tworzymy embeddingi, jak wyszukujemy.
>
> Data: 2026-04-14

---

## 1. Źródła wiedzy

| Źródło | Format | Rozmiar | Priorytet | Status |
|---|---|---|---|---|
| Ebook "Bez pierdolenia" | PDF | ~90 stron, ~10 000 słów | Główne | Gotowy |
| Własne notatki / plany | Markdown lub tekst | Do ustalenia | Uzupełniające | Do przygotowania |
| Artykuły / linki | URL → tekst | Do ustalenia | Uzupełniające | Przyszłość |

---

## 2. Strategia chunkingu

### Dlaczego chunking jest ważny

RAG nie wysyła całego ebooka do agenta — wysyła tylko fragmenty (chunki) relevantne do pytania. Jakość chunkingu bezpośrednio wpływa na jakość odpowiedzi:

- Za duże chunki → agent dostaje za dużo tekstu, dużo nieistotnych informacji, wyższy koszt tokenów
- Za małe chunki → agent dostaje urwane zdania bez kontekstu, odpowiada niepełnie
- Źle podzielone (np. w środku akapitu) → embedding nie oddaje sensu fragmentu, similarity search zwraca śmieci

### Metoda podziału — semantyczna (po kontekście)

**Zasada: jeden chunk = jeden zamknięty temat.** Nie dzielimy mechanicznie co X tokenów. Dzielimy po sensie — każdy chunk powinien odpowiadać na jedno pytanie lub omawiać jedną koncepcję.

Dlaczego semantyczna a nie po tokenach:

- Ebook ma ~10 000 słów — to mały dokument. Wyjdzie ~20-40 chunków semantycznych, co jest idealnym zakresem dla pgvector
- Ebook ma jasną strukturę (rozdziały, podrozdziały) — naturalne granice tematów już istnieją
- Pytania userów będą tematyczne ("jak progresować?", "ile serii?") — chunk = temat = trafne dopasowanie
- Przy podziale po tokenach ryzykujesz chunk który zaczyna się w połowie jednego tematu i kończy w połowie drugiego — embedding jest "rozmyty", similarity search zwraca go na pytania o oba tematy, ale nie odpowiada dobrze na żaden
- Overlap (nakładka między chunkami) jest NIEPOTRZEBNY przy podziale semantycznym — kontekst nie jest ucięty, bo cały temat jest w jednym kawałku

### Jak dzielić w praktyce

**Krok 1: Zidentyfikuj tematy w ebooku**

Przejrzyj spis treści / nagłówki ebooka. Każdy podrozdział lub wyraźnie odseparowany temat = kandydat na chunk. Przykład:

| Chunk | Temat | Szacunkowy rozmiar |
|---|---|---|
| 1 | Wprowadzenie — dla kogo jest ten poradnik | ~300 słów |
| 2 | Progresja obciążeń — jak zwiększać ciężary | ~500 słów |
| 3 | FBW vs split — jaki plan wybrać | ~600 słów |
| 4 | Rozgrzewka — co robić przed treningiem | ~200 słów |
| 5 | Lista ćwiczeń na klatkę piersiową | ~400 słów |
| ... | ... | ... |

**Krok 2: Sprawdź rozmiar każdego chunka**

- Chunk poniżej 50 słów → za mały, embedding będzie słaby. Połącz z pokrewnym tematem
- Chunk 100-800 słów → idealny zakres. Zostaw jak jest
- Chunk powyżej 1000 słów (~1300 tokenów) → za duży, szukaj naturalnego podziału na pod-tematy. Np. jeśli "Ćwiczenia na nogi" omawia osobno przysiady, wypady i leg press — podziel na 3 chunki

**Krok 3: Nie dziel list i tabel**

Jeśli chunk zawiera listę ćwiczeń z seriami/powtórzeniami — cała lista to jeden chunk, nawet jeśli jest długa. Ucięta lista jest bezużyteczna.

### Parametry

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| Metoda podziału | Semantyczna (po tematach/kontekstach) | Jeden chunk = jeden zamknięty temat |
| Min rozmiar chunka | ~50 słów | Poniżej → embedding za słaby, połącz z pokrewnym |
| Max rozmiar chunka | ~1000 słów (~1300 tokenów) | Powyżej → szukaj naturalnego podziału na pod-tematy |
| Overlap | BRAK | Niepotrzebny — kontekst nie jest ucięty |
| Szacowana liczba chunków | 20-40 | Przy 10 000 słów i semantycznym podziale |

### Metadane chunka

Każdy chunk zapisywany z metadanymi:

| Pole | Przykład | Po co |
|---|---|---|
| source | 'ebook' | Rozróżnienie źródeł |
| source_page | 23 | Do ewentualnej referencji |
| section_title | 'Progresja obciążeń' | Kluczowe — opisuje temat chunka, pomaga w retrievalu |
| chunk_index | 5 | Kolejność w dokumencie |

section_title jest szczególnie ważny przy podziale semantycznym — to jest "etykieta" tematu. Przy retrievalu system może użyć go jako dodatkowego sygnału. Jeśli user pyta "jak zwiększać ciężary?", chunk z section_title "Progresja obciążeń" dostanie wyższy score.

### Kiedy podział semantyczny NIE wystarczy

Jeśli w przyszłości dodasz do RAG duże źródła (np. 100-stronicowy artykuł naukowy, duży zbiór notatek), podział semantyczny wymaga ręcznej pracy — musisz przejrzeć tekst i zidentyfikować tematy. Przy dużych zbiorach warto wrócić do podziału automatycznego (po tokenach z overlap). Ale przy ebooku 10k słów i kilkudziesięciu notatkach — semantyczny jest lepszy i warty tego wysiłku.

---

## 3. Ingestion pipeline

### Przegląd procesu

```
PDF ebooka
    │
    ▼
Ekstrakcja tekstu (z zachowaniem nagłówków)
    │
    ▼
Podział na chunki (hierarchiczny)
    │
    ▼
Dodanie metadanych do każdego chunka
    │
    ▼
Embedding każdego chunka (OpenAI text-embedding-3-small)
    │
    ▼
Zapis do Supabase (tabela knowledge_embeddings)
```

### Ważne decyzje

**Jednorazowy skrypt vs pipeline:**

Na MVP: jednorazowy skrypt uruchamiany ręcznie. Ebook się nie zmienia, więc nie potrzebujemy automatycznego reindexingu.

Post-MVP: skrypt n8n triggerowany gdy dodasz nowe źródło (notatki, artykuł).

**Czyszczenie tekstu z PDF:**

PDF-y bywają problematyczne — nagłówki/stopki na każdej stronie, numery stron, dziwne łamanie linii. Po ekstrakcji tekstu z PDF-a warto:
- Usunąć powtarzające się nagłówki/stopki
- Połączyć łamane linie w akapity
- Usunąć puste linie i nadmiarowe białe znaki

To nie musi być idealne — ale im czystszy tekst, tym lepsze embeddingi.

**Duplikaty:**

Przed zapisem nowego chunka sprawdź czy nie istnieje już identyczny (lub bardzo podobny) w bazie. Przy re-ingestion: usuń stare chunki ze źródła i wstaw nowe (nie dokładaj — bo będziesz mieć duplikaty).

---

## 4. Retrieval (wyszukiwanie)

### Przegląd procesu

```
Wiadomość usera: "Jaki plan treningowy dla początkującego?"
    │
    ▼
Truncate do 1000 znaków (safety net)
    │
    ▼
Embedding wiadomości (text-embedding-3-small)
    │
    ▼
Similarity search w pgvector (cosine distance)
    │
    ▼
Top 3-5 chunków z najwyższym score
    │
    ▼
Filtracja: odrzuć chunki z score < 0.3
    │
    ▼
Formatowanie chunków jako rag_context do PROMPT-01
```

### Parametry retrievalu

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| Top K | 5 (pobranie) → max 3 (po filtracji) | 5 daje bufor, filtracja odcina nierelevantne |
| Similarity threshold | 0.3 (cosine similarity) | Poniżej 0.3 chunk jest prawdopodobnie nierelevantny |
| Max znaków query | 1000 (truncate) | Ochrona przed przekroczeniem limitu tokenów embeddingu |
| Metric | Cosine distance | Standard dla text-embedding-3-small |

### Co się dzieje gdy nic nie pasuje

Jeśli WSZYSTKIE chunki mają score poniżej 0.3:

- rag_context = "Brak materiałów na ten temat w bazie wiedzy."
- Agent dostaje jasny sygnał że nie ma źródła
- PROMPT-01 nakazuje: "powiedz wprost że nie masz tego w swoich materiałach"
- Agent odpowiada: "Tego nie mam w swojej bazie, szczerze. Zapytaj trenera."

To jest kluczowy mechanizm anty-halucynacyjny.

### Formatowanie rag_context

Chunki przekazywane do agenta w formacie:

```
Fragment 1 (źródło: ebook, rozdział: "Pierwszy tydzień"):
[treść chunka]

---

Fragment 2 (źródło: ebook, rozdział: "Progresja obciążeń"):
[treść chunka]
```

Metadane (źródło, rozdział) pomagają agentowi zrozumieć kontekst i ewentualnie nawiązać do niego w odpowiedzi.

---

## 5. Testowanie RAG

### Testy jakości retrievalu

Przygotuj listę 15-20 pytań pokrywających różne tematy z ebooka. Dla każdego pytania:

1. Wiesz który fragment ebooka zawiera odpowiedź (ground truth)
2. Odpytaj system RAG
3. Sprawdź czy zwrócony chunk zawiera ten fragment
4. Zmierz similarity score

**Metryki:**
- Hit rate: w ilu przypadkach poprawny chunk był w top 3? Cel: powyżej 80%
- Średni score dla poprawnych chunków: powinien być powyżej 0.5

**Typowe problemy:**
- Niski hit rate → chunki za małe lub źle podzielone
- Wysoki score ale zły chunk → pytanie dwuznaczne, zmień pytanie testowe
- Wszystkie scores niskie → problem z embeddingami lub czyszczeniem tekstu

### Testy end-to-end z agentem

Po teście retrievalu — zadaj te same pytania agentowi (przez pełny pipeline) i sprawdź:
- Czy agent cytuje wiedzę z ebooka?
- Czy odpowiada "nie wiem" na pytania spoza bazy?
- Czy nie dodaje od siebie wymyślonych danych (halucynacja)?

Patrz [testing-and-ops.md](testing-and-ops.md) po pełną strategię testowania.

---

## 6. Aktualizacja bazy wiedzy

### MVP: ręczna

Gdy chcesz dodać nowe źródło (notatki, artykuł):
1. Przygotuj tekst w Markdown
2. Uruchom skrypt ingestion z parametrem source='notatki'
3. Sprawdź w Supabase czy chunki się dodały
4. Przetestuj 2-3 pytania na nowym materiale

### Post-MVP: półautomatyczna (n8n)

Flow w n8n:
1. Wrzuć plik do wyznaczonego folderu (np. Google Drive / folder na serwerze)
2. n8n wykrywa nowy plik (trigger)
3. Uruchamia skrypt ingestion
4. Wysyła Ci notyfikację "Zaindeksowano nowe źródło: X, Y chunków"

### Ważne: re-ingestion nie jest automatyczny

Gdy ZMIENIASZ istniejące źródło (np. aktualizujesz ebooka):
1. Usuń stare chunki tego źródła z bazy (DELETE WHERE source = 'ebook')
2. Uruchom ingestion ponownie
3. Nie dodawaj na wierzch — dostaniesz duplikaty

To celowa decyzja — automatyczny re-ingestion przy 10k słów jest ryzykowny (możesz stracić dane) i niepotrzebny (ebook się rzadko zmienia).
