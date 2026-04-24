# ADR — Tydzień 8: Landing Page, Optymalizacja Wydajności, Reskin UI

> Dokument decyzji architektonicznych dla Tygodnia 8 projektu BEZ PIERDOLENIA — AI Trener Personalny.
> Opisuje co zostało zbudowane, jakie decyzje podjęto, jakie błędy popełniono i czego się nauczyliśmy.

---

## Co zrobiliśmy

### 1. Landing Page (`/`)

Stara strona główna była formularzem logowania. Dziś zamieniliśmy ją w pełną stronę sprzedażową (landing page) aplikacji.

**Sekcje landing page:**
- Hero z animowanym oknem czatu (Pitbul odpowiada na przykładowe pytania)
- Problem (co nie działa bez planu)
- Jak to działa (3 kroki)
- Dowód — przykładowe rozmowy z Pitbulem
- Opinie użytkowników (Kuba 18 lat, Justyna 23, Dawid 21)
- Porównanie z trenerem personalnym
- Obiekcje (akordeon z pytaniami i odpowiedziami)
- Cennik (19 zł tydzień / 69 zł miesiąc / 189 zł 3 miesiące)
- Darmowy ebook jako lead magnet
- Końcowe CTA

**Login przeniesiony na `/login`** — stara strona logowania dostała własny URL, landing page zajął główny adres.

---

### 2. Optymalizacja Wydajności

Lighthouse pokazał wynik **83/100** na starcie. Po zmianach: **93/100**.

**Co naprawiliśmy:**

| Problem | Fix |
|---|---|
| Cały `page.tsx` był client component | Wyciągnięto `AnimatedChatWindow` i `Accordion` do osobnych plików z `'use client'` — reszta strony renderuje się na serwerze |
| Wentylator komputera kręcił się od razu po wejściu | `IntersectionObserver` — animacje czatu pauzują kiedy nie są widoczne na ekranie |
| CSS blokował ładowanie strony | `optimizeCss: true` w konfiguracji + instalacja pakietu `critters` |
| Niepotrzebne polyfille JS (~14 KB) | `browserslist` — budujemy tylko dla nowoczesnych przeglądarek |
| Brak `<main>` — accessibility | Dodano `<main>` wrapper wokół treści |
| Zbyt niski kontrast tekstu | `zinc-600` → `zinc-400` w kilku miejscach |

**Pliki zmienione:**
- `frontend/src/app/page.tsx` — usunięto `'use client'`, importuje nowe komponenty
- `frontend/src/app/components/AnimatedChatWindow.tsx` — **nowy plik**
- `frontend/src/app/components/Accordion.tsx` — **nowy plik**
- `frontend/src/app/globals.css` — dodano animację `wave`
- `frontend/package.json` — `browserslist`, `critters`
- `frontend/next.config.ts` — `optimizeCss: true`

---

### 3. Reskin UI — Neon Green Theme

Cały interfejs aplikacji (chat, plan, ustawienia, logowanie) dostał nowy wygląd spójny z landing page.

**Zmiany wizualne:**

**Chat:**
- Header: zamiast "BEZ PIERDOLENIA / z Pitbulem" → zielone kółko "P" + "Pitbul ● online 24/7"
- Wiadomości Pitbula: zielone tło (`#00FF88`) zamiast szarego
- Wskaźnik myślenia: trzy skaczące zielone kropki + tekst z animacją falową (literka po literce)
- Przycisk "Wyślij": zielony
- Input: zielona ramka przy focus

**Plan i Ustawienia:**
- Ten sam header co chat (Pitbul + online 24/7)
- Aktywna zakładka nawigacji: zielona zamiast białej
- Nagłówki sekcji w ustawieniach: zielone
- Przyciski akcji: zielone
- Dodano przycisk "Wyloguj" do strony Plan (brakowało)

**Logowanie:**
- Duże zielone kółko "P" z efektem poświaty zamiast napisu "BEZ PIERDOLENIA"
- Napis: "PITBUL" + "Twój trener AI" zamiast "AI trener personalny"
- Checkbox GDPR: zielony
- Link powrotu na stronę główną

**Pliki zmienione:**
- `frontend/src/app/chat/page.tsx`
- `frontend/src/app/plan/page.tsx`
- `frontend/src/app/settings/page.tsx`
- `frontend/src/app/login/page.tsx`
- `frontend/src/app/globals.css`

---

### 4. Naprawa Promptu Pitbula

Podczas testów znaleźliśmy trzy poważne błędy w zachowaniu Pitbula:

**Błąd 1: Pisał w pierwszej osobie jako autor ebooka**
Pitbul powiedział "trenuję 5.5 roku na siłowni" — to było zdanie z ebooka napisane przez autora, ale Pitbul powtórzył je jakby mówił o sobie.

**Błąd 2: Listował źródła wiedzy zamiast odpowiadać na pytanie**
Gdy zapytano "skąd bierzesz info?", Pitbul wymienił swoje źródła. Gdy zapytano ponownie — wymienił dokładnie to samo zamiast zareagować na kontekst.

**Błąd 3: Nie wiedział że ma 7 źródeł**
W opisie narzędzia RAG stało "baza wiedzy z ebooka" — ale w bazie było już 1374 chunków z 7 różnych źródeł. Pitbul myślał że ma tylko ebook.

**Co naprawiono:**
- Opis narzędzia RAG zmieniony z "ebooka treningowego" na "wiele źródeł"
- Dodana instrukcja: nie cytuj tekstów z bazy w pierwszej osobie
- Dodana instrukcja: reaguj na wątpliwości zamiast powtarzać odpowiedź
- **Usunięto** sekcję ze skryptowaną odpowiedzią "skąd bierzesz info" — to był błąd, przewidywanie konkretnych pytań i dawanie gotowych odpowiedzi prowadzi do sztywnego, powtarzalnego zachowania

**Plik zmieniony:**
- `backend/agents/graph.py` — sekcja `PITBUL_STATIC_PROMPT`

---

### 5. Deployment

Projekt wdrażany jest przez **Railway** — nie Vercel. Railway automatycznie wykrywa push na branch `main` i wdraża obie usługi (frontend Next.js + backend FastAPI).

Flow:
```
git push origin main → GitHub → Railway auto-deploy
```

---

## Decyzje Podjęte Dzisiaj

| Decyzja | Dlaczego |
|---|---|
| Landing page w tej samej aplikacji Next.js (nie osobna strona) | Prostsze utrzymanie, jedno wdrożenie, ten sam backend |
| AnimatedChatWindow i Accordion jako osobne pliki client-side | Tylko one potrzebują JavaScriptu — reszta strony może być statyczna |
| IntersectionObserver zamiast zawsze-aktywnych animacji | 3 animacje naraz powodowały duże zużycie CPU (wentylator) |
| Zielone tło wiadomości Pitbula (jak w przykładach na LP) | Spójność z landing page, wyraźna identyfikacja kto mówi |
| Usunięcie skryptowanych odpowiedzi z promptu | Przewidywanie każdego pytania z góry nie działa — model musi myśleć samodzielnie |
| Nie naprawiamy polyfilli Next.js (~14 KB) | Są hardcodowane w Next.js, usunięcie wymagałoby niebezpiecznych hacków — nie warto |

---

## Błędy Które Popełniliśmy

**Błąd 1: Dodałem sekcję "SKĄD BIERZESZ INFORMACJE" do promptu**
Kiedy Pitbul niepoprawnie odpowiedział na pytanie o źródła, dodałem gotową, skryptowaną odpowiedź do promptu. To był zły kierunek — Pitbul zaczął cytować tę sekcję dosłownie, z błędem ("3 źródła" ale wymienił 4), i nadal powtarzał to samo gdy pytano drugi raz. Sekcja została usunięta.

**Wniosek:** Nie skryptuj odpowiedzi na konkretne pytania. Dawaj modelowi zasady myślenia, nie gotowe odpowiedzi.

---

## Co Tu Się Zadziało — Prosto

Zrobiliśmy dziś trzy duże rzeczy:

**Po pierwsze** — stworzyliśmy stronę sprzedażową aplikacji. Wcześniej jak ktoś wchodził na adres strony, od razu widział formularz logowania. Teraz widzi profesjonalną stronę która tłumaczy co to za produkt, ile kosztuje, co dostaje i dlaczego warto. Dopiero jak kliknie "zacznij" — trafia do logowania.

**Po drugie** — przeprojektowaliśmy wygląd całej aplikacji. Zdecydowałeś że Pitbul powinien wyglądać i zachowywać się spójnie — tak jak go widzisz na stronie sprzedażowej, tak samo ma wyglądać w samej aplikacji. Zielone kolory, animowane wskaźniki pisania, awatar "P", napis "Pitbul — online 24/7". Zamiast neutralnego, schludnego interfejsu — charakter marki w każdym elemencie.

**Po trzecie** — próbowaliśmy naprawić zachowanie Pitbula. Okazało się że czerpał informacje z tekstów pisanych przez autora ebooka i powtarzał je jako swoje własne doświadczenia. Zdecydowałeś też że nie chcesz dawać mu z góry napisanych odpowiedzi na konkretne pytania — chcesz żeby myślał samodzielnie zamiast czytać ze ściągi. To ważna decyzja projektowa: mniej skryptowania, więcej zaufania do modelu AI.

---

## Następne Kroki

- Głębszy refactor promptu Pitbula — krótszy, mniej prescriptive, więcej swobody
- Integracja Stripe — płatności
- Testowanie zachowania Pitbula z 7 źródłami w bazie wiedzy
