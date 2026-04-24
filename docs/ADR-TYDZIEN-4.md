# ADR — Tydzień 4: Training Plan Generator + UX + Bugfixes

> Dokument decyzji architektonicznych dla Tygodnia 4 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie były problemy i decyzje, co odrzucono i co zostało.
>
> Data: 2026-04-17 | Autor: Konrad + Claude | Status: Ukończony

---

## Spis treści

1. [Przegląd tygodnia](#1-przegląd-tygodnia)
2. [Training Plan Generator — Szybcior](#2-training-plan-generator--szybcior)
3. [Zakładka Plan (/plan)](#3-zakładka-plan-plan)
4. [Rozbudowa agenta Pitbul](#4-rozbudowa-agenta-pitbul)
5. [UX i mobile](#5-ux-i-mobile)
6. [Bugfixes — sesja końcowa](#6-bugfixes--sesja-końcowa)
7. [RODO i polityka prywatności](#7-rodo-i-polityka-prywatności)
8. [Problemy i rozwiązania](#8-problemy-i-rozwiązania)
9. [Znane długi techniczne](#9-znane-długi-techniczne)
10. [Stan na koniec tygodnia](#10-stan-na-koniec-tygodnia)

---

## 1. Przegląd tygodnia

### Co miało powstać (plan)

- Priorytet 1: Markdown w chacie
- Priorytet 2: UX czatu (timeout, disable, 429)
- Priorytet 3: RODO (checkbox, polityka prywatności)
- Priorytet 4: Training Plan Generator (Szybcior + zakładka /plan)
- Priorytet 5: Stripe (świadomie odłożone)

### Co faktycznie powstało

Wszystkie 4 priorytety zostały zrealizowane. Dodatkowo zbudowano system edycji planu przez Pitbula, naprawiono serię bugów UX (mobile, zakładki, pamięć agenta, timeout) i wdrożono SSE keepalive dla długich operacji.

### Podsumowanie komponentów

| Komponent | Status | Opis |
|---|---|---|
| Szybcior — plan generator | ✅ | Agent generujący plany treningowe w JSON |
| Endpoint POST /plan/generate | ✅ | Wywołuje Szybciora, zwraca plan |
| Endpoint GET /plan/ | ✅ | Pobiera aktualny plan użytkownika |
| Zakładka /plan | ✅ | Widok planu, odświeżanie, responsive |
| Narzędzie edit_plan_exercise | ✅ | Pitbul może edytować ćwiczenia w planie |
| Narzędzie generate_training_plan | ✅ | Pitbul wywołuje Szybciora przez LangGraph |
| Markdown w chacie | ✅ | react-markdown + remark-gfm |
| SSE typing animation | ✅ | Efekt pisania znak po znaku |
| SSE keepalive | ✅ | Co 20s podczas długich operacji |
| JWT auto-refresh | ✅ | getValidToken() odświeża token gdy wygasa |
| RODO checkbox | ✅ | Zgoda przy rejestracji |
| Strona /privacy | ✅ | Statyczna polityka prywatności |
| Mobile viewport fix | ✅ | h-[100dvh] zamiast min-h-screen |
| Custom checkboxy (mobile) | ✅ | SVG checkboxy zamiast native |
| sessionStorage persistence | ✅ | Wiadomości czatu przeżywają zmianę zakładki |
| Historia po user_id | ✅ | Pamięć Pitbula niezależna od sesji |

---

## 2. Training Plan Generator — Szybcior

### Decyzja: osobny agent zamiast logiki wbudowanej w Pitbula

**Powód:** Generowanie planu to osobna, deterministyczna operacja — potrzebuje własnego promptu (PROMPT-04), własnych danych wejściowych i generuje strukturę JSON. Wbudowanie tego w Pitbula pogorszyłoby jakość obu zadań.

**Implementacja:** `backend/agents/plan_generator.py` — synchroniczna funkcja `run_plan_generator(user_id, generation_reason)` wywoływana przez Pitbula przez narzędzie LangGraph.

### PROMPT-04 — format JSON z doubled curly braces

**Problem:** PROMPT-04 zawierał przykład JSON z `{plan_name}`, `{goal}` itp. Python's `.format()` próbował je interpretować jako zmienne i rzucał `KeyError`.

**Rozwiązanie:** Wszystkie nawiasy klamrowe w przykładzie JSON w stringu promptu musiały być podwojone (`{{plan_name}}`, `{{goal}}`). Nawiasy które SĄ zmiennymi do `.format()` pozostały pojedyncze.

**Lekcja:** Każdy literalny `{` w stringu przekazywanym do `.format()` musi być escapowany jako `{{`.

### Parsowanie JSON z markdown code fences

Claude czasem zwraca JSON opakowany w ` ```json ... ``` `. Szybcior obsługuje oba przypadki:

```python
if raw.startswith("```"):
    lines = raw.split("\n")
    raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
plan_data = json.loads(raw)
```

### Zapis do bazy — select + update/insert zamiast upsert

**Problem:** `supabase.table("training_plans").upsert(..., on_conflict="user_id")` rzucał błąd `42P10 no unique constraint` — tabela `training_plans` nie miała UNIQUE constraint na `user_id`.

**Decyzja:** Zamiast dodawać constraint do bazy, zmieniono logikę na select + update/insert:

```python
existing = supabase.table("training_plans").select("id").eq("user_id", user_id).execute()
if existing.data:
    supabase.table("training_plans").update({...}).eq("user_id", user_id).execute()
else:
    supabase.table("training_plans").insert({...}).execute()
```

**Powód odrzucenia upsert:** Zmiana schematu bazy w środku tygodnia 4 byłaby ryzykowna. Logika select+update/insert jest równie prosta i nie wymaga migracji.

### Wywołanie synchronicznego agenta w async FastAPI

Szybcior jest funkcją synchroniczną (blokujące wywołanie Anthropic SDK). Wywołanie go bezpośrednio w async endpoint blokowałoby event loop FastAPI.

**Rozwiązanie:** `run_in_executor` w node `tool_dispatcher` LangGraph:

```python
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, tool_fn.invoke, tc["args"])
```

---

## 3. Zakładka Plan (/plan)

### Decyzja: osobna strona zamiast widoku w chacie

**Powód:** Plan treningowy to dokument — użytkownik wraca do niego wielokrotnie, nie raz po wygenerowaniu. Osobna strona pozwala na czytelny widok bez interfejsu czatu.

### Layout ćwiczeń — karty zamiast tabeli

**Powód:** Tabela z kolumnami (ćwiczenie, serie, powtórzenia, przerwa) na wąskim ekranie wymagałaby poziomego scrollowania. Karty flex ze statystykami po prawej działają na każdej szerokości.

### Silent polling co 3s gdy brak planu

Gdy użytkownik wchodzi na /plan bez wygenerowanego planu, strona co 3 sekundy cicho sprawdza czy plan się pojawił. Mechanizm wyłącza się gdy plan zostanie załadowany.

**Powód:** Pitbul może właśnie generować plan w chacie — zamiast kazać userowi ręcznie odświeżać, strona aktualizuje się sama.

### Nawigacja Chat ↔ Plan

Header na obu stronach zawiera nawigację z aktywnym stanem (biały background na aktywnej zakładce). Zakładka Plan jest zablokowana (`cursor-not-allowed`, szary tekst) gdy Pitbul generuje odpowiedź lub trwa typing animation — zapobiega to wyjściu z czatu w trakcie odpowiedzi.

---

## 4. Rozbudowa agenta Pitbul

### Decyzja: ainvoke zamiast astream

**Problem:** `astream(stream_mode="messages")` po wywołaniu narzędzia (np. Szybciora) nie yielduał kolejnych tokenów — odpowiedź Pitbula po zakończeniu narzędzia była pusta.

**Rozwiązanie:** Przejście na `ainvoke` — agent wykonuje całą pracę (włącznie z narzędziami), zwraca gotową odpowiedź, frontend animuje ją jako typing effect.

**Kompromis:** Brak prawdziwego token-by-token streamingu. Przy prostych odpowiedziach Pitbul i tak odpowiada w kilka sekund, więc różnica jest niezauważalna. Przy generowaniu planu (3 wywołania Claude) odpowiedź dochodzi po 60-90s — rozwiązane keepalivem SSE.

### SSE keepalive co 20s

Generowanie planu = 3 wywołania Claude (Pitbul decyduje → Szybcior generuje → Pitbul odpowiada). Łącznie 60-120 sekund bez żadnych danych do frontendu — Railway i przeglądarki zamykają idle connection.

**Rozwiązanie:** Backend uruchamia agenta jako `asyncio.Task` i co 20s wysyła komentarz SSE (`: keepalive`). Frontend ignoruje linie bez prefixu `data: `.

```python
agent_task = asyncio.create_task(run_agent())
while not agent_task.done():
    try:
        await asyncio.wait_for(asyncio.shield(agent_task), timeout=20.0)
    except asyncio.TimeoutError:
        yield ": keepalive\n\n"
```

### Timeout resetowany przy każdym chunk'u

Poprzednio: stały timeout 90s liczony od wysłania wiadomości.
Teraz: timeout 150s resetowany przy każdym odebranym chunk'u (keepalive lub token).

**Efekt:** Długie operacje (generowanie planu) nie powodują "brak odpowiedzi od serwera" — keepalive co 20s resetuje odliczanie.

### Narzędzie edit_plan_exercise

Pitbul może modyfikować konkretne ćwiczenie w planie bez wywoływania Szybciora. Tool przyjmuje `day_label`, `old_exercise_name` i opcjonalne nowe wartości. W przypadku nieudanego matchu zwraca pełną listę dostępnych dni i ćwiczeń, żeby Pitbul mógł spróbować ponownie z właściwą nazwą.

### System prompt — sekcja AKTUALNY PLAN TRENINGOWY

Pitbul dostaje w system prompcie pełną strukturę aktualnego planu użytkownika. Dzięki temu gdy user prosi o zmianę ćwiczenia, Pitbul wie jak dokładnie nazywają się dni i ćwiczenia i może poprawnie wywołać `edit_plan_exercise`.

### Historia wiadomości po user_id zamiast session_id

**Problem:** Sesja wygasała po 30 minutach bezczynności. Nowa sesja = pusta historia = Pitbul "zapomina" ostatnie wiadomości.

**Rozwiązanie:** `get_conversation_history` zmienione z filtrowania po `session_id` na ostatnie 20 wiadomości po `user_id`:

```python
result = supabase.table("messages")\
    .select("role, content")\
    .eq("user_id", user_id)\
    .order("created_at", desc=True)\
    .limit(20)\
    .execute()
return list(reversed(result.data or []))
```

**Efekt:** Pitbul zawsze widzi 20 ostatnich wiadomości niezależnie od sesji. Blacha (summarizer) nadal działa jako długoterminowa pamięć.

---

## 5. UX i mobile

### Mobile viewport — h-[100dvh]

**Problem:** `min-h-screen` (= `100vh`) nie uwzględnia paska adresu mobilnej przeglądarki. Na iOS/Android czat wychodził poza widoczny obszar.

**Rozwiązanie:** `h-[100dvh]` — `dvh` (dynamic viewport height) to CSS unit który uwzględnia aktualną wysokość viewport po schowaniu/pokazaniu paska przeglądarki.

### Custom checkboxy (SVG)

**Problem:** Native checkbox z `accent-white` nie renderował się poprawnie na niektórych urządzeniach mobilnych.

**Rozwiązanie:** Własny komponent — `div` z obramowaniem + SVG z ptaszkiem gdy `checked`:

```tsx
<div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${checked ? 'bg-white border-white' : 'border-zinc-600'}`}>
  {checked && <svg className="w-3 h-3 text-black" ...><path d="M2 6l3 3 5-5" /></svg>}
</div>
```

Użyty na checkboxach sprzętu w quizie i checkboxie RODO przy rejestracji.

### sessionStorage dla wiadomości czatu

**Problem:** Przejście na zakładkę /plan i powrót resetowało historię wiadomości czatu (Next.js rozmontowuje komponent przy nawigacji).

**Rozwiązanie:** Wiadomości zapisywane do `sessionStorage` przy każdej zmianie stanu. Przy montowaniu komponentu inicjalizowane z sessionStorage. Czyszczone przy wylogowaniu.

### Pełna odpowiedź zapisywana do sessionStorage od razu

**Problem:** Jeśli user wychodzi z /chat podczas typing animation (lub gdy Pitbul myśli), po powrocie wiadomość jest urwana.

**Rozwiązanie:** Gdy token dotrze (pełna odpowiedź jako jeden string), natychmiast zapisujemy go do sessionStorage przez `messagesRef`. Typing animation operuje na React state (pusty content, wypełniany znak po znaku). Po powrocie na /chat sessionStorage ma kompletną wiadomość.

```tsx
// Przy pierwszym tokenie:
const withFull = [...messagesRef.current, { role: 'assistant', content: fullContent }]
sessionStorage.setItem('bezp_chat_messages', JSON.stringify(withFull))
// React state — pusty content dla animacji:
setMessages(prev => [...prev, { role: 'assistant', content: '' }])
```

Fetch nie jest przerywany przy unmount — odpowiedź dochodzi do końca w tle nawet gdy user wyszedł z /chat.

### typingTargetIndexRef — fix race condition

**Problem:** Typing interval używał `prev[prev.length - 1]` jako target. Jeśli user wysłał kolejną wiadomość podczas animacji, `last` był wiadomością usera i litery trafiały do złego bąbelka.

**Rozwiązanie:** `typingTargetIndexRef` przechowuje konkretny indeks wiadomości asystenta w tablicy. Nawet jeśli tablica się powiększy, index zawsze wskazuje właściwy bąbelek.

---

## 6. Bugfixes — sesja końcowa

### Plan nie odświeżał się po edycji

**Przyczyna:** Przeglądarka cachowała odpowiedź GET `/plan/`.

**Fix:** Cache busting przez `?t=${Date.now()}` w URL i nagłówek `Cache-Control: no-cache` przy każdym fetchu planu.

### Przycisk Odśwież nie dawał feedbacku

**Przyczyna:** Brak osobnego stanu dla operacji odświeżania — `loading` był używany do initial load screen, nie do przycisku.

**Fix:** Osobny stan `refreshing`. Przycisk pokazuje "Odświeżam..." i jest `disabled` podczas fetchu.

### edit_plan_exercise — UPDATE po id zamiast user_id

**Problem:** `update().eq("user_id", user_id)` działał poprawnie gdy był jeden wiersz, ale był nieprecyzyjny — przy ewentualnych duplikatach zaktualizowałby wszystkie.

**Fix:** SELECT pobiera `id` konkretnego wiersza, UPDATE używa `.eq("id", plan_id)`.

### Supabase update bez sprawdzenia wyniku

**Problem:** Zarówno `edit_plan_exercise` jak i `run_plan_generator` wywoływały `.execute()` bez sprawdzania czy operacja się powiodła. Pitbul mógł mówić "zmieniono" mimo faktycznego błędu.

**Fix:** Sprawdzanie `update_res.data` po każdej operacji zapisu. Jeśli puste — zwracamy błąd który Pitbul dostaje jako wynik narzędzia.

### Duplikat klucza przy rejestracji na mobile

**Przyczyna:** `upsert` na tabeli `user_profiles` bez `on_conflict` zachowywał się nieprzewidywalnie.

**Fix:** `upsert(..., on_conflict="user_id")`.

---

## 7. RODO i polityka prywatności

### Checkbox zgody przy rejestracji

Wymagany przed wysłaniem formularza. Walidacja po stronie frontendu (`if (!gdprConsent) setError(...)`). Custom SVG checkbox (spójny ze sprzętem w quizie).

Tekst: *"Akceptuję politykę prywatności i wyrażam zgodę na przetwarzanie danych osobowych, w tym danych zdrowotnych (waga, kontuzje), w celu korzystania z usługi AI trenera personalnego."*

### Strona /privacy

Statyczna strona z polityką prywatności. Zawiera: cel przetwarzania danych, katalog zbieranych danych (email, dane treningowe, wiadomości), podstawę prawną (zgoda RODO Art. 6), prawa użytkownika, kontakt.

**Decyzja:** Brak middleware sprawdzającego czy user zaakceptował — checkbox przy rejestracji jest wystarczający na MVP. Dodatkowe wymagania (np. wersjonowanie zgód) post-MVP.

---

## 8. Problemy i rozwiązania

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `KeyError: '\n  "plan_name"'` | `{plan_name}` w przykładzie JSON w PROMPT-04 interpretowany przez `.format()` | Doubled curly braces: `{{plan_name}}` w przykładzie |
| `42P10 no unique constraint` | `upsert(on_conflict="user_id")` na tabeli bez UNIQUE constraint | Zastąpienie upsert logiką select + update/insert |
| `from routers.auth import get_current_user` | Zły import — middleware jest w `middleware.py`, nie w `routers/auth.py` | `from middleware import get_current_user` |
| Puste bąbelki po wywołaniu narzędzia | `astream(stream_mode="messages")` nie yielduał tokenów po tool call | Przejście na `ainvoke` + pełna odpowiedź na raz |
| Event loop blokowany przez Szybciora | Synchroniczny Szybcior blokował async FastAPI | `run_in_executor` w `tool_dispatcher` |
| Timeout przy generowaniu planu | 3 wywołania Claude × ~30s = 90s, stary limit = 90s | SSE keepalive + reset timeout przy każdym chunk'u |
| Urwana odpowiedź przy zmianie zakładki | Abort na unmount przerywał fetch; setState po unmount ignorowany | Fetch żyje po unmount; pełna odpowiedź do sessionStorage przez messagesRef natychmiast gdy token dotrze |
| Pitbul nie pamiętał ostatnich wiadomości | Historia ładowana po session_id; sesja wygasała po 30 min | Historia po user_id — ostatnie 20 wiad. niezależnie od sesji |
| Checkboxy niewidoczne na mobile | `accent-white` nie działał na niektórych przeglądarkach mobilnych | Custom SVG checkboxy |
| Plan nie odświeżał się po edycji | Przeglądarka cachowała GET /plan/ | Cache busting `?t=timestamp` + `Cache-Control: no-cache` |
| Pitbul mówił "zmieniono" mimo błędu | Brak sprawdzania wyniku Supabase update | Sprawdzanie `update_res.data`, błąd zwracany do Pitbula |
| Pitbul źle matchował nazwy ćwiczeń | Podawał inną nazwę niż w planie | Tool zwraca pełną listę dostępnych ćwiczeń przy błędzie |
| Duplikat klucza na mobile przy quizie | `upsert` bez `on_conflict` | `upsert(on_conflict="user_id")` |

---

## 9. Znane długi techniczne

| # | Dług | Priorytet | Kiedy naprawić |
|---|---|---|---|
| 1 | Stripe — płatności i dostęp | Wysoki | Po potwierdzeniu wartości produktu z prawdziwymi userami |
| 2 | Token JWT w localStorage (nie httpOnly cookie) | Niski | Post-MVP |
| 3 | Brak prawdziwego token-by-token streamingu | Niski | Jeśli użytkownicy zgłoszą że odpowiedzi dochodzą za wolno |
| 4 | Brak retry logic przy błędach Supabase | Niski | Post-MVP |
| 5 | edit_plan_exercise nie obsługuje usuwania ćwiczenia | Niski | Gdy user zgłosi potrzebę |
| 6 | Brak strony ustawień (zmiana danych, usunięcie konta) | Średni | Przed publicznym launch z większą liczbą userów |
| 7 | Brak paginacji historii wiadomości | Niski | Gdy użytkownicy będą mieć >100 wiadomości |

---

## 10. Stan na koniec tygodnia

### Co działa

- Cały flow użytkownika: rejestracja → quiz → chat → plan
- Pitbul: konwersacja, RAG, pamięć (Blacha), ekstrakcja (Uszatek), generowanie planów (Szybcior), edycja ćwiczeń
- Zakładka /plan: widok planu, odświeżanie, silent polling gdy brak planu
- Mobile: poprawny viewport, custom checkboxy, responsive layout
- Markdown w chacie: listy, bold, nagłówki, kod
- RODO: checkbox zgody, strona /privacy
- Typing animation z keepalive SSE
- sessionStorage: wiadomości przeżywają zmianę zakładki, pełna odpowiedź przy powrocie

### Co nie zostało zrobione

- Stripe (świadomie odłożone)
- Testy z zewnętrznymi użytkownikami

### Następne kroki (Tydzień 5 / Faza 2)

1. Testy z prawdziwymi użytkownikami — zebranie feedbacku
2. Stripe — płatności, gdy produkt potwierdzony przez userów
3. Strona ustawień (zmiana wagi, celu, usunięcie konta)
4. Powiadomienia push lub email (np. przypomnienie o treningu) — post-MVP

### URL produkcyjny

**Frontend:** https://bezp-rag-agent.vercel.app
**Backend:** https://bezp-rag-agent-production.up.railway.app
**Health check:** https://bezp-rag-agent-production.up.railway.app/health
