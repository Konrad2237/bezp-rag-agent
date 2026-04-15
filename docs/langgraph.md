# LangGraph — architektura grafu agentów

> Jak agenci łączą się w graf, jakie narzędzia ma Orchestrator, co jest w grafie a co poza nim.
>
> Data: 2026-04-14

---

## 1. Agent vs pipeline

System może działać na dwa sposoby:

**Pipeline (chatbot z RAG):** Wiadomość → pobierz kontekst → wyślij do LLM → odpowiedz. LLM nie podejmuje żadnych decyzji poza treścią odpowiedzi. RAG zawsze odpytany, plan generowany tylko na żądanie.

**Agent z narzędziami (LangGraph ReAct):** Wiadomość → agent MYŚLI → agent DECYDUJE czy użyć narzędzia → jeśli tak: wywołuje, czyta wynik, decyduje znowu → odpowiada.

**Wybieramy agenta z narzędziami** — bo agent sam decyduje kiedy szukać w bazie wiedzy, kiedy generować plan, kiedy dopytać usera. To jest prawdziwy agent i to chcemy mieć w portfolio.

---

## 2. Struktura grafu

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  fetch_context  │
                  │                 │
                  │  Równolegle:    │
                  │  - profil usera │
                  │  - summary      │
                  │  - historia     │
                  │  - pending      │
                  │    conflicts    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  ORCHESTRATOR   │◄──────────────────┐
                  │  (Claude Sonnet)│                    │
                  │                 │   Pętla narzędzi:  │
                  │  Decyduje:      │   agent wywołuje   │
                  │  - odpowiedzieć │   narzędzie,       │
                  │  - użyć narzę- │   czyta wynik,     │
                  │    dzia         │   decyduje znowu   │
                  └───────┬────────┘                    │
                          │                             │
                   ┌──────┴──────┐                      │
                   │             │                      │
              odpowiedź     tool call                   │
                   │             │                      │
                   │             ▼                      │
                   │    ┌────────────────┐              │
                   │    │  WYKONAJ       │              │
                   │    │  NARZĘDZIE     │──────────────┘
                   │    │                │  (wynik wraca
                   │    │ - search_rag   │   do agenta)
                   │    │ - gen_plan     │
                   │    │ - update_goal  │
                   │    └────────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │  post_process   │
          │                 │
          │  - zapisz msg   │
          │  - extraction   │
          │    (background) │
          │  - summarizer   │
          │    (background) │
          └────────┬────────┘
                   │
                   ▼
              ┌─────────┐
              │   END   │
              └─────────┘
```

---

## 3. State — dane przepływające przez graf

Stan to obiekt przechodzący między node'ami. Każdy node czyta z niego i/lub dopisuje.

| Pole | Typ | Ustawiane przez | Czytane przez |
|---|---|---|---|
| user_id | string | Chat API (z JWT) | Wszystkie node'y |
| user_message | string | Chat API (z requestu) | fetch_context, orchestrator |
| user_profile | dict | fetch_context | orchestrator |
| memory_summary | string | fetch_context | orchestrator |
| conversation_history | lista | fetch_context | orchestrator |
| pending_conflicts | lista | fetch_context | orchestrator |
| agent_response | string | orchestrator | post_process |
| tool_results | lista | narzędzia | orchestrator |

---

## 4. Node'y

### Node 1: fetch_context

Pobiera równolegle 4 rzeczy z Supabase:

1. Profil usera z `user_profiles`
2. Podsumowanie z `conversation_summaries`
3. Ostatnie 10 wiadomości z bieżącej sesji z `messages`
4. Nierozwiązane konflikty z `pending_conflicts`

NIE pobiera RAG context — to jest narzędzie agenta (agent decyduje kiedy szukać).

Zapisuje wyniki do state.

### Node 2: orchestrator

Serce systemu. Claude Sonnet z PROMPT-01 jako system prompt + kontekst ze state + dostępne narzędzia.

Pętla agenta:
1. Czyta wiadomość usera + kontekst
2. Decyduje: odpowiedzieć od razu, czy najpierw użyć narzędzia?
3. Jeśli narzędzie → wywołuje, czyta wynik, wraca do kroku 2
4. Jeśli odpowiedź → generuje tekst (streaming), zapisuje do state

### Node 3: post_process

Po odpowiedzi agenta (nie blokuje usera — background):
1. Zapisuje wiadomości (user + agent) do `messages`
2. Aktualizuje `last_activity_at` w sesji
3. Triggeruje Extraction Agent (PROMPT-02) w tle
4. Jeśli msg_count % 10 == 0 → triggeruje Summarizer (PROMPT-03) w tle

---

## 5. Narzędzia (tools) Orchestratora

### Narzędzie 1: search_knowledge

| | |
|---|---|
| **Kiedy agent go używa** | Gdy user pyta o coś co wymaga wiedzy z ebooka (ćwiczenia, progresja, plany) |
| **Kiedy NIE używa** | "Cześć", pytanie o samopoczucie, rozmowa nie wymagająca faktów |
| **Wejście** | Query (string) — agent sam formułuje zapytanie do bazy wiedzy |
| **Wyjście** | Top 3 chunki z RAG lub "Brak materiałów na ten temat" |
| **Model** | text-embedding-3-small (embedding) + pgvector (search) |

Dlaczego RAG jako narzędzie a nie pre-fetch:
- Nie każda wiadomość wymaga RAG. "Cześć" nie potrzebuje szukania w ebooku
- Agent sam formułuje query. User pisze "co robić jak boli bark?", agent szuka "kontuzja bark alternatywne ćwiczenia" — lepszy query niż surowa wiadomość
- Bardziej agentic = lepiej w portfolio

Kompromis: dodaje jedną rundę LLM (agent decyduje → szuka → odpowiada). Dodatkowe 1-2s latency. Przy streamingu user widzi "agent pisze..." więc jest OK.

### Narzędzie 2: generate_training_plan

| | |
|---|---|
| **Kiedy agent go używa** | Gdy user prosi o plan lub agent uzna że pora zaproponować |
| **Kiedy NIE używa** | Przy zwykłej rozmowie, pytaniach o technikę |
| **Wejście** | Powód generowania (string) — np. "user poprosił o plan na masę 3x/tydzień" |
| **Wyjście** | Plan treningowy (JSON) zapisany do `training_plans` + potwierdzenie |
| **Model** | Claude Sonnet (PROMPT-04) |

Typowe triggery — agent decyduje sam:
- User wprost prosi: "Ułóż mi plan"
- Pierwsza rozmowa po quizie — agent proponuje: "Mogę Ci ułożyć plan, chcesz?"
- User zmienił cel — agent proponuje nowy plan

### Narzędzie 3: update_user_goal

| | |
|---|---|
| **Kiedy agent go używa** | Gdy user WPROST mówi "zmień mój cel na redukcję" i agent chce potwierdzić |
| **Kiedy NIE używa** | Drobne aktualizacje — robi Extraction Agent w tle |
| **Wejście** | Pole do aktualizacji + nowa wartość |
| **Wyjście** | Potwierdzenie aktualizacji |

Opcjonalne na MVP. Extraction Agent robi to samo w tle. Ale daje agentowi możliwość natychmiastowej aktualizacji z potwierdzeniem w rozmowie.

---

## 6. Co jest w LangGraph, co nie

| Element | W LangGraph? | Dlaczego |
|---|---|---|
| fetch_context | Tak (node) | Część synchronicznego flow |
| Orchestrator | Tak (node z narzędziami) | Serce agenta |
| search_knowledge | Tak (tool) | Agent decyduje kiedy szukać |
| generate_plan | Tak (tool) | Agent decyduje kiedy generować |
| update_user_goal | Tak (tool) | Agent decyduje kiedy aktualizować |
| post_process | Tak (node) | Część synchronicznego flow |
| Extraction Agent | Nie (background task) | Nie blokuje usera, uruchamiany po odpowiedzi |
| Summarizer | Nie (background task) | Nie blokuje usera, uruchamiany co 10 wiadomości |

Extraction i Summarizer to zwykłe async taski (FastAPI BackgroundTasks). Nie są node'ami LangGraph bo:
- Nie wpływają na to co user widzi w bieżącej odpowiedzi
- Gdyby były w grafie, user czekałby na ich zakończenie
- Nie podejmują decyzji — dostają input, zwracają output

---

## 7. Przepływ z perspektywy użytkownika

### Scenariusz: user pyta o progresję

```
User: "Jak zwiększać ciężary na ławce?"

fetch_context:
  → profil: {cel: masa, poziom: poczatkujacy, ...}
  → summary: "User trenuje od 2 tygodni, robi FBW 3x..."
  → historia: [ostatnie 3 wiadomości z tej sesji]
  → conflicts: brak

orchestrator (runda 1):
  Agent czyta pytanie + kontekst
  Agent myśli: "to pytanie o progresję, muszę sprawdzić bazę wiedzy"
  → TOOL CALL: search_knowledge("progresja obciążeń ławka początkujący")

search_knowledge:
  → embedding query → similarity search → top 3 chunki
  → zwraca chunki o progresji z ebooka

orchestrator (runda 2):
  Agent czyta chunki z RAG
  Agent myśli: "mam info, mogę odpowiedzieć"
  → ODPOWIEDŹ: "Dobra, na początku progresja jest prosta. [info z ebooka]
     Przy Twoim poziomie..."
  → streaming do usera

post_process:
  → zapis wiadomości
  → Extraction Agent: has_updates: false (pytanie o wiedzę, nie o usera)
```

### Scenariusz: user prosi o plan

```
User: "Ułóż mi plan treningowy"

fetch_context → orchestrator (runda 1):
  Agent myśli: "user chce plan, mam profil, użyję narzędzia"
  → TOOL CALL: generate_training_plan("user poprosił o plan, 
     cel: masa, 3 dni/tyg, początkujący")

generate_training_plan:
  → search_knowledge("plan treningowy masa początkujący FBW")
  → PROMPT-04 + profil + RAG → Claude Sonnet → JSON planu
  → zapis do training_plans
  → zwraca potwierdzenie + skrócony opis planu

orchestrator (runda 2):
  Agent czyta wynik narzędzia
  → ODPOWIEDŹ: "Dobra, ułożyłem Ci plan. FBW 3x tydzień, 
     skupiony na podstawowych ćwiczeniach. [krótki opis]
     Pełny plan masz w zakładce Plan."

post_process:
  → zapis, extraction, etc.
```

### Scenariusz: prosta rozmowa (bez narzędzi)

```
User: "Cześć, jak się masz?"

fetch_context → orchestrator (runda 1):
  Agent myśli: "powitanie, nie potrzebuję narzędzi"
  → ODPOWIEDŹ: "Siema! Dobrze, gotowy do roboty. Co tam u Ciebie?"

Bez search_knowledge, bez generate_plan.
Szybka odpowiedź, niski koszt.
```
