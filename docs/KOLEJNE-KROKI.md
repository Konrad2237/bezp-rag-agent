# Kolejne kroki — post Tydzień 5

## Do zrobienia przed Stripe

### 1. Obniżyć limit pętli agentów (10 min)
Żeby agent nie odpalał 10 rund w poszukiwaniu idealnej odpowiedzi — tokeny idą, jakość nie rośnie.

Zmiany w 3 plikach:
- `backend/agents/plan_generator.py`: `recursion_limit: 15` → `10`
- `backend/agents/summarizer.py`: `recursion_limit: 12` → `8`
- `backend/agents/extraction.py`: `recursion_limit: 10` → `8`

---

### 2. Blacha — podsumowanie na koniec sesji (2-3h)
Teraz Blacha odpala się co 15 wiadomości. Rozmowa 14 wiadomości = brak podsumowania.

Plan:
- Frontend: `beforeunload` event → POST `/session-end`
- Backend: nowy endpoint sprawdza `get_unsummarized_count` — jeśli > 0, odpala Blachę
- Backup: n8n cron co godzinę, szuka sesji bez podsumowania od >2h

---

### 3. Monitoring — zero kodu, tylko API keys

**LangSmith** (darmowy) — widać każde wywołanie LLM: tokeny, czas, pełny trace grafu LangGraph.
Jak włączyć: dodać do `.env`:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<klucz z smith.langchain.com>
LANGCHAIN_PROJECT=bezp-rag-agent
```
To wystarczy. LangGraph automatycznie wysyła trace.

**Sentry** (darmowy) — automatyczne alerty gdy w kodzie wyskakuje błąd. Nie trzeba przeglądać Railway logs.
Jak włączyć: `pip install sentry-sdk` + 3 linijki w `main.py`.

**n8n alerty** (jak już masz n8n):
- Email gdy koszt API > X PLN/dzień
- Email gdy konflikt w profilu nierozwiązany > 3 dni

---

## Po tych trzech rzeczach → Stripe

Faza 2 z `mvp-plan.md`:
1. Stripe — płatności
2. Strona ustawień (zmiana danych, usunięcie konta)
3. Agent Progresji — Faza 3-4, dopiero gdy będzie feedback od userów czy chcą logować treningi

---

## Dodatkowe pomysły (bez terminu)

- Timeout 5s na wywołania narzędzi (Tavily, Supabase) — żeby agent nie wisial
- Logowanie kosztu tokenów per user_id — widać który user jest najdroższy
- Limit dla Uszatka: max 2 aktualizacje profilu na jedno wywołanie
- Szybcior: zapis "generuję..." do Supabase na starcie — jeśli crash, user wie co się stało
