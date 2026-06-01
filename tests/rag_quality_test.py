#!/usr/bin/env python3
"""
Testy jakości RAG — BEZ PIERDOLENIA backend
============================================

Sprawdza 4 wymiary jakości odpowiedzi systemu RAG:

  R1-R5  Grounding    — Czy agent podaje konkretne fakty z bazy wiedzy (nie halucynuje)?
  O1-O3  Off-topic    — Czy agent odmawia pytań poza zakresem zamiast zmyślać?
  C1     Consistency  — Czy to samo pytanie zadane 2x daje spójne odpowiedzi?
  T1-T3  Relevance    — Czy odpowiedź faktycznie odpowiada na pytanie?

Każdą odpowiedź ocenia Claude Haiku jako LLM-as-judge (skala 0-10 per kryterium).
Na końcu: raport z wynikami + diagnoza gdzie RAG działa dobrze a gdzie się sypie.

Wymagania:
    pip install aiohttp anthropic

Konfiguracja (zmienne środowiskowe lub .env w katalogu głównym projektu):
    BASE_URL          — adres backendu (domyślnie: http://localhost:8000)
    TEST_TOKEN        — JWT aktywnego usera z aktywną subskrypcją (WYMAGANY)
    ANTHROPIC_API_KEY — klucz Anthropic dla LLM-as-judge (czytany z .env)

Uruchomienie:
    cd tests
    python rag_quality_test.py

    # Z tokenem podanym jako zmienna środowiskowa:
    TEST_TOKEN=eyJ... python rag_quality_test.py

    # Na produkcji:
    BASE_URL=https://bezp-rag-agent-production.up.railway.app TEST_TOKEN=eyJ... python rag_quality_test.py
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import aiohttp
except ImportError:
    print("BLAD: Wymagany pakiet aiohttp.\nZainstaluj: pip install aiohttp")
    sys.exit(1)

try:
    import anthropic as anthropic_sdk
except ImportError:
    print("BLAD: Wymagany pakiet anthropic.\nZainstaluj: pip install anthropic")
    sys.exit(1)

# ─── Wczytaj .env z katalogu glownego projektu ──────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

BASE_URL          = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
TEST_TOKEN        = os.getenv("TEST_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Kolory ANSI ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg):      print(f"  {GREEN}+{RESET}  {msg}")
def warn(msg):    print(f"  {YELLOW}!{RESET}  {msg}")
def err(msg):     print(f"  {RED}x{RESET}  {msg}")
def info(msg):    print(f"  {CYAN}>{RESET}  {msg}")
def dim(msg):     print(f"     {DIM}{msg}{RESET}")
def section(msg): print(f"\n{BOLD}{BLUE}{msg}{RESET}")


# ─── Struktura wyniku ─────────────────────────────────────────────────────────
@dataclass
class TestResult:
    test_id:       str
    category:      str
    question:      str
    passed:        bool  = True
    score:         float = 0.0     # 0-10, wynik od sedziego
    response:      str   = ""      # pelna odpowiedz agenta
    judge_verdict: str   = ""      # uzasadnienie sedziego
    error:         str   = ""      # blad HTTP lub inny


# ═════════════════════════════════════════════════════════════════════════════
# PRZYPADKI TESTOWE
# ═════════════════════════════════════════════════════════════════════════════

# R1-R5: Grounding — czy agent podaje konkretne fakty, nie ogolniki?
# Pytania z oczekiwanymi odpowiedziami ktore powinny byc w bazie wiedzy treningowej.
GROUNDING_TESTS = [
    {
        "id": "R1",
        "question": "Ile gramow bialka na kilogram masy ciala powinienem jesc zeby budowac miesnie?",
        "criterion": (
            "Czy odpowiedz zawiera KONKRETNA LICZBE lub zakres liczbowy (np. 1.6, 2.0, 2.2 g/kg lub '1.6-2.2 g/kg')? "
            "Score 10 = podana konkretna wartosc lub zakres z jednostka (g/kg). "
            "Score 5 = wspomniano ze 'wiecej niz normalnie' ale bez liczby. "
            "Score 0 = tylko ogolniki ('duzo bialka') bez zadnej liczby."
        ),
    },
    {
        "id": "R2",
        "question": "Co to jest RIR (Reps in Reserve) i jak z tego korzystac planujac intensywnosc treningu?",
        "criterion": (
            "Czy odpowiedz poprawnie definiuje RIR jako 'ile powtorzen zostaje w zapasie przed osiagnieciem niepowodzenia'? "
            "Czy podaje praktyczny przyklad (np. RIR 2 = mozesz zrobic jeszcze 2 powtorzenia, RIR 0 = failure)? "
            "Score 10 = precyzyjna definicja + praktyczny przyklad liczbowy. "
            "Score 5 = poprawna definicja bez przykladu. "
            "Score 0 = bledna lub brak definicji."
        ),
    },
    {
        "id": "R3",
        "question": "Ile godzin snu potrzebuje osoba trenujaca silowo do pelnej regeneracji?",
        "criterion": (
            "Czy odpowiedz zawiera KONKRETNA LICZBE godzin snu (np. 7-9h, minimum 7h, 8h)? "
            "Czy wyjasnia DLACZEGO sen jest kluczowy dla regeneracji (hormony, GH, synteza bialek)? "
            "Score 10 = konkretna liczba godzin + mechanizm biologiczny. "
            "Score 5 = konkretna liczba bez wyjasnienia. "
            "Score 0 = tylko 'duzo snu' bez zadnej wartosci."
        ),
    },
    {
        "id": "R4",
        "question": "Czym jest periodyzacja treningu i dlaczego jest wazna? Wyjasni jak to dziala w praktyce.",
        "criterion": (
            "Czy odpowiedz wyjasnia periodyzacje jako SYSTEMATYCZNE planowanie zmian objetosci/intensywnosci w czasie? "
            "Czy wymienia struktury czasowe (np. mikrocykl/mezocykl/makrocykl) LUB rodzaje periodyzacji (liniowa, falowa, blokowa)? "
            "Score 10 = pelne wyjasnienie z konkretnymi strukturami czasowymi lub typami. "
            "Score 5 = poprawna idea ale bez konkretnych terminow. "
            "Score 0 = ogolnikowe lub bledne wyjasnienie."
        ),
    },
    {
        "id": "R5",
        "question": "Jak czesto w tygodniu powinienem trenowac ta sama grupe miesniowa zeby maksymalnie stymulowac hipertrofie?",
        "criterion": (
            "Czy odpowiedz zawiera KONKRETNA CZESTOTLIWOSC treningow na grupe miesniowa (np. 2x/tydzien, 2-3x/tydzien)? "
            "Czy odnosi sie do regeneracji, okna superkompensacji lub badan naukowych? "
            "Score 10 = konkretna liczba dni/tydzien + wyjasnienie mechanizmu. "
            "Score 5 = konkretna liczba bez wyjasnienia. "
            "Score 0 = brak konkretnej odpowiedzi na pytanie o czestotliwosc."
        ),
    },
]

# O1-O3: Off-topic — czy agent odmawia pytan poza zakresem?
OFFTOPIC_TESTS = [
    {
        "id": "O1",
        "question": "Jak naprawic cieknacy kran w lazience?",
        "criterion": (
            "Czy odpowiedz ODMAWIA pomocy w temacie hydrauliki domowej? "
            "Czy NIE zawiera zadnych porad technicznych dotyczacych kranu/hydrauliki? "
            "Czy przekierowuje na temat fitnessu/treningu? "
            "Score 10 = jasna odmowa BEZ porad hydraulicznych + przekierowanie na trening. "
            "Score 5 = odmowa, ale bez przekierowania na trening. "
            "Score 0 = udziela porad hydraulicznych (NIEDOPUSZCZALNE — agent jest trenerem, nie hydraulikiem)."
        ),
    },
    {
        "id": "O2",
        "question": "Napisz mi wiersz o jesieni i przemijaniu",
        "criterion": (
            "Czy odpowiedz ODMAWIA napisania wiersza i pozostaje w temacie treningu? "
            "Score 10 = brak wiersza, humorystyczna odmowa z powrotem do treningu. "
            "Score 7 = odmowa bez humoru, ale bez wiersza. "
            "Score 0 = napisala wiersz (NIEDOPUSZCZALNE — agent powinien odmawiac tematow poza zakresem)."
        ),
    },
    {
        "id": "O3",
        "question": "W co najlepiej zainwestowac 50 000 zlotych — akcje, kryptowaluty czy obligacje?",
        "criterion": (
            "Czy odpowiedz ODMAWIA udzielenia porad finansowych/inwestycyjnych? "
            "Czy NIE zawiera zadnych konkretnych rekomendacji inwestycyjnych? "
            "Czy przekierowuje na temat zdrowia/treningu? "
            "Score 10 = jasna odmowa BEZ porad finansowych + przekierowanie. "
            "Score 5 = odmowa bez redirectu. "
            "Score 0 = podaje porady inwestycyjne (NIEDOPUSZCZALNE)."
        ),
    },
]

# C1: Consistency — to samo pytanie zadane dwa razy w tej samej sesji.
# Sprawdzamy czy FAKTY sa spojne (liczby, zakresy), nie czy slowa sa identyczne.
CONSISTENCY_QUESTION = "Ile bialka dziennie powinienem jesc przy budowaniu masy miesniowej?"

# T1-T3: Relevance — czy odpowiedz faktycznie odpowiada na pytanie?
RELEVANCE_TESTS = [
    {
        "id": "T1",
        "question": "Mam bol kolana podczas przysiadu — co moge zrobic zeby trenowac bez bolu?",
        "criterion": (
            "Czy odpowiedz:\n"
            "1. Odnosi sie KONKRETNIE do bolu kolana podczas przysiadu (nie ogolnie do 'kontuzji')?\n"
            "2. Sugeruje KONKRETNE alternatywy cwiczeniowe (np. leg press, hack squat, rozne odmiany przysiadu) "
            "LUB konkretne modyfikacje techniki (szer. rozstawu, glebokosci)?\n"
            "3. Zaleca konsultacje z fizjoterapeutam lub lekarzem (wymog bezpieczenstwa)?\n"
            "Score 10 = spelnia wszystkie 3 kryteria. "
            "Score 7 = spelnia 2 z 3. "
            "Score 3 = tylko ogolniki. "
            "Score 0 = nie odpowiada na pytanie."
        ),
    },
    {
        "id": "T2",
        "question": "Jestem zupelnym poczatkujacym, nigdy nie trenovatem silowo. Od czego zaczac?",
        "criterion": (
            "Czy odpowiedz daje KONKRETNY punkt startowy dla absolutnego poczatkujacego? "
            "Konkretny = zawiera przynajmniej JEDNO z: "
            "nazwy podstawowych cwiczen (przysiad, martwy ciag, wyciskanie, pompki), "
            "sugerowana czestotliwosc (np. 3x/tydzien), "
            "typ programu (full body zamiast splitu), "
            "rekomendacje zacznij od mniejszych ciezarow. "
            "Score 10 = kilka konkretnych wskazowek. "
            "Score 5 = jeden konkret plus ogolniki. "
            "Score 0 = tylko ogolne 'idz na silownie i cwicz'."
        ),
    },
    {
        "id": "T3",
        "question": "Jak dlugo powinienem odpoczywac miedzy seriami gdy trenuje na sile (nie na mase)?",
        "criterion": (
            "Czy odpowiedz podaje KONKRETNY CZAS odpoczynku miedzy seriami podczas treningu silowego? "
            "Oczekiwana odpowiedz: zakres 2-5 minut (lub zblizone) dla treningu na sile. "
            "Czy ODROZNIA trening na sile (dluzsze przerwy) od hipertrofii (krotsze)? "
            "Score 10 = konkretny zakres czasowy + wyjasnienie roznych przerw dla sily vs masy. "
            "Score 5 = konkretny zakres bez rozroznienia. "
            "Score 0 = ogolne 'odpoczywaj wystarczajaco' bez zadnych liczb."
        ),
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# SSE READER — odbiera pelna odpowiedz agenta ze streamu
# ═════════════════════════════════════════════════════════════════════════════

async def send_chat_and_read(
    session: aiohttp.ClientSession,
    message: str,
    token: str,
) -> tuple[int, str]:
    """
    Wysyla POST /chat/ i zbiera pelna odpowiedz z SSE streamu.
    Zwraca (status_http, tresc_odpowiedzi).

    Format SSE z backendu (chat.py):
        : keepalive             — co 20s podczas generowania, ignoruj
        data: {"token": "..."}  — pelna odpowiedz agenta (jedna paczka na koniec)
        data: {"done": true}    — koniec streamu
        data: {"error": "..."}  — blad agenta
    """
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"message": message}

    try:
        async with session.post(
            f"{BASE_URL}/chat/",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                return resp.status, body[:500]

            full_response = ""
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line or line.startswith(":"):
                    continue  # keepalive lub pusta linia SSE
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if "token" in data:
                            full_response = data["token"]
                        if data.get("done"):
                            break
                        if "error" in data:
                            return 500, data["error"]
                    except json.JSONDecodeError:
                        pass

            return 200, full_response

    except asyncio.TimeoutError:
        return 0, "TIMEOUT — agent nie odpowiedzial w 120s"
    except Exception as e:
        return 0, f"BLAD POLACZENIA: {e}"


# ═════════════════════════════════════════════════════════════════════════════
# LLM-AS-JUDGE — Claude Haiku ocenia kazda odpowiedz
# ═════════════════════════════════════════════════════════════════════════════

def judge_response(
    question: str,
    answer: str,
    criterion: str,
    judge_client: anthropic_sdk.Anthropic,
) -> tuple[float, str]:
    """
    Haiku ocenia odpowiedz agenta wedlug podanego kryterium.
    Zwraca (score 0-10, uzasadnienie po polsku).
    Prog PASS: score >= 7.
    """
    prompt = f"""Jestes ewaluatorem jakosci odpowiedzi systemu AI trenera personalnego.

PYTANIE ZADANE SYSTEMOWI:
{question}

ODPOWIEDZ SYSTEMU:
{answer}

KRYTERIUM OCENY:
{criterion}

Odpowiedz WYLACZNIE w formacie JSON (zero tekstu poza JSON):
{{"score": <liczba calkowita 0-10>, "reasoning": "<1-2 zdania po polsku, co konkretnie zadecydowalo o ocenie>", "passed": <true jesli score>=7, false jesli <7>}}"""

    try:
        resp = judge_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Haiku czasem owija JSON w backticki — usun je
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        return float(data.get("score", 0)), data.get("reasoning", "brak uzasadnienia")
    except Exception as e:
        return 0.0, f"Blad sedziego: {e}"


def judge_consistency(
    question: str,
    answer1: str,
    answer2: str,
    judge_client: anthropic_sdk.Anthropic,
) -> tuple[float, str]:
    """
    Haiku ocenia czy dwie odpowiedzi na to samo pytanie sa faktycznie spojne.
    Ocenia spojnosc FAKTOW (liczby, zakresy) — nie identycznosc slow.
    """
    prompt = f"""Jestes ewaluatorem spojnosci odpowiedzi systemu AI.

PYTANIE:
{question}

ODPOWIEDZ 1:
{answer1}

ODPOWIEDZ 2:
{answer2}

Oce czy obie odpowiedzi sa FAKTYCZNIE SPOJNE — czy podaja te same liczby, zakresy wartosci i zalecenia, nawet jesli uzyte sa inne slowa.
Skala:
10 = identyczne fakty i liczby w obu odpowiedziach
7  = zblizone fakty, lekko inne sformulowanie, brak sprzecznosci
4  = rozne podejscie lub inne liczby (np. jedna mowi 1.6 g/kg, druga mowi 3 g/kg)
0  = sprzeczne informacje

Odpowiedz WYLACZNIE w formacie JSON:
{{"score": <liczba calkowita 0-10>, "reasoning": "<1-2 zdania po polsku>", "passed": <true jesli score>=7>}}"""

    try:
        resp = judge_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        return float(data.get("score", 0)), data.get("reasoning", "brak uzasadnienia")
    except Exception as e:
        return 0.0, f"Blad sedziego: {e}"


# ═════════════════════════════════════════════════════════════════════════════
# RUNNER
# ═════════════════════════════════════════════════════════════════════════════

async def run_all_tests() -> list[TestResult]:
    if not TEST_TOKEN:
        print(f"\n{RED}BLAD: TEST_TOKEN nie ustawiony.{RESET}")
        print("Zaloguj sie przez localhost, skopiuj JWT i uruchom:")
        print("  TEST_TOKEN=eyJ... python rag_quality_test.py")
        sys.exit(1)

    if not ANTHROPIC_API_KEY:
        print(f"\n{RED}BLAD: ANTHROPIC_API_KEY nie znaleziony.{RESET}")
        print("Sprawdz czy klucz jest w .env (w katalogu glownym projektu)")
        sys.exit(1)

    judge = anthropic_sdk.Anthropic(api_key=ANTHROPIC_API_KEY)
    results: list[TestResult] = []

    conn = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=conn) as session:

        # ── Sprawdz czy backend zyje ──────────────────────────────────────────
        section("[ Sprawdzam polaczenie z backendem ]")
        try:
            async with session.get(
                f"{BASE_URL}/health",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status == 200:
                    ok(f"Backend dziala: {BASE_URL}")
                else:
                    err(f"Backend zwrocil {r.status} na /health — przerywam")
                    sys.exit(1)
        except Exception as e:
            err(f"Nie moge polaczyc sie z backendem: {e}")
            err("Sprawdz czy backend jest uruchomiony (uvicorn main:app --reload)")
            sys.exit(1)

        # ── R1-R5: Grounding ──────────────────────────────────────────────────
        section("[ R1-R5: Grounding — czy agent podaje konkretne fakty z bazy wiedzy? ]")
        print(f"  {DIM}Ocena: konkretne liczby/mechanizmy > ogolniki. Prog PASS: score >= 7/10{RESET}\n")

        for tc in GROUNDING_TESTS:
            test_id   = tc["id"]
            question  = tc["question"]
            criterion = tc["criterion"]

            info(f"{test_id}: {question[:75]}...")
            t0 = time.perf_counter()
            status, response = await send_chat_and_read(session, question, TEST_TOKEN)
            elapsed = (time.perf_counter() - t0) * 1000

            result = TestResult(test_id=test_id, category="Grounding", question=question)

            if status != 200:
                result.passed = False
                result.error  = f"HTTP {status}: {response[:200]}"
                err(f"  {test_id} FAIL (HTTP {status}): {response[:80]}")
                results.append(result)
                await asyncio.sleep(2)
                continue

            result.response = response
            dim(f"Agent ({elapsed:.0f}ms): {response[:130]}...")

            score, reasoning = judge_response(question, response, criterion, judge)
            result.score         = score
            result.judge_verdict = reasoning
            result.passed        = score >= 7

            color = GREEN if result.passed else RED
            icon  = "+" if result.passed else "x"
            print(f"  {color}{icon}{RESET}  {test_id}  score={score:.0f}/10 — {reasoning}")

            results.append(result)
            await asyncio.sleep(2)

        # ── O1-O3: Off-topic ──────────────────────────────────────────────────
        section("[ O1-O3: Off-topic — czy agent odmawia pytan poza zakresem? ]")
        print(f"  {DIM}Ocena: jasna odmowa + redirect na trening > udzielenie odpowiedzi off-topic{RESET}\n")

        for tc in OFFTOPIC_TESTS:
            test_id   = tc["id"]
            question  = tc["question"]
            criterion = tc["criterion"]

            info(f"{test_id}: {question[:75]}")
            t0 = time.perf_counter()
            status, response = await send_chat_and_read(session, question, TEST_TOKEN)
            elapsed = (time.perf_counter() - t0) * 1000

            result = TestResult(test_id=test_id, category="Off-topic", question=question)

            if status != 200:
                result.passed = False
                result.error  = f"HTTP {status}: {response[:200]}"
                err(f"  {test_id} FAIL (HTTP {status}): {response[:80]}")
                results.append(result)
                await asyncio.sleep(2)
                continue

            result.response = response
            dim(f"Agent ({elapsed:.0f}ms): {response[:130]}...")

            score, reasoning = judge_response(question, response, criterion, judge)
            result.score         = score
            result.judge_verdict = reasoning
            result.passed        = score >= 7

            color = GREEN if result.passed else RED
            icon  = "+" if result.passed else "x"
            print(f"  {color}{icon}{RESET}  {test_id}  score={score:.0f}/10 — {reasoning}")

            results.append(result)
            await asyncio.sleep(2)

        # ── C1: Consistency ───────────────────────────────────────────────────
        section("[ C1: Consistency — to samo pytanie 2x, czy fakty sa spojne? ]")
        print(f"  {DIM}Pytanie: {CONSISTENCY_QUESTION}{RESET}\n")

        info("C1 (zapytanie 1/2)...")
        status1, resp1 = await send_chat_and_read(session, CONSISTENCY_QUESTION, TEST_TOKEN)
        await asyncio.sleep(3)

        info("C1 (zapytanie 2/2)...")
        status2, resp2 = await send_chat_and_read(session, CONSISTENCY_QUESTION, TEST_TOKEN)

        c1 = TestResult(test_id="C1", category="Consistency", question=CONSISTENCY_QUESTION)
        if status1 != 200 or status2 != 200:
            c1.passed = False
            c1.error  = f"HTTP {status1}/{status2}"
            err(f"  C1 FAIL: blad polaczenia HTTP {status1}/{status2}")
        else:
            dim(f"Odp 1: {resp1[:110]}...")
            dim(f"Odp 2: {resp2[:110]}...")
            score, reasoning = judge_consistency(CONSISTENCY_QUESTION, resp1, resp2, judge)
            c1.score         = score
            c1.judge_verdict = reasoning
            c1.passed        = score >= 7
            c1.response      = f"[1]: {resp1[:120]}\n[2]: {resp2[:120]}"
            color = GREEN if c1.passed else RED
            icon  = "+" if c1.passed else "x"
            print(f"  {color}{icon}{RESET}  C1  score={score:.0f}/10 — {reasoning}")

        results.append(c1)
        await asyncio.sleep(2)

        # ── T1-T3: Relevance ──────────────────────────────────────────────────
        section("[ T1-T3: Relevance — czy odpowiedz faktycznie odpowiada na pytanie? ]")
        print(f"  {DIM}Ocena: konkretna i trafna odpowiedz > ogolnikowa lub off-topic{RESET}\n")

        for tc in RELEVANCE_TESTS:
            test_id   = tc["id"]
            question  = tc["question"]
            criterion = tc["criterion"]

            info(f"{test_id}: {question[:75]}")
            t0 = time.perf_counter()
            status, response = await send_chat_and_read(session, question, TEST_TOKEN)
            elapsed = (time.perf_counter() - t0) * 1000

            result = TestResult(test_id=test_id, category="Relevance", question=question)

            if status != 200:
                result.passed = False
                result.error  = f"HTTP {status}: {response[:200]}"
                err(f"  {test_id} FAIL (HTTP {status}): {response[:80]}")
                results.append(result)
                await asyncio.sleep(2)
                continue

            result.response = response
            dim(f"Agent ({elapsed:.0f}ms): {response[:130]}...")

            score, reasoning = judge_response(question, response, criterion, judge)
            result.score         = score
            result.judge_verdict = reasoning
            result.passed        = score >= 7

            color = GREEN if result.passed else RED
            icon  = "+" if result.passed else "x"
            print(f"  {color}{icon}{RESET}  {test_id}  score={score:.0f}/10 — {reasoning}")

            results.append(result)
            await asyncio.sleep(2)

    return results


# ═════════════════════════════════════════════════════════════════════════════
# RAPORT KONCOWY
# ═════════════════════════════════════════════════════════════════════════════

def print_report(results: list[TestResult]) -> None:
    section("=" * 62)
    section("  RAPORT JAKOSCI RAG — BEZ PIERDOLENIA")
    section("=" * 62)

    # Grupuj wyniki per kategoria
    categories: dict[str, list[TestResult]] = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    all_passed = 0
    all_total  = 0

    for cat, cat_results in categories.items():
        ok_list    = [r for r in cat_results if r.passed and not r.error]
        fail_list  = [r for r in cat_results if not r.passed and not r.error]
        error_list = [r for r in cat_results if r.error]
        total_no_error = len(ok_list) + len(fail_list)
        scores    = [r.score for r in cat_results if not r.error]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        color = GREEN if len(ok_list) == total_no_error else (YELLOW if ok_list else RED)
        print(f"\n{BOLD}{cat}{RESET}  {color}{len(ok_list)}/{total_no_error} PASS{RESET}  avg={avg_score:.1f}/10")

        for r in cat_results:
            if r.error:
                print(f"  {RED}x{RESET}  {r.test_id}: BLAD — {r.error}")
            elif r.passed:
                print(f"  {GREEN}+{RESET}  {r.test_id}: {r.score:.0f}/10 — {r.judge_verdict}")
            else:
                print(f"  {RED}x{RESET}  {r.test_id}: {r.score:.0f}/10 — {r.judge_verdict}")

        all_passed += len(ok_list)
        all_total  += total_no_error

    # Ogolny wynik
    print(f"\n{'─'*62}")
    pct = all_passed / all_total * 100 if all_total else 0
    total_color = GREEN if pct >= 80 else (YELLOW if pct >= 60 else RED)
    print(f"{BOLD}LACZNIE: {total_color}{all_passed}/{all_total} PASS ({pct:.0f}%){RESET}")

    # Szczegoly nieudanych testow
    failed = [r for r in results if not r.passed and not r.error]
    if failed:
        print(f"\n{BOLD}{RED}Testy do poprawy:{RESET}")
        for r in failed:
            print(f"\n  {RED}x{RESET}  {r.test_id} ({r.category})  score={r.score:.0f}/10")
            print(f"     Pytanie:   {r.question[:90]}...")
            print(f"     Verdict:   {r.judge_verdict}")
            resp_preview = r.response[:250].replace("\n", " ")
            print(f"     Odpowiedz: {resp_preview}...")
    else:
        print(f"\n{GREEN}Wszystkie testy przeszly. RAG dziala poprawnie.{RESET}")

    # Interpretacja sredniej per kategoria
    print(f"\n{BOLD}Interpretacja wynikow:{RESET}")
    cat_scores: dict[str, list[float]] = {}
    for r in results:
        if not r.error:
            cat_scores.setdefault(r.category, []).append(r.score)

    for cat, scores in cat_scores.items():
        avg = sum(scores) / len(scores)
        if avg < 5:
            print(f"  {RED}!{RESET}  {cat}: KRYTYCZNE ({avg:.1f}/10) — wymaga natychmiastowej uwagi")
        elif avg < 7:
            print(f"  {YELLOW}!{RESET}  {cat}: SLABE ({avg:.1f}/10) — RAG nie dostarcza wystarczajacej jakosci")
        else:
            print(f"  {GREEN}+{RESET}  {cat}: OK ({avg:.1f}/10)")

    print()


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

async def main():
    total_chat_calls = len(GROUNDING_TESTS) + len(OFFTOPIC_TESTS) + 2 + len(RELEVANCE_TESTS)
    print(f"\n{BOLD}RAG Quality Tests — BEZ PIERDOLENIA{RESET}")
    print(f"Backend:   {BASE_URL}")
    print(f"Token:     {'[ustawiony]' if TEST_TOKEN else f'{RED}[BRAK — wymagany]{RESET}'}")
    print(f"LLM-judge: claude-haiku-4-5-20251001")
    print(f"Testy:     {len(GROUNDING_TESTS)}x Grounding + {len(OFFTOPIC_TESTS)}x Off-topic + 1x Consistency + {len(RELEVANCE_TESTS)}x Relevance")
    print(f"           = {total_chat_calls} zapytan do backendu (~{total_chat_calls * 25 // 60} min przy 25s/odpowiedz)\n")

    results = await run_all_tests()
    print_report(results)


if __name__ == "__main__":
    asyncio.run(main())
