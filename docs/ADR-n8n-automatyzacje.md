# ADR — Automatyzacje n8n dla projektu BEZ PIERDOLENIA

**Data:** 23.04.2026  
**Autor:** Konrad Pochwała  
**Status:** Wdrożone i aktywne

---

## Kontekst

Projekt BEZ PIERDOLENIA to AI trener personalny oparty na RAG i agentach. Backend działa na Railway, baza danych na Supabase, frontend na Vercel. n8n jest zainstalowany self-hosted na VPS (193.33.111.78) i służy jako warstwa automatyzacji i monitoringu — bez ingerencji w kod backendu.

---

## Zbudowane automatyzacje

### 1. Health Check backendu
**Jak działa:** Co 5 minut wysyła zapytanie do endpointu `/health` na Railway. Jeśli odpowiedź jest błędna lub brak odpowiedzi — natychmiastowy email z alertem.  
**Decyzja Konrada:** Częstotliwość co 5 minut — wystarczający czas reakcji przy zerowym koszcie na self-hosted n8n.  
**Błędy po drodze:** Brak — najprostsza automatyzacja, zbudowana jako pierwsza celowo.

---

### 2. Alert — nowy użytkownik
**Jak działa:** Co 5 minut odpytuje Supabase Auth API (`/auth/v1/admin/users`) z service role key. Filtruje userów stworzonych w ostatnich 5 minutach przez Code node w JavaScript. Jeśli znajdzie nowego — wysyła email z adresem email nowego użytkownika.  
**Decyzja Konrada:** Zamiast Supabase Database Webhook (który nie działał niezawodnie z n8n na `auth.users`) wybrano prostszy i bardziej niezawodny polling co 5 minut.  
**Błędy po drodze:**
- Pierwotna próba użycia Supabase webhook — nie działała
- Zły URL Supabase (brakujące `.supabase.co` w domenie)
- Literówka w project ID (`migoupbssklweifekuc` vs `migoupbssklweifekuct`)
- Filtrowanie po `created_at` wymagało Code node zamiast IF node

---

### 3. Nierozwiązane konflikty
**Jak działa:** Cron codziennie rano sprawdza tabelę `conflicts` w Supabase. Szuka konfliktów starszych niż 3 dni bez rozwiązania. Wysyła email z listą.  
**Decyzja Konrada:** Codzienny cron zamiast real-time — konflikty nie wymagają natychmiastowej reakcji.

---

### 4. Dzienny raport aktywności
**Jak działa:** Cron o 8:00 codziennie. Dwa równoległe zapytania do Supabase — dane z ostatnich 24h i dane sprzed 48h (poprzedni dzień). Merge node łączy wyniki. Code node (110+ linii JS) liczy statystyki: sesje, wiadomości, aktywni userzy, średnia/mediana na sesję, top user, health score, wykrywanie anomalii. Basic LLM Chain (Anthropic Claude) generuje komentarz AI. Email HTML z tabelką porównawczą i komentarzem.  
**Decyzja Konrada:** Dodanie porównania z poprzednim dniem (zmiana %), health score i komentarza AI — wykracza poza standardowy monitoring.  
**Błędy po drodze:**
- Merge node "Combine by Position" nie działał gdy jeden dzień nie miał danych
- Dwa emaile zamiast jednego — okazało się że workflow odpalam dwa razy ręcznie podczas testów, nie był to bug
- Nagłówki kolumn "Dziś/Wczoraj" zmieniono na konkretne daty (`dd.LL.yyyy`) bo raport przychodzi rano i "dziś" było mylące

---

### 5. Auto Ingest — automatyczne chunkowanie nowych dokumentów
**Jak działa:** Google Drive Trigger (polling co minutę) monitoruje folder `BEZP Sources` na Google Drive. Gdy pojawi się nowy plik TXT — pobiera go przez Google Drive node, wgrywa na VPS przez SSH Upload, odpala skrypt Python (`ingest_multi.py`) przez SSH Execute z flock (zabezpieczenie przed równoległym uruchomieniem). Code node parsuje output skryptu. Email z podsumowaniem: nazwa pliku, liczba nowych chunków, status.  
**Decyzja Konrada:** Google Drive jako interfejs wrzucania plików (zamiast ręcznego SCP) — wygodniejsze i bardziej CV-friendly.  
**Decyzja Konrada:** `flock -n /tmp/ingest.lock` — zabezpieczenie przed race condition gdy dwa pliki wrzucone jednocześnie.  
**Ograniczenie (świadoma decyzja):** Jeden plik na raz — przy wrzuceniu dwóch plików jednocześnie drugi zostanie pominięty przez flock. Akceptowalne przy obecnej skali.

---

## Problemy techniczne i decyzje infrastrukturalne

### Dostęp do VPS
- SSH kluczem przestało działać po długiej przerwie (connection timeout)
- Odzyskanie dostępu przez VNC w panelu webh.me → SystemRescue → mount /dev/vda2 → reset hasła root → reboot
- Wniosek: zapisywać hasła do menedżera haseł

### LangSmith API — nieudana próba
Podjęto próbę podłączenia LangSmith API do raportu dziennego. Problemy:
- Zły endpoint (`api.smith.langchain.com` zamiast `eu.api.smith.langchain.com` — konto EU)
- Zły Tenant ID (wzięty z ID projektu zamiast ID organizacji z URL `/o/`)
- Po rozwiązaniu — projekt ma zbyt mało ruchu żeby raport miał sens (2 runy tygodniowo)
- **Decyzja Konrada:** Porzucono LangSmith raport na tym etapie — wróci gdy projekt będzie miał realnych użytkowników

### Google OAuth2 — niemożliwe na VPS z IP
Google OAuth2 wymaga domeny w redirect URI — nie akceptuje surowego IP. Obejście: Service Account z udostępnieniem folderu Drive. Nowy Service Account stworzony w projekcie Google Cloud `n8n-drive` z włączonym Google Drive API.

### Python na VPS
- pip nie był zainstalowany — `apt install python3-pip`
- `--break-system-packages` nie działał na Ubuntu 24.04 — rozwiązano przez virtual environment (`/root/venv`)
- Zależności: `openai`, `supabase`, `python-dotenv`
- Problem z polskimi znakami w nazwach plików przy SCP — rozwiązanie: zmiana nazwy przed kopiowaniem

---

## Stack techniczny automatyzacji

- **n8n** self-hosted na VPS (Ubuntu 24.04, Docker)
- **Supabase REST API** — zapytania przez HTTP Request node z service role key
- **Google Drive API** — Service Account (nie OAuth2 — ograniczenie Google dla VPS bez domeny)
- **SSH** — password auth do VPS
- **Gmail/SMTP** — wysyłka emaili
- **Python venv** na VPS — środowisko dla skryptu ingest
- **flock** — zabezpieczenie przed równoległym uruchomieniem skryptu

---

## Do CV — co powiedzieć na rozmowie

**Zbudowałem 5 automatyzacji n8n dla własnego projektu AI:**

1. **Monitoring backendu** — health check co 5 min, email alert gdy pada
2. **Alert nowego użytkownika** — polling Supabase Auth API co 5 min, filtrowanie w JavaScript
3. **Monitoring konfliktów** — cron + Supabase query, codzienny email z listą
4. **Dzienny raport z analizą AI** — dwa źródła danych, merge, statystyki w JS, komentarz LLM, HTML email z tabelką porównawczą
5. **Automatyczny pipeline ingestion dokumentów** — Google Drive → SSH → Python script → email z potwierdzeniem

**Decyzje które podjąłem samodzielnie:**
- Polling zamiast webhooków tam gdzie webhooki były zawodne (niezawodność > real-time)
- flock zamiast kolejkowania (prostota > over-engineering)
- Jeden plik na raz jako świadome ograniczenie (wystarczające dla obecnej skali)
- Porzucenie LangSmith raportu gdy okazał się bezużyteczny przy braku ruchu
- Service Account zamiast OAuth2 (ograniczenie Google, nie błąd projektowy)
- VPS self-hosted zamiast n8n Cloud (kontrola kosztów + doświadczenie DevOps)
