# BEZ PIERDOLENIA — AI Trener

> AI trener odpowiadający na podstawie bazy wiedzy z książek i badań naukowych — nie z ogólnej wiedzy modelu.

---

## Spis treści

- [Co robi](#co-robi)
- [Funkcjonalności](#funkcjonalności)
- [Jak to działa](#jak-to-działa)
  - [Technicznie](#technicznie)
- [Architektura AI](#architektura-ai)
- [Technologie](#technologie)
- [Jak uruchomić](#jak-uruchomić)
- [Struktura projektu](#struktura-projektu)
- [Wyniki testów](#wyniki-testów)
- [Czego się nauczyłem](#czego-się-nauczyłem)
- [Autor](#autor)

---

## Co robi

**AI Trener** to webowa aplikacja SaaS, która zastępuje generyczne porady treningowe spersonalizowanym asystentem. Użytkownik wypełnia quiz startowy (cel, poziom zaawansowania, dostępny sprzęt, wyniki siłowni), po czym rozmawia z trenerem odpowiadającym na podstawie bazy wiedzy z książek i badań naukowych — zanim odpowie, przeszukuje 1364 fragmentów z 8 źródeł i opiera odpowiedź na tym co znalazł. Aplikacja pamięta profil użytkownika między sesjami, generuje gotowe plany treningowe i samodzielnie aktualizuje swoją wiedzę o użytkowniku w trakcie każdej rozmowy. Dostęp płatny przez Stripe: 19 / 69 / 189 PLN (tydzień / miesiąc / kwartał).

---

## Funkcjonalności

- **Chat z AI trenerem** — rozmowa z Claude Sonnet 4.6, odpowiedzi zakorzenione w bazie wiedzy — agent przed odpowiedzią przeszukuje 1364 fragmentów z 8 źródeł. Sam decyduje kiedy szukać w bazie, kiedy w internecie, a kiedy wygenerować plan
- **Quiz startowy** — 22 pytania zbierające profil użytkownika (cel, wiek, waga, poziom, sprzęt, wyniki na ćwiczeniach bazowych). Dane są używane przy każdej odpowiedzi
- **Generowanie planu treningowego** — Szybcior (Claude Sonnet) tworzy gotowy plan: ćwiczenia, serie, powtórzenia, progresja, notatki. Plan można edytować przez chat
- **Aktualizacja profilu w tle** — po każdej rozmowie Uszatek (Claude Haiku) wyciąga z niej nowe informacje o użytkowniku i aktualizuje profil bez pytania
- **Kondensacja historii** — co 15 wiadomości Blacha (Claude Haiku) tworzy podsumowanie sesji (max 250 słów), żeby agent zawsze miał kontekst nawet po długich rozmowach
- **Strona ustawień** — zmiana emaila, hasła, 18 pól profilu, podgląd planu, usunięcie konta
- **Subskrypcja Stripe** — płatność, automatyczne potwierdzenia, anulowanie z zachowaniem dostępu do końca okresu
- **Limit wiadomości** — 5/minutę i 100/dzień, liczony atomowo — równoległe requesty nie obchodzą limitu

---

## Jak to działa

Użytkownik zadaje pytanie. Zanim model odpowie, system przeszukuje bazę wiedzy złożoną z fragmentów książek i badań naukowych i wybiera te, które są najbardziej trafne dla tego konkretnego pytania. Łączy je z profilem użytkownika — celem, poziomem, dostępnym sprzętem, wynikami siłowni — i dopiero wtedy generuje odpowiedź. W tle, po każdej rozmowie, system automatycznie wyciąga nowe informacje o użytkowniku z treści rozmowy i aktualizuje jego profil. Co 15 wiadomości skraca historię do krótkiego podsumowania, żeby agent zawsze miał aktualny kontekst bez przesyłania całej historii.

### Technicznie

```
Użytkownik wpisuje wiadomość
        │
        ▼
[middleware.py] Weryfikacja JWT
  run_in_threadpool(supabase.auth.get_user) — nie blokuje event loop
  require_active_subscription → 403 jeśli brak aktywnej subskrypcji
        │
        ▼
[chat.py] Atomic rate limit check
  asyncio.Lock + _in_flight dict
  DB_count + in_flight[user_id] >= limit? → 429
        │
        ▼
[graph.py fetch_context] Równoległe pobieranie (ThreadPoolExecutor, 6 workerów):
  profil użytkownika, historia 6 wiadomości, podsumowanie sesji, pending_conflicts
        │
        ▼
[graph.py — Pitbul] LangGraph StateGraph (ReAct loop)
  fetch_context → orchestrator → tools ↔ orchestrator → post_process

  Dostępne narzędzia:
  • search_knowledge_tool  →  pgvector RPC match_knowledge() (top_k=5, threshold=0.3)
  • search_web_tool         →  Tavily
  • generate_training_plan  →  wywołuje Szybcior (osobny pipeline)
  • edit_plan_exercise      →  UPDATE w tabeli training_plans
  • resolve_conflict        →  rozwiązanie sprzeczności w profilu
        │
        ▼
[chat.py] SSE stream — cała odpowiedź w jednej paczce na końcu
  keepalive `: keepalive` co 20s (asyncio.shield + timeout)
  Disconnect? → agent_task.cancel() + asyncio.create_task(background_tasks)
        │
        ▼
[BackgroundTasks — w tle po odpowiedzi]
  save_messages()   →  tabela messages (null byte sanitization)
  extraction.py     →  Uszatek (Haiku): 1 wywołanie, JSON {updates, conflicts} → user_profiles
  summarizer.py     →  Blacha (Haiku): co 15 wiadomości, max 250 słów → conversation_summaries
```

### Kluczowe decyzje techniczne

**`ainvoke` zamiast `astream` w LangGraph**  
Frontend animuje "pisanie" przez CSS — backend zwraca całą odpowiedź w jednej paczce SSE. Alternatywa (`astream`) wymagałaby agregowania tokenów między tool calls po stronie klienta, co komplikuje obsługę błędów i kolejność wiadomości.

**Haiku dla Uszatka i Blachy, Sonnet dla Pitbula i Szybciora**  
Ekstrakcja JSON z rozmowy i sumaryzacja tekstu nie wymagają jakości Sonnet. Haiku jest ~15x tańszy — przy każdej wiadomości te dwa wywołania są obowiązkowe, więc koszt ma bezpośredni wpływ na marżę.

**Szybcior jako pipeline, nie agent**  
Generowanie planu to deterministyczny przepływ: pobierz RAG → wstrzyknij kontekst → generuj JSON. Próba użycia agenta z narzędziami dałaby te same wyniki z wyższymi kosztami i większą szansą na błąd.

**Osobny `supabase_admin` dla wszystkich zapisów DB**  
Po `supabase.auth.sign_up()` klient Supabase zmienia wewnętrzny token, co powoduje naruszenia RLS przy zapisach. `supabase` (anon key) — tylko auth; `supabase_admin` (service_role) — wszystkie zapisy do DB.

**Prompt caching Anthropic**  
Statyczna część system promptu Pitbula i Szybciora oznaczona `cache_control: ephemeral`. Cache TTL 5 minut — przy częstych requestach oszczędza ~80% kosztów tokenów wejściowych na statycznym kontekście.

---

## Architektura AI

### Pitbul — główny agent (`agents/graph.py`) · Claude Sonnet 4.6

Agent z pętlą decyzyjną (LangGraph ReAct). Przy każdym zapytaniu dostaje profil użytkownika, ostatnie 6 wiadomości z bazy, podsumowanie poprzednich sesji i listę nierozwiązanych sprzeczności w profilu. Sam decyduje które narzędzie wywołać i kiedy zakończyć — może przeszukać bazę kilka razy z różnymi zapytaniami, sprawdzić internet, wygenerować plan, albo odmówić jeśli pytanie jest poza zakresem.

**Narzędzia Pitbula:**

| Narzędzie | Co robi |
|---|---|
| `search_knowledge_tool` | Przeszukuje bazę wiedzy — 1364 fragmenty z 8 źródeł naukowych — i zwraca najbardziej trafne |
| `search_web_tool` | Tavily API — dla pytań spoza bazy wiedzy, np. aktualne badania lub sprzęt |
| `generate_training_plan` | Wywołuje Szybciora i zwraca wygenerowany plan treningowy |
| `edit_plan_exercise` | Modyfikuje konkretne ćwiczenie w planie (UPDATE w tabeli training_plans) |
| `resolve_conflict` | Rozwiązuje sprzeczność wykrytą przez Uszatka — aktualizuje profil po potwierdzeniu przez użytkownika |

---

### Szybcior — generator planów (`agents/plan_generator.py`) · Claude Sonnet 4.6

Generuje plan treningowy w jednym wywołaniu modelu, bez pętli decyzyjnej. Przed wywołaniem dostaje wyniki wyszukiwania w bazie wiedzy, historię poprzednich planów użytkownika i podsumowanie sesji — wszystko jako kontekst. Zwraca plan jako ustrukturyzowany JSON. Jeśli model zwróci pusty wynik, próbuje maksymalnie 5 razy.

---

### Uszatek — ekstrakcja profilu (`agents/extraction.py`) · Claude Haiku 4.5

Jedno wywołanie modelu uruchamiane w tle po każdej wymianie wiadomości. Dostaje ostatnią wymianę i aktualny profil użytkownika. Zwraca dwie listy: aktualizacje profilu (np. nowa waga) i wykryte sprzeczności (np. "napisał że jest początkującym, ale ma ławkę 100 kg"). Aktualizacje zapisywane są od razu. Sprzeczności trafiają do osobnej listy — Pitbul zapyta o nie przy kolejnej okazji.

---

### Blacha — sumaryzacja historii (`agents/summarizer.py`) · Claude Haiku 4.5

Jedno wywołanie modelu uruchamiane gdy nazbierało się 15 wiadomości. Odpala się też gdy użytkownik zamknie kartę przeglądarki lub zerwie połączenie. Dostaje ostatnie 15 wiadomości i poprzednie podsumowanie. Zwraca tekst max 250 słów, który Pitbul dostaje jako kontekst przy każdej kolejnej rozmowie.

---

## Technologie

### Backend

| Narzędzie | Do czego |
|---|---|
| Python 3.11+ | Język backendu |
| FastAPI | REST API + SSE streaming |
| LangGraph | Graf agenta Pitbul (ReAct loop z narzędziami) |
| langchain-anthropic | Integracja Claude z LangGraph |
| Anthropic SDK (≥0.39.0,<1.0.0) | Wywołania Claude z prompt caching |
| OpenAI SDK | Embeddingi do RAG (text-embedding-3-small) |
| Supabase Python | Klient bazy danych i autentykacji |
| Stripe | Płatności i subskrypcje |
| Tavily Python | Web search dla agenta |
| httpx | Async HTTP client (weryfikacja haseł) |
| Pydantic v2 | Walidacja requestów |
| LangSmith | Tracing wywołań LLM (opcjonalne) |

### Frontend

| Narzędzie | Do czego |
|---|---|
| Next.js ^16.2.4 | Framework (App Router) |
| React 19.2.4 | UI |
| TypeScript ^5 | Typowanie |
| Tailwind CSS ^4 | Stylowanie |
| react-markdown ^10.1.0 | Renderowanie odpowiedzi agenta w Markdown |
| remark-gfm ^4.0.1 | GitHub Flavored Markdown |

### Infrastruktura i serwisy zewnętrzne

| Serwis | Do czego |
|---|---|
| Supabase (PostgreSQL + pgvector) | Baza danych, autentykacja, wyszukiwanie semantyczne |
| Anthropic Claude Sonnet 4.6 | Główny agent (Pitbul) + generator planów (Szybcior) |
| Anthropic Claude Haiku 4.5 | Ekstrakcja profilu (Uszatek) + sumaryzacja (Blacha) |
| OpenAI text-embedding-3-small | Generowanie wektorów do wyszukiwania w bazie wiedzy (1364 fragmenty z 8 źródeł) |
| Tavily | Web search w czasie rzeczywistym |
| Stripe | Subskrypcje |
| Railway | Hosting backendu |
| Vercel | Hosting frontendu |

---

## Jak uruchomić

### Wymagania

- Python 3.11+, Node.js 20+
- Konto [Supabase](https://supabase.com) z włączonym rozszerzeniem `pgvector`
- Klucze API: Anthropic, OpenAI, Tavily, Stripe

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Zmienne środowiskowe

Utwórz `.env` w katalogu `backend/`:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...

SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...

STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_WEEK=price_...
STRIPE_PRICE_MONTH=price_...
STRIPE_PRICE_QUARTER=price_...

ALLOWED_ORIGINS=http://localhost:3000
```

Utwórz `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Baza wiedzy

Przed pierwszym uruchomieniem wgraj bazę wiedzy do Supabase:

```bash
# Umieść plik .docx w katalogu projektu
python scripts/ingest.py
```

Skrypt dzieli tekst na fragmenty semantyczne, generuje embeddingi i wgrywa do Supabase. Prosi o potwierdzenie przed wgraniem.

---

## Struktura projektu

```
bezp-rag-agent/
│
├── backend/
│   ├── main.py                  # Punkt wejścia FastAPI, CORS, rejestracja routerów
│   ├── config.py                # Klienty: supabase (anon), supabase_admin (service_role), openai
│   ├── middleware.py            # get_current_user (JWT + threadpool), require_active_subscription
│   ├── requirements.txt
│   │
│   ├── routers/
│   │   ├── auth.py              # /auth — rejestracja, logowanie, /me, refresh
│   │   ├── quiz.py              # /quiz/submit — zapis 22 pól profilu
│   │   ├── chat.py              # /chat — SSE, rate limiting (asyncio.Lock), /session-end
│   │   ├── plan.py              # /plan — GET plan, POST generate (wywołuje Szybciora)
│   │   ├── settings.py          # /settings — profil (18 pól), email, hasło, DELETE konta
│   │   └── payments.py          # /payments — Stripe checkout, webhook (3 eventy), anulowanie
│   │
│   ├── services/
│   │   ├── rag.py               # search_knowledge(): embedding → pgvector RPC match_knowledge()
│   │   ├── search.py            # search_web(): Tavily API
│   │   └── memory.py            # save_messages(), get_conversation_history(), summaries, profile
│   │
│   └── agents/
│       ├── graph.py             # Pitbul — LangGraph ReAct, 5 narzędzi, prompt caching
│       ├── extraction.py        # Uszatek — 1 wywołanie Haiku → {updates, conflicts} → DB
│       ├── summarizer.py        # Blacha — 1 wywołanie Haiku → max 250 słów summary → DB
│       └── plan_generator.py    # Szybcior — LangGraph pipeline bez tool calls, Sonnet, JSON planu
│
├── frontend/
│   └── src/app/
│       ├── page.tsx             # Landing page (publiczna)
│       ├── login/               # Logowanie / rejestracja
│       ├── quiz/                # Quiz startowy — 22 pytania
│       ├── chat/                # Główny widok czatu, SSE reader, sessionStorage
│       ├── plan/                # Widok i edycja planu treningowego
│       ├── settings/            # Profil, subskrypcja, usunięcie konta
│       └── pricing/             # Strona cenowa Stripe
│
├── scripts/
│   ├── ingest.py                # docx → fragmenty (GPT-4o-mini) → embeddingi → Supabase
│   ├── ingest_multi.py          # Ingestion wielu plików jednocześnie
│   ├── upload_chunks.py         # Upload gotowych fragmentów JSON
│   ├── agent.py                 # Test agenta w terminalu (bez pełnego stacku)
│   └── test_search.py           # Test RAG search — sprawdzenie co zwraca pgvector
│
└── docs/                        # ADR, architektura, schemat DB, system prompty (nie deployowane)
```

---

## Wyniki testów

Projekt przeszedł trzy rundy testów przed wdrożeniem na produkcję.

| Kategoria | Wynik |
|---|---|
| Bezpieczeństwo (OWASP Top 10 + specyficzne dla tej architektury) | **73/75 PASS** |
| Jakość odpowiedzi AI | **11/12 PASS (92%)** |
| Logowanie i subskrypcje | **10/10 PASS** |

**Testy bezpieczeństwa** obejmują próby włamania przez spreparowane dane wejściowe (SQL injection, XSS), próby dostępu do cudzych danych, omijanie płatności, 10 technik wyciągania instrukcji systemu z modelu AI i weryfikację poprawności nagłówków HTTP. 2 drobne ostrzeżenia, oba świadomie zaakceptowane.

**Testy jakości odpowiedzi** używają drugiego modelu AI jako sędziego — dostaje pytanie, odpowiedź agenta i kryterium oceny, wystawia ocenę 0–10. Agent 5/5 podał konkretne liczby i mechanizmy (nie ogólniki), 3/3 odmówił odpowiedzi na pytania poza zakresem, odpowiedzi na to samo pytanie były spójne. Jedyny nieudany test to celowo sprzeczne pytanie zadane na koncie zaawansowanego zawodnika — agent słusznie wykrył sprzeczność zamiast odpowiedzieć.

---

## Czego się nauczyłem

### Kiedy AI naprawdę "myśli", a kiedy tylko wykonuje instrukcje

Większość systemów AI to seria z góry ustalonych kroków — model dostaje pytanie, przeszukuje bazę, generuje odpowiedź. Pitbul działa inaczej: po każdym kroku sam decyduje co zrobić dalej. Może przeszukać bazę wiedzy trzy razy z różnymi pytaniami, sprawdzić internet, a na końcu stwierdzić że pytanie nie dotyczy treningu i odmówić odpowiedzi. Zrozumiałem że ta autonomia ma sens tylko tam gdzie nie wiadomo z góry ile kroków potrzeba — przy prostych, przewidywalnych zadaniach (jak streszczenie tekstu) to zbędna komplikacja.

### Jak dzielisz tekst źródłowy, tak dobra będzie odpowiedź AI

System przed odpowiedzią szuka w bazie wiedzy fragmentów pasujących do pytania. Jakość tego wyszukiwania zależy głównie od tego jak ten tekst był podzielony na fragmenty. Dzielenie mechanicznie co 500 znaków rozrywa myśli w połowie — model dostaje fragment bez początku lub końca. Wybrałem dzielenie przez AI: inny model czyta tekst i tnie go tam gdzie zmienia się temat. Efekt: gdy ktoś pyta o białko, system zwraca kompletne, sensowne akapity o białku — nie urwany fragment o suplementacji. Testy potwierdziły skuteczność — agent podaje konkretne liczby i mechanizmy biologiczne, nie ogólniki.

### Serwer który "czeka" jest zepsuty, nawet jeśli działa

Serwer obsługuje wiele requestów równocześnie. Biblioteka do bazy danych, której używam, blokuje jednak cały serwer podczas każdej operacji — dopóki nie sprawdzi tokenu, żaden inny request nie może przejść. To jak kasa w sklepie gdzie kasjer musi skończyć rozmowę przez telefon zanim obsłuży kolejnego klienta. Odkryłem to dopiero przy testach obciążeniowych. Rozwiązanie: biblioteka działa w osobnym wątku, serwer nie czeka na jej wynik. Drugi problem: rate limiter przepuszczał zbyt wiele requestów gdy przychodziły równocześnie, bo wszystkie odczytały "limit nie przekroczony" przed zapisem. Zabezpieczenie: sprawdzenie i zapis jako jedna niepodzielna operacja.

### Tańszy model tam gdzie wystarczy, droższy tam gdzie potrzeba

Modele AI różnią się jakością i ceną — nawet 15x. Napisałem najpierw wszystko na najmocniejszym modelu, bo "po co oszczędzać na jakości". Po analizie okazało się że dwa komponenty (wyciąganie danych z rozmów i robienie streszczeń) nie potrzebują inteligencji najmocniejszego modelu — wykonują powtarzalne zadanie według wzorca. Przełączenie ich na tańszy model nie pogorszyło jakości, a obniżyło koszt każdej wiadomości o ~70%. Nauczyłem się że dobieranie modelu do zadania to decyzja architektoniczna, nie oszczędzanie.

### Złożona infrastruktura tam gdzie wystarczy proste wywołanie

Uszatek i Blacha zaczęły jako pełnoprawne agenty z całą infrastrukturą do podejmowania decyzji i wywoływania narzędzi. Okazało się że ta infrastruktura nic nie robiła — oba komponenty miały jeden krok, żadnych decyzji do podjęcia, żadnych narzędzi. Usunąłem całą tę warstwę i zastąpiłem zwykłym wywołaniem modelu. Pytanie które zadaję teraz przed każdym architektonicznym wyborem: czy ten komponent musi zdecydować o czymś w trakcie działania? Jeśli nie — nie potrzebuje specjalnej infrastruktury.

### Zewnętrzne biblioteki się zmieniają bez pytania o zgodę

Trzy biblioteki zepsuły działający kod w trakcie projektu, każda inaczej: jedna usunęła metodę, druga zmieniła strukturę zwracanego obiektu, trzecia zmieniła sposób budowania zapytań. Żadna nie powiadomiła z wyprzedzeniem. Wniosek: dostęp do zewnętrznych bibliotek najlepiej izolować w jednym miejscu — wtedy zmiana biblioteki to zmiana w jednym pliku, nie szukanie wszystkich miejsc w kodzie.

---

## Autor

**Konrad Pochwała**

- GitHub: [DO UZUPEŁNIENIA]
- LinkedIn: [DO UZUPEŁNIENIA]
