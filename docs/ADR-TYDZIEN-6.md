# ADR — Tydzień 6: Optymalizacja kosztów, latencji i monitoring

> Dokument decyzji architektonicznych dla Tygodnia 6 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie decyzje podjęto, jakie błędy popełniono i czego się nauczyliśmy.
>
> Data: 2026-04-21 | Autor: Konrad + Claude | Status: Ukończony

---

## Spis treści

1. [Przegląd tygodnia](#1-przegląd-tygodnia)
2. [Co zbudowaliśmy](#2-co-zbudowaliśmy)
3. [Optymalizacja kosztów i latencji — szczegóły techniczne](#3-optymalizacja-kosztów-i-latencji--szczegóły-techniczne)
4. [Monitoring — LangSmith i n8n](#4-monitoring--langsmith-i-n8n)
5. [Zmiany w plikach](#5-zmiany-w-plikach)
6. [Schemat zmian konfiguracyjnych](#6-schemat-zmian-konfiguracyjnych)
7. [Decyzje które Konrad podjął](#7-decyzje-które-konrad-podjął)
8. [Błędy które popełniliśmy](#8-błędy-które-popełniliśmy)
9. [Co odkryliśmy po drodze](#9-co-odkryliśmy-po-drodze)
10. [Proste wyjaśnienie rozwiązanych problemów](#10-proste-wyjaśnienie-rozwiązanych-problemów)
11. [Stan na koniec tygodnia](#11-stan-na-koniec-tygodnia)

---

## 1. Przegląd tygodnia

### Cel

Po tygodniu 5 system działał poprawnie, ale był drogi i wolny. Pitbul przy jednej wiadomości ze zmianą profilu zużywał ~19k tokenów na Sonnet. Szybcior przy generowaniu planu — 40 sekund i 17k tokenów. Blacha potrafiła odpowiadać po podsumowaniu zamiast kończyć pracę. Tydzień 6 to był tydzień naprawiania tych problemów.

### Cel dodatkowy

Ustrukturyzowanie Blachy tak, żeby wywoływała się po zamknięciu przeglądarki (koniec sesji), a nie tylko po 15 wiadomościach — bo ktoś mógł napisać 8 wiadomości i wyjść, nigdy nie osiągając progu 15.

### Efekt

- Pitbul: ~19k tokenów → ~12k; koszt ~15x niższy (Sonnet → Haiku); latencja porównywalna
- Blacha: 3 wywołania LLM → 2; odpala się też przy wyjściu ze strony
- Szybcior: prompt caching aktywny; limit tokenów zmniejszony z 4096 → 2048
- Monitoring: LangSmith traces + 3 automatyzacje n8n

---

## 2. Co zbudowaliśmy

### Blacha — wyzwalanie na koniec sesji

**Problem:** Blacha wyzwalała się tylko gdy nazbierało się ≥15 wiadomości od ostatniego podsumowania. User który napisał 8 wiadomości i wyszedł nigdy nie dostawał zaktualizowanego podsumowania — przy kolejnej wizycie Pitbul zaczynał bez kontekstu z poprzedniej sesji.

**Rozwiązanie:**

1. Frontend — `beforeunload` + `navigator.sendBeacon` wysyła token do `/chat/session-end`
2. Backend — endpoint weryfikuje token, sprawdza ile jest niespodsumowanych wiadomości, odpala Blachę w tle przez FastAPI `BackgroundTasks`
3. Podobnie przy wylogowaniu — `handleLogout` wywołuje `sendBeacon` zanim wyczyści localStorage

**Dlaczego sendBeacon a nie fetch:** `beforeunload` to jedyne zdarzenie które odpala się gdy użytkownik zamyka kartę. Problem: przeglądarka natychmiast zabija wszelkie asynchroniczne wywołania uruchomione w `beforeunload`. `sendBeacon` to jedyne API które działa w tym momencie — przeglądarka gwarantuje wysłanie requestu nawet po zamknięciu karty. Wadą `sendBeacon` jest brak możliwości ustawienia custom nagłówków (np. `Authorization`) — dlatego token JWT trafia w body requestu.

**Cooldown:** Endpoint sprawdza kiedy ostatnio Blacha działała (`conversation_summaries.updated_at`). Jeśli minęło mniej niż 30 minut od ostatniego podsumowania — nie odpala jej ponownie. Zapobiega sytuacji gdzie user otwiera i zamyka kartę co chwilę i generuje dziesiątki wywołań Blachy.

```
Frontend (beforeunload)
  └─► POST /chat/session-end  {token: "..."}
        ├─ verify token (Supabase)
        ├─ count unsummarized messages  (0 < count < 15)
        ├─ check cooldown  (updated_at > now - 30min → skip)
        └─ BackgroundTasks.add_task(run_summarizer_agent)
```

### Blacha — eliminacja zbędnego wywołania LLM

**Problem:** Po wywołaniu narzędzia `update_summary` (zapisanie podsumowania do bazy) Blacha wracała do agenta, który generował kolejną odpowiedź — potwierdzenie że podsumowanie zapisano. To było trzecie wywołanie LLM, całkowicie zbędne.

**Rozwiązanie:** `_blacha_after_tools` — funkcja która po każdym wywołaniu narzędzi sprawdza czy `update_summary` już się wykonało. Jeśli tak — kończy graf zamiast wracać do agenta.

```python
def _blacha_after_tools(state) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage) and "Podsumowanie zapisane" in str(msg.content):
            return END  # koniec — nie wracaj do agenta
    return "agent"
```

Zamiast `add_edge("tools", "agent")` — `add_conditional_edges("tools", _blacha_after_tools, {"agent": "agent", END: END})`.

Efekt: Blacha = 2 wywołania LLM (pobierz dane → zapisz) zamiast 3.

### Pitbul — zmiana modelu Sonnet → Haiku

**Problem:** Pitbul używał `claude-sonnet-4-20250514`. Przy wiadomości ze zmianą profilu (gdzie Uszatek po odpowiedzi wywoływał narzędzia) łączny koszt dochodził do ~19k tokenów i $0.15 za wiadomość.

**Rozwiązanie:** Zmiana na `claude-haiku-4-5-20251001`. Haiku jest ~20x tańszy od Sonnet i ~2x szybszy. Wątpliwość była czy Haiku da radę używać narzędzi (LangGraph tool use) — testy potwierdziły że tak.

**Wynik z logów:** Po zmianie Pitbul obsługując zmianę profilu użył ~16k tokenów i odpowiedział w 8 sekund. Przed zmianą: ~19k tokenów, 43 sekundy.

### Pitbul — prompt caching

**Przed:** SystemMessage zawierał jeden długi string łączący statyczny prompt + dynamiczne dane (profil usera, podsumowanie pamięci, historia planu, aktualny plan). Każde wywołanie Pitbula = pełny input tokenizowany od nowa.

**Po:** Split na dwa bloki:

```python
SystemMessage(content=[
    {
        "type": "text",
        "text": PITBUL_STATIC_PROMPT,       # ~4k tokenów, niezmienne
        "cache_control": {"type": "ephemeral"},  # cachuj to
    },
    {
        "type": "text",
        "text": dynamic_context,             # profil, plan, historia — zmienne
        # brak cache_control — nie cachuj, bo zmienia się per-user
    }
])
```

**Co to daje:** Anthropic cache'uje blok statyczny między wywołaniami (TTL 5 minut). Przy kolejnym wywołaniu Pitbula w tej samej sesji — statyczny blok (~4k tokenów) nie jest przetwarzany od nowa, płaci się za niego jak za 10% normalnej ceny. Potwierdzone w LangSmith: `cache_read_input_tokens: 4270` zamiast `input_tokens: 4270`.

**Historia wiadomości:** Zmniejszona z 10 do 6 ostatnich wiadomości. 6 wiadomości = pełny kontekst ostatniej wymiany zdań. Reszta jest w podsumowaniu Blachy — nie potrzeba więcej w raw historii.

### Szybcior — prompt caching

Identyczna technika co u Pitbula. Statyczny system prompt cachowany, dynamiczne dane (profil, podsumowanie, powód generowania) w HumanMessage.

**Dodatkowa zmiana:** `max_tokens` obniżone z 4096 → 2048. Plan treningowy w JSON mieści się w ~600-800 tokenach — 4096 było nadmiarowe i powodowało że model "mógł" generować dużo tekstu przed JSON. 2048 to wyraźny sygnał: bądź zwięzły.

**`recursion_limit`:** Poprzednia sesja obniżyła limit z 15 → 10 myśląc że to oszczędność. W tej sesji okazało się że 10 to za mało: Szybcior dla 3-dniowego planu potrzebuje: `get_plan_history` + `search_knowledge` + `search_web` (opcjonalnie) + generowanie JSON + opcjonalny retry. To może być 10+ kroków grafu. Przywrócono 15.

---

## 3. Optymalizacja kosztów i latencji — szczegóły techniczne

### Jak działa prompt caching Anthropic

Anthropic cache'uje prefixes promptu — jeśli zaczynasz request identycznym blokiem co poprzedni, nie płacisz pełnej ceny za jego tokenizację. Warunki:

- Blok musi mieć `"cache_control": {"type": "ephemeral"}`
- TTL cache = 5 minut
- Minimalna wielkość bloku do cachowania: 1024 tokeny (Sonnet/Haiku)
- Cache jest per-klucz API i per-model

Koszt cache miss (pierwsze wywołanie): normalna cena + 25% overhead za zapisanie do cache.
Koszt cache hit (kolejne wywołanie w ciągu 5 min): ~10% normalnej ceny za ten blok.

### Routing modeli

| Agent | Model przed | Model po | Powód |
|---|---|---|---|
| Pitbul | claude-sonnet-4-20250514 | claude-haiku-4-5-20251001 | 20x tańszy, rozmowa wystarczy Haiku |
| Szybcior | claude-sonnet-4-20250514 | claude-sonnet-4-20250514 | Zostaje Sonnet — generuje strukturalny JSON, Haiku był mniej niezawodny |
| Uszatek | claude-haiku-4-5-20251001 | claude-haiku-4-5-20251001 | Bez zmian |
| Blacha | claude-haiku-4-5-20251001 | claude-haiku-4-5-20251001 | Bez zmian |
| Classifier | claude-haiku-4-5-20251001 | claude-haiku-4-5-20251001 | Bez zmian |

### Liczby przed/po

| Operacja | Tokeny przed | Tokeny po | Latencja przed | Latencja po |
|---|---|---|---|---|
| Pitbul (prosta zmiana profilu) | ~19k | ~16k | 43s | 8s |
| Pitbul (zwykła wiadomość) | ~12k | ~12k (cache hit) | ~8s | ~5s |
| Szybcior (generowanie planu 3-dniowego) | ~17k | ~17k | 40s | 38s |
| Blacha (per sesja) | 3 wywołania LLM | 2 wywołania LLM | — | — |

Szybcior ma nadal ~40 sekund — to architektoniczny limit. 3 sekwencyjne wywołania Sonnet + narzędzia nie zejdą poniżej tego czasu bez pre-fetchingu RAG przed wywołaniem grafu. Zostawiamy na później.

---

## 4. Monitoring — LangSmith i n8n

### LangSmith

LangSmith to platforma Anthropic/LangChain do śledzenia wywołań LangGraph. Po skonfigurowaniu zmiennych środowiskowych każde wywołanie grafu pojawia się jako "trace" z pełnym drzewem kroków: który node, które narzędzie, ile tokenów, ile ms.

**Konfiguracja (zmienne env):**

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=bezp-rag-agent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

**Co widać w LangSmith:**
- Każdy node grafu (setup → agent → tools → finalize)
- Ile tokenów na wejściu vs wyjściu
- `cache_read_input_tokens` — ile tokenów przyszło z cache (potwierdza że caching działa)
- Czas każdego kroku
- Pełna treść wywołań (prompt + odpowiedź)

### n8n — automatyzacje (skonfigurowane przez Konrada samodzielnie)

Trzy workflow w n8n, odpytujące bezpośrednio Supabase przez REST API:

#### Workflow 1: Codzienny raport aktywności

**Cel:** Codziennie rano email z podsumowaniem aktywności użytkowników z ostatnich 24h.

**Pipeline:**
```
Schedule Trigger (codziennie rano)
  └─► HTTP Request → Supabase (dane dziś)
  └─► HTTP Request → Supabase (dane wczoraj)
  └─► Code (JavaScript) — agregacja:
        - liczba sesji / wiadomości / aktywnych userów
        - średnia, mediana, max na sesję
        - top user + % dominacji
        - % zmiana dzień do dnia
        - heurystyki: dominacja usera (>60%), krótkie sesje, anomalie
  └─► Basic LLM Chain (Claude Haiku) — interpretacja:
        - status systemu
        - podsumowanie trendów
        - wykryte ryzyka
        - rekomendacje
  └─► Send Email (HTML) — tabela z kolorami (zielony/czerwony), health score, komentarz AI
```

**Kluczowa decyzja:** Cała logika numeryczna w JavaScript (deterministyczna). Claude dostaje gotowe liczby i interpretuje — nie liczy. To zapobiega halucynacjom w metrykach.

#### Workflow 2: Alert — nierozwiązane konflikty (>24h)

**Cel:** Email gdy w tabeli `pending_conflicts` są konflikty z flagą `resolved: false` starsze niż 24h.

**Pipeline:**
```
Schedule Trigger
  └─► HTTP Request → Supabase (pending_conflicts)
        filtry: resolved=eq.false, created_at=lt.{{now - 1 dzień}}
  └─► Code — agregacja (count + lista konfliktów)
  └─► IF (count > 0)
        └─► Send Email
```

**Problem z autoryzacją:** Tabela ma RLS (Row Level Security). `anon key` zwracał puste dane. Rozwiązanie: `service_role_key` omija RLS — używany tylko w n8n (server-side, nie w kodzie frontendu).

#### Workflow 3: Health-check

**Cel:** Sprawdzenie czy backend żyje — alert gdy nie odpowiada.

**Pipeline:**
```
Schedule Trigger (co X minut)
  └─► HTTP Request → GET /health
  └─► IF (status != 200)
        └─► Send Email / alert
```

---

## 5. Zmiany w plikach

| Plik | Co się zmieniło |
|---|---|
| `backend/agents/graph.py` | Model Sonnet → Haiku; historia 10 → 6 wiad.; split systemu prompt na PITBUL_STATIC_PROMPT + dynamic_context; cache_control na statyczny blok |
| `backend/agents/plan_generator.py` | Split promptu — SZYBCIOR_STATIC_PROMPT (bez zmiennych) + dynamic dane w HumanMessage; cache_control na static blok; max_tokens 4096 → 2048; recursion_limit 10 → 15 |
| `backend/agents/summarizer.py` | Split systemu prompt — BLACHA_SYSTEM_PROMPT_STATIC + previous_summary w HumanMessage; cache_control; dodano `_blacha_after_tools`; zmieniono `add_edge("tools","agent")` → `add_conditional_edges` |
| `backend/routers/chat.py` | Nowy model `SessionEndRequest`; nowy endpoint `POST /chat/session-end`; import `BackgroundTasks`, `datetime`, `timedelta` |
| `frontend/src/app/chat/page.tsx` | Nowy `useEffect` z `beforeunload` + `sendBeacon`; fix `handleLogout` — sendBeacon przed czyszczeniem localStorage |

---

## 6. Schemat zmian konfiguracyjnych

### Zmienne środowiskowe dodane do Railway (backend)

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__xxxxxxxxxxxxxxxxxxxx
LANGCHAIN_PROJECT=bezp-rag-agent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### Jak działa prompt caching — schemat

```
Pierwsze wywołanie Pitbula:
  ┌─────────────────────────────────────────┐
  │ SystemMessage                           │
  │  Block 1: PITBUL_STATIC_PROMPT          │
  │           cache_control: ephemeral      │  ◄── Anthropic zapisuje do cache
  │  Block 2: dynamic_context (profil etc.) │
  └─────────────────────────────────────────┘
  Koszt: pełna cena + 25% za zapisanie do cache

Kolejne wywołanie w ciągu 5 minut:
  ┌─────────────────────────────────────────┐
  │ SystemMessage                           │
  │  Block 1: [z cache] ✓                   │  ◄── Nie przetwarza, płaci 10%
  │  Block 2: dynamic_context (nowy)        │  ◄── Przetwarza normalnie
  └─────────────────────────────────────────┘
  Koszt: 10% za blok statyczny + normalna cena za blok dynamiczny
```

### Jak działa endpoint session-end — schemat

```
Przeglądarka (beforeunload lub logout)
  │
  ▼ navigator.sendBeacon(POST /chat/session-end, {token: "jwt..."})
  │
  ▼ Backend /chat/session-end
  │  1. supabase.auth.get_user(token) → weryfikacja
  │  2. get_unsummarized_count(user_id) → count
  │  3. if count == 0: return (nic do roboty)
  │  4. if count >= 15: return (per-message trigger już to ogarnie)
  │  5. sprawdź updated_at w conversation_summaries
  │  6. if updated_at < now - 30min: return (cooldown)
  │  7. BackgroundTasks.add_task(run_summarizer_agent, user_id)
  │
  ▼ Blacha odpala się w tle, przeglądarka już zamknięta
```

### Jak działa graph Blachy po zmianie — schemat

```
Przed:
setup → agent → tools → agent → END
                 (update_summary) (potwierdzenie — zbędne)

Po:
setup → agent → tools → [_blacha_after_tools sprawdza]
                 (update_summary)   │
                                    ├─► update_summary wykonane → END (koniec)
                                    └─► inne narzędzie → agent (kontynuuj)
```

---

## 7. Decyzje które Konrad podjął

### "Haiku wystarczy dla Pitbula"

Wątpliwość: czy mniejszy model da radę używać narzędzi w pętli ReAct (LangGraph tool use), rozmawiać naturalnie i rozumieć kontekst treningu.

Konrad zdecydował: próbujemy. Test w logach potwierdził że Haiku poprawnie wywołuje narzędzia (`edit_plan_exercise`, `generate_training_plan`, `search_knowledge_tool`), odpowiada spójnie i rozumie polskie pytania. Szybcior został na Sonnet — generuje strukturalny JSON i tu Haiku był mniej niezawodny.

Uzasadnienie na rozmowie: routing modeli to standardowa praktyka produkcyjna. Nie każde zadanie wymaga największego modelu. Haiku na rozmowę, Sonnet na generowanie struktury — to właściwy podział.

### "Szybcior zostaje na Sonnet"

Konrad mógł zaoszczędzić więcej przenosząc Szybciora też na Haiku. Zdecydował nie ryzykować — Szybcior generuje JSON który musi być parsowany automatycznie. Jeden błąd w strukturze JSON = brak planu dla usera. Sonnet jest bardziej niezawodny w trzymaniu formatu. Koszt Szybciora (~17k tokenów Sonnet) akceptowalny bo odpala się raz per plan, nie per wiadomość.

### "Stripe odkładamy"

Konrad miał plan dodać Stripe w tygodniu 6. Zdecydował że szkoda czasu — na razie nie ma zamiaru sprzedawać, a Stripe wymaga dużo konfiguracji (webhooks, plany cenowe, obsługa failed payment). Lepiej zainwestować czas w solidność techniczną systemu i monitoring niż w infrastrukturę sprzedaży której nie będzie używana.

### "n8n samemu, bez pomocy Claude"

Konrad ogarnął konfigurację n8n samodzielnie. Trzy workflow: codzienny raport, alert konflikty, health-check. Zintegrowanie z Supabase przez REST API, obsługa RLS przez service_role_key, agregacja w JS, interpretacja przez Haiku. Konrad rozwiązał po drodze kilka nietrywialnych problemów (RLS, empty output, format danych) bez asysty.

---

## 8. Błędy które popełniliśmy

### Błąd 1: recursion_limit zbyt agresywnie obniżony

**Co się stało:** W poprzedniej sesji obniżono `recursion_limit` Szybciora z 15 → 10 myśląc że to optymalizacja. W tej sesji przy próbie generowania 3-dniowego planu pojawił się `GraphRecursionError` — graf się zatrzymał w połowie.

**Dlaczego:** Nie policzyliśmy faktycznej liczby kroków. Szybcior dla normalnego planu robi: setup → agent → tools (get_plan_history) → agent → tools (search_knowledge) → agent → [opcjonalnie tools (search_web)] → agent (generuje JSON) → finalize. To jest minimum 8 kroków, z opcjonalnym retry to nawet 11-12. Graf LangGraph liczy każde przejście między nodami — nie tylko wywołania LLM.

**Nauka:** Przed obniżaniem recursion_limit — policz faktyczne kroki grafu w scenariuszu worst-case, nie best-case. Przywrócono 15.

### Błąd 2: Blacha nie odpalała się przy wylogowaniu

**Co się stało:** Dodaliśmy `sendBeacon` w evencie `beforeunload`. Działało przy zamknięciu karty. Ale przy kliknięciu "Wyloguj" (przycisk w UI) Blacha się nie odpalała.

**Dlaczego:** `handleLogout` najpierw czyściło localStorage (`localStorage.removeItem('bezp_token')`), a dopiero potem nawigowało do strony głównej. Event `beforeunload` odpala się przy nawigacji i w nim czytamy `localStorage.getItem('bezp_token')` — ale token już był usunięty. Beacon wysyłał `{token: null}` i backend odrzucał jako unauthorized.

**Fix:** Przenieść wywołanie `sendBeacon` w `handleLogout` przed `localStorage.removeItem`. Sekwencja: sendBeacon → removeItem → router.push.

**Nauka:** Kolejność operacji ma znaczenie. Jeśli coś jest potrzebne w wywołaniu asynchronicznym — nie usuwaj tego przed wywołaniem.

### Błąd 3: Uszatek wywoływał narzędzie bez wymaganego parametru

**Co się stało:** Uszatek próbował zapisać notatkę do profilu wywołując `update_user_profile({'field': 'notatki'})` bez parametru `value`. SDK rzuciło błąd walidacji.

**Dlaczego:** Opis narzędzia w docstringu był zbyt lakoniczny — "aktualizuje pole w profilu". Model wiedział że chce zaktualizować `notatki` ale nie wiedział że musi podać nową wartość.

**Fix:** Rozbudowanie docstringa o przykład: "ZAWSZE podawaj oba parametry. Przykład: field='waga', value='85kg'". Model przy kolejnej próbie podał oba parametry poprawnie.

**Nauka:** Docstring narzędzia to de facto instrukcja dla LLM. Niejasny docstring = niejasne wywołanie. Konkretny przykład w docstringu jest ważniejszy niż opis ogólny.

### Błąd 4: Ścieżka Windows z różną kapitalizacją

**Co się stało:** Next.js rzucił błąd "invariant expected layout router to be mounted" przy uruchamianiu frontendu lokalnie.

**Dlaczego:** Folder był otworzony jako `C:\Users\pochw\Desktop\...` (duże D) ale process był uruchomiony z `C:\Users\pochw\desktop\...` (małe d). Windows na poziomie systemu plików nie rozróżnia, ale Next.js (i Node.js) ma własną logikę rozwiązywania modułów która jest case-sensitive.

**Fix:** Uruchomić terminal z poprawną kapitalizacją ścieżki.

**Nauka:** Na Windows — zawsze używaj spójnej kapitalizacji ścieżek przy pracy z Node.js/Next.js.

---

## 9. Co odkryliśmy po drodze

### Prompt caching działa — i jest potwierdzalne

Dodanie `cache_control` to jedna linijka kodu. Efekt widoczny w LangSmith: pole `cache_read_input_tokens` przy kolejnym wywołaniu zawiera liczbę tokenów które przyszły z cache zamiast być przetworzone od nowa. Bez LangSmith tego nie byłoby widać — optymalizacja byłaby nieweryfikowalna.

Wniosek: monitoring (LangSmith) pozwala udowodnić że optymalizacja działa, a nie tylko zakładać.

### Haiku sobie radzi z tool use w polskim

Wątpliwość przed zmianą była czy mniejszy model poprawnie wywołuje narzędzia w LangGraph w kontekście polskim. Okazało się że tak — Haiku wywołuje narzędzia poprawnie, parsuje odpowiedzi i kontynuuje konwersację naturalnie. Nieznaczna różnica w "jakości" odpowiedzi Pitbula nie była warta 20x wyższego kosztu Sonnet.

### sendBeacon — jedyne API które działa przy zamknięciu karty

Standardowy `fetch` w `beforeunload` jest zabijany zanim odpowiedź wróci. XMLHttpRequest synchroniczny blokuje zamknięcie karty. `sendBeacon` to specjalne API zaprojektowane dokładnie do tego przypadku — przeglądarka gwarantuje wysłanie requestu, ale nie gwarantuje odpowiedzi. Idealnie dopasowane do "odpal Blachę i zapomnij".

### n8n: trigger ≠ źródło danych

Konrad podczas konfiguracji n8n napotkał nieoczywisty koncept: Schedule Trigger nie dostarcza danych — on tylko uruchamia flow o określonej godzinie. Dane muszą być pobrane osobno przez HTTP Request node. To mylące na początku bo np. Webhook Trigger dostarcza dane (z body requestu) i tam granica jest rozmyta.

---

## 10. Proste wyjaśnienie rozwiązanych problemów

### Problem: "Pitbul kosztuje za dużo i odpowiada za wolno"

**Co to znaczy:** Każda wiadomość do Pitbula to wywołanie dużego modelu AI (Claude Sonnet). Sonnet to najinteligentniejszy model, ale też najdroższy i najwolniejszy. Rozmowa codzienna nie wymaga "Einsteina" — wystarczy "zdolny student".

**Jak naprawiliśmy:** Zmieniliśmy model Pitbula z Sonnet na Haiku. Haiku jest małym modelem Claude — 20 razy tańszy i 2 razy szybszy. Rozmowa codzienna ("jak mam ćwiczyć plecy?", "zmień mi to ćwiczenie") nie wymaga Sonnet. Szybcior który generuje plan treningowy w formacie JSON został na Sonnet — tu precyzja jest ważniejsza.

Wynik: wiadomość która wcześniej zajmowała 43 sekundy — po zmianie zajmuje 8 sekund.

### Problem: "Prompt caching — co to w ogóle jest?"

**Co to znaczy:** Za każdym razem gdy Pitbul dostaje wiadomość, serwer Anthropic przetwarza cały tekst który wysyłamy: instrukcje dla agenta, profil użytkownika, historię planu, poprzednie wiadomości. To dużo tekstu i dużo pieniędzy.

**Jak naprawiliśmy:** Instrukcje dla agenta (prompt) są zawsze takie same — nie zmieniają się między wiadomościami. Powiedzieliśmy Anthropic: "ten kawałek tekstu jest stały, trzymaj go w pamięci podręcznej". Przy kolejnej wiadomości Anthropic nie przetwarza go od nowa — bierze z cache i płacimy 10 razy mniej za ten kawałek.

Analogia: zamiast czytać całą instrukcję obsługi za każdym razem gdy używasz narzędzia — wiesz jak go używać po pierwszym przeczytaniu.

### Problem: "Blacha nie podsumowywała rozmów gdy wychodziłem przed 15 wiadomościami"

**Co to znaczy:** Blacha (agent pamięci) wyzwalała się automatycznie po 15 wiadomościach. Ale co jeśli napisałem 8 wiadomości i wyszedłem? Blacha się nie odpaliła. Przy następnej wizycie Pitbul zaczynał bez wiedzy o tej sesji.

**Jak naprawiliśmy:** Przeglądarka teraz informuje backend gdy zamykasz kartę lub wylogujesz się. Backend sprawdza ile wiadomości zostało niespodsumowanych i jeśli jest ich więcej niż 0 — odpala Blachę w tle. Ty już zamknąłeś kartę, ale Blacha działa jeszcze przez chwilę i zapisuje co było.

**Dlaczego to nieoczywiste technicznie:** Przeglądarka przy zamknięciu karty zabija wszystkie operacje sieciowe. Jest jedno specjalne API (`navigator.sendBeacon`) które pozwala wysłać ostatnią wiadomość zanim wszystko się zamknie. Token uwierzytelniający trafia w treści wiadomości (nie w nagłówku) bo to jedyny sposób.

### Problem: "Blacha robiła 3 wywołania AI zamiast 2"

**Co to znaczy:** Blacha miała do zrobienia: (1) pobierz wiadomości, (2) zapisz podsumowanie. Ale po zapisaniu wracała do modelu który generował potwierdzenie: "podsumowanie zostało zapisane". To trzecie wywołanie AI nic nie wnosiło — odpowiedź szła do nikąd.

**Jak naprawiliśmy:** Dodaliśmy sprawdzenie: "czy narzędzie `update_summary` właśnie się wykonało?". Jeśli tak — zakończ pracę bez pytania agenta o potwierdzenie. Oszczędzamy jedno wywołanie LLM przy każdym uruchomieniu Blachy.

### Problem: "Monitoring — skąd wiedzieć że optymalizacje działają?"

**Co to znaczy:** Zmieniliśmy model, dodaliśmy caching, zmniejszyliśmy historię. Ale skąd wiemy że to faktycznie działa i ile oszczędzamy?

**Jak naprawiliśmy:** Skonfigurowaliśmy LangSmith — platforma która "nagrywa" każde wywołanie agenta. Po każdej wiadomości widzimy: ile tokenów zużyto, ile przyszło z cache (oszczędność), ile ms zajął każdy krok, jaki był prompt i odpowiedź. Bez tego pracowalibyśmy w ciemno.

Plus trzy automatyczne raporty w n8n: codzienny email z aktywnością użytkowników, alert gdy są stare nierozwiązane konflikty, health-check backendu.

---

## 11. Stan na koniec tygodnia

### Co działa

- Blacha odpala się przy zamknięciu karty i przy wylogowaniu (nie tylko po 15 wiadomościach)
- Blacha = 2 wywołania LLM (nie 3)
- Pitbul na Haiku — ~15x tańszy, ~2x szybszy
- Prompt caching aktywny u Pitbula i Szybciora (potwierdzone w LangSmith)
- Historia wiadomości Pitbula: 6 ostatnich (wystarczające, mniej tokenów)
- LangSmith — pełny monitoring wywołań agentów
- 3 automatyzacje n8n: codzienny raport, alert konflikty, health-check

### Znane ograniczenia

- Szybcior — ~40 sekund to architektoniczny limit (3 sekwencyjne Sonnet). Można by zrównoleglić RAG search z wywołaniem agenta, ale to poważna zmiana architektury — odkładamy
- Blacha — cooldown 30 minut może być zbyt krótki jeśli user bardzo aktywnie używa aplikacji i wychodzi co chwilę
- Stripe — świadomie odłożony

### Następne kroki

1. Strona ustawień (zmiana celu, wagi, usunięcie konta)
2. Stripe — gdy będzie gotowość do sprzedaży
3. Agent Progresji — gdy pojawi się infrastruktura do logowania treningów przez usera
