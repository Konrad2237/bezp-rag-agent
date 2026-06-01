#!/usr/bin/env python3
"""
Stress tests — BEZ PIERDOLENIA backend
========================================

Scenariusze:
  S1  Concurrent /health          — 50 równoległych requestów, mierzy latencję
  S2  Auth login storm            — 20 concurrent błędnych loginów → czy nie ma 500?
  S3  Rate-limit race condition   — 8 /chat naraz od jednego usera → race condition check
  S4  Latency benchmark           — /health i /auth/me przy 1 / 10 / 50 concurrent
  S5  Long session drift          — seria sekwencyjnych wiad., mierzy drift latencji
  S6  SSE abrupt disconnect       — zryw połączenia w trakcie streamu → czy agent wisi?
  S7  Payload fuzzing             — złe dane → 4xx, nigdy 500
  S8  Guard DOS simulation        — 30 req bez tokenu → guard pod obciążeniem

Wymagania:
    pip install aiohttp

Konfiguracja (zmienne środowiskowe lub .env w głównym katalogu):
    BASE_URL   — adres backendu  (domyślnie: http://localhost:8000)
    TEST_TOKEN — JWT aktywnego usera z aktywną subskrypcją (S3/S5/S6 wymagają)

Uruchomienie:
    cd tests
    python stress_test.py

    # Produkcja:
    BASE_URL=https://bezp-rag-agent-production.up.railway.app python stress_test.py

    # Z tokenem (pełne testy):
    BASE_URL=http://localhost:8000 TEST_TOKEN=eyJ... python stress_test.py
"""

import asyncio
import os
import sys
import time
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

# Wymuś UTF-8 na Windows (cp1250 nie obsługuje znaków box-drawing)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import aiohttp
except ImportError:
    print("BŁĄD: Wymagany pakiet aiohttp.\nZainstaluj: pip install aiohttp")
    sys.exit(1)

# ─── Konfiguracja ──────────────────────────────────────────────────────────────
# Wczytaj .env z głównego katalogu projektu (jeśli istnieje)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

BASE_URL   = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
TEST_TOKEN = os.getenv("TEST_TOKEN", "")

# Skróć długie sesje do ~3 wiad. w szybkim trybie (bez TEST_TOKEN nie ma sensu i tak)
LONG_SESSION_MSGS = int(os.getenv("LONG_SESSION_MSGS", "5"))

# ─── Kolorki (ANSI) ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def err(msg):  print(f"  {RED}✗{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")
def dim(msg):  print(f"     {DIM}{msg}{RESET}")


# ─── Struktura wyniku ──────────────────────────────────────────────────────────
@dataclass
class Result:
    name:    str
    passed:  bool = True
    metrics: dict = field(default_factory=dict)
    issues:  list = field(default_factory=list)
    skipped: bool = False


# ─── Helpers ───────────────────────────────────────────────────────────────────
async def timed_get(
    session: aiohttp.ClientSession, url: str, **kw
) -> tuple[int, float]:
    """Zwraca (status_code, czas_ms)."""
    t0 = time.perf_counter()
    try:
        async with session.get(url, **kw) as r:
            await r.read()
            return r.status, (time.perf_counter() - t0) * 1000
    except Exception:
        return 0, (time.perf_counter() - t0) * 1000


async def timed_post(
    session: aiohttp.ClientSession, url: str, **kw
) -> tuple[int, float, bytes]:
    """Zwraca (status_code, czas_ms, body)."""
    t0 = time.perf_counter()
    try:
        async with session.post(url, **kw) as r:
            body = await r.read()
            return r.status, (time.perf_counter() - t0) * 1000, body
    except Exception as e:
        return 0, (time.perf_counter() - t0) * 1000, b""


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def pstats(ms: list[float]) -> dict:
    """Podstawowe percentyle z listy czasów."""
    if not ms:
        return {}
    s = sorted(ms)
    n = len(s)
    return {
        "min":  round(min(s)),
        "mean": round(statistics.mean(s)),
        "p50":  round(s[int(n * 0.50)]),
        "p95":  round(s[int(n * 0.95)]),
        "max":  round(max(s)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# S1 — Concurrent /health (50 jednoczesnych)
# ══════════════════════════════════════════════════════════════════════════════
async def s1_concurrent_health() -> Result:
    """
    50 równoległych GET /health.
    Mierzy latencję i sprawdza czy wszystkie odpowiedzi to 200.
    Baseline: czy serwer w ogóle daje radę pod lekkim ruchem.
    """
    N = 50
    r = Result(name="S1 — Concurrent /health (50 jednoczesnych)")

    conn = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(
        connector=conn, timeout=aiohttp.ClientTimeout(total=30)
    ) as session:
        tasks   = [timed_get(session, f"{BASE_URL}/health") for _ in range(N)]
        resps   = await asyncio.gather(*tasks)

    statuses = [x[0] for x in resps]
    times    = [x[1] for x in resps]
    ok200    = statuses.count(200)
    errors   = N - ok200
    s        = pstats(times)

    r.metrics = {"requests": N, "ok_200": ok200, "errors": errors, **s}

    if ok200 == N:
        ok(f"{ok200}/{N} × 200  |  P50={s['p50']}ms  P95={s['p95']}ms  max={s['max']}ms")
    else:
        err(f"Tylko {ok200}/{N} odpowiedzi 200 — {errors} błędów")
        r.issues.append(f"{errors} requestów zakończonych błędem przy 50 concurrent /health")
        r.passed = False

    if s.get("p95", 0) > 3000:
        warn(f"P95={s['p95']}ms — /health powinien być szybszy; możliwe że serwer się dusi")
        r.issues.append(
            "Wysoka latencja /health pod lekkim obciążeniem. "
            "Sprawdź czy jest wystarczająca liczba workerów (Railway default = 1 worker)."
        )

    return r


# ══════════════════════════════════════════════════════════════════════════════
# S2 — Auth login storm (20 concurrent, błędne dane)
# ══════════════════════════════════════════════════════════════════════════════
async def s2_auth_login_storm() -> Result:
    """
    20 równoległych POST /auth/login z błędnymi danymi.
    Oczekiwanie: wszystkie 401, zero 500.
    Sprawdza czy serwer nie crasha przy flood'zie złych loginów.
    """
    N = 20
    r = Result(name="S2 — Auth login storm (20 concurrent, złe dane)")

    payload = {"email": "stress.test.nonexistent@example.com", "password": "BadPassword999!"}

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=20)
    ) as session:
        tasks = [
            timed_post(session, f"{BASE_URL}/auth/login", json=payload)
            for _ in range(N)
        ]
        resps = await asyncio.gather(*tasks)

    statuses = [x[0] for x in resps]
    times    = [x[1] for x in resps]
    got_401  = statuses.count(401)
    got_500  = statuses.count(500)
    got_0    = statuses.count(0)
    s        = pstats(times)

    r.metrics = {
        "requests": N, "401": got_401, "500": got_500,
        "conn_errors": got_0, **s
    }

    if got_500 > 0:
        err(f"{got_500} × 500 — serwer crasha przy równoległych błędnych loginach!")
        r.issues.append(
            f"{got_500} × HTTP 500 przy storm złych loginów — "
            "prawdopodobny wyciek wyjątku z Supabase przez str(e) bez sanityzacji"
        )
        r.passed = False
    else:
        ok(f"Brak 500  |  {got_401}/{N} × 401  |  P50={s['p50']}ms  P95={s['p95']}ms")

    if got_0 > 0:
        warn(f"{got_0} błędów połączenia — serwer może być przeciążony lub niedostępny")

    if s.get("p95", 0) > 8000:
        warn(
            f"P95={s['p95']}ms przy odrzucaniu złych loginów — "
            "Supabase Auth prawdopodobnie throttluje. OK, ale warto monitorować."
        )

    return r


# ══════════════════════════════════════════════════════════════════════════════
# S3 — Rate-limit race condition (8 concurrent /chat)
# ══════════════════════════════════════════════════════════════════════════════
async def s3_rate_limit_race() -> Result:
    """
    8 równoległych requestów do /chat od jednego usera.
    Limit to 5/minutę — oczekujemy że 3+ dostaną 429.

    ZNANY POTENCJALNY BUG w kodzie:
      check_rate_limit() w chat.py jest SYNCHRONICZNĄ funkcją wywoływaną
      bezpośrednio w async endpoincie (bez run_in_threadpool).
      Przy 8 concurrent requestach wszystkie trafiają do check_rate_limit
      zanim JAKIKOLWIEK agent zdąży zapisać wiadomości do bazy.
      Efekt: wszystkie 8 mogą przejść przez limit jednocześnie (race condition).

    Test sprawdza czy ten scenariusz faktycznie zachodzi.
    """
    r = Result(name="S3 — Rate-limit race condition (8 /chat jednocześnie)")

    if not TEST_TOKEN:
        warn("TEST_TOKEN nie ustawiony — pomijam S3")
        r.skipped = True
        return r

    N = 8
    headers = auth_headers(TEST_TOKEN)
    payload = {"message": "Ile białka jeść dziennie?"}

    info(f"Wysyłam {N} requestów JEDNOCZEŚNIE (rate limit = 5/min)...")

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=120)
    ) as session:
        tasks = [
            timed_post(session, f"{BASE_URL}/chat/", json=payload, headers=headers)
            for _ in range(N)
        ]
        resps = await asyncio.gather(*tasks)

    statuses = [x[0] for x in resps]
    times    = [x[1] for x in resps]

    got_200 = statuses.count(200)
    got_429 = statuses.count(429)
    got_403 = statuses.count(403)
    got_500 = statuses.count(500)
    got_0   = statuses.count(0)

    r.metrics = {
        "requests": N,
        "200_ok": got_200,
        "429_rate_limited": got_429,
        "403_no_sub": got_403,
        "500_error": got_500,
        "conn_errors": got_0,
        **pstats(times),
    }

    if got_500 > 0:
        err(f"{got_500} × 500 pod burst obciążeniem /chat!")
        r.issues.append(
            f"{got_500} × HTTP 500 przy 8 concurrent /chat — "
            "możliwy deadlock, wyczerpanie wątków lub niezabezpieczony wyjątek"
        )
        r.passed = False

    elif got_403 >= N:
        warn(f"Wszystkie {N} = 403 (brak subskrypcji) — TEST_TOKEN bez aktywnej sub")
        r.issues.append("Nie można przetestować race condition — token bez aktywnej subskrypcji")

    elif got_200 >= 6:
        # Więcej niż 5 przeszło — to jest race condition
        warn(
            f"RACE CONDITION POTWIERDZONY: {got_200}/8 requestów przeszło przez rate limit "
            f"(oczekiwano max 5). Wszystkie trafiły do check_rate_limit przed zapisaniem wiad. w DB."
        )
        r.issues.append(
            f"RACE CONDITION w rate limiterze: {got_200} requestów przeszło jednocześnie "
            f"mimo limitu 5/min. Przyczyna: check_rate_limit() jest wywołana synchronicznie "
            f"w async endpoincie — odczytuje stan DB ZANIM jakikolwiek agent zdąży zapisać "
            f"wiadomości. Fix: przenieść sprawdzanie do momentu PO zapisie lub użyć "
            f"atomowej operacji (Redis counter z TTL, lub INSERT z on-conflict zamiast SELECT)."
        )
        # Nie failujemy testu — to dokumentujemy, nie crasha
        r.passed = True  # system nie crashuje, ale ma race condition

    elif got_429 >= 3:
        ok(f"Rate limiter aktywny: {got_200} × 200  +  {got_429} × 429")

    else:
        ok(f"Wyniki: {got_200}×200  {got_429}×429  {got_403}×403  {got_500}×500")

    return r


# ══════════════════════════════════════════════════════════════════════════════
# S4 — Latency benchmark: /health i /auth/me przy 1/10/50 users
# ══════════════════════════════════════════════════════════════════════════════
async def s4_latency_benchmark() -> Result:
    """
    Mierzy jak latencja zmienia się przy skalowaniu concurrent userów.
    /health  = brak DB, czysty FastAPI overhead
    /auth/me = 1× Supabase Auth + 1× DB query (synchroniczne — blokują event loop)

    Spodziewany problem:
      middleware.py wywołuje supabase.auth.get_user() i supabase_admin.table().execute()
      SYNCHRONICZNIE w async dependency — blokuje event loop.
      Przy 20 concurrent /auth/me widać to jako drastyczny wzrost P95.
    """
    r = Result(name="S4 — Latency benchmark: /health i /auth/me @ 1/10/50 concurrent")

    async def batch_get(n: int, url: str, headers: dict = None) -> list[float]:
        conn = aiohttp.TCPConnector(limit=100)
        async with aiohttp.ClientSession(
            connector=conn, timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            kw = {"headers": headers} if headers else {}
            resps = await asyncio.gather(*[timed_get(session, url, **kw) for _ in range(n)])
        return [x[1] for x in resps if x[0] == 200]

    # /health benchmark
    print()
    for n in [1, 10, 50]:
        times = await batch_get(n, f"{BASE_URL}/health")
        s = pstats(times)
        ok_n = len(times)
        info(f"/health  × {n:2d}:  {ok_n}/{n} OK  |  P50={s.get('p50','?')}ms  P95={s.get('p95','?')}ms  max={s.get('max','?')}ms")
        r.metrics[f"health_{n}"] = s
        await asyncio.sleep(0.5)

    # /auth/me benchmark (wymaga tokenu)
    if TEST_TOKEN:
        headers = auth_headers(TEST_TOKEN)
        print()
        prev_p95 = 0
        for n in [1, 10, 20]:
            times = await batch_get(n, f"{BASE_URL}/auth/me", headers=headers)
            s = pstats(times)
            ok_n = len(times)
            info(f"/auth/me × {n:2d}:  {ok_n}/{n} OK  |  P50={s.get('p50','?')}ms  P95={s.get('p95','?')}ms  max={s.get('max','?')}ms")
            r.metrics[f"auth_me_{n}"] = s
            await asyncio.sleep(1)

            # Sprawdź czy P95 rośnie nieproporcjonalnie
            current_p95 = s.get("p95", 0)
            if prev_p95 and current_p95 > prev_p95 * 4:
                warn(
                    f"P95 skoczyło {prev_p95}ms → {current_p95}ms przy skalowaniu × {n} "
                    f"— blokowanie event loop przez sync Supabase calls w middleware"
                )
                r.issues.append(
                    f"/auth/me P95 rośnie drastycznie przy skali ({prev_p95}ms → {current_p95}ms): "
                    "get_current_user() i require_active_subscription() wywołują Supabase synchronicznie "
                    "w async dependency. Każdy request blokuje event loop. "
                    "Fix: owinąć w run_in_threadpool() lub użyć asyncio Supabase client."
                )
            prev_p95 = current_p95
    else:
        warn("TEST_TOKEN nie ustawiony — pomijam /auth/me benchmark")

    # Sprawdź nieliniowość /health
    h1  = r.metrics.get("health_1",  {}).get("p50", 0)
    h50 = r.metrics.get("health_50", {}).get("p50", 0)
    if h1 and h50 and h50 > h1 * 8:
        warn(f"/health P50: 1user={h1}ms → 50users={h50}ms (×{round(h50/h1)}) — nieliniowy wzrost")
        r.issues.append(
            f"Nieliniowy wzrost latencji /health przy skali (×{round(h50/h1)}): "
            "Railway może mieć tylko 1 worker. Rozważ gunicorn z wieloma workerami."
        )

    r.passed = True  # benchmark, zawsze przechodzi — problemy w issues
    return r


# ══════════════════════════════════════════════════════════════════════════════
# S5 — Long session drift (sekwencyjne wiadomości)
# ══════════════════════════════════════════════════════════════════════════════
async def s5_long_session_drift() -> Result:
    """
    Wysyła LONG_SESSION_MSGS wiadomości sekwencyjnie (z pauzami dla rate limitu).
    Mierzy czy latencja rośnie z numerem wiadomości (drift).

    Potencjalne przyczyny driftu:
    - Narastanie background tasks (Uszatek/Blacha uruchamiane co chwilę)
    - Rosnący kontekst w pamięci agenta (więcej wiadomości = dłuższy prompt)
    - Supabase timeout przy wielu równoległych zapisach w tle
    - Memory leak w LangGraph state
    """
    r = Result(name=f"S5 — Long session drift ({LONG_SESSION_MSGS} sekwencyjnych wiad.)")

    if not TEST_TOKEN:
        warn("TEST_TOKEN nie ustawiony — pomijam S5")
        r.skipped = True
        return r

    messages = [
        "Jak trenować mięśnie klatki piersiowej?",
        "Jak wygląda poprawna progresja ciężarów?",
        "Ile serii i powtórzeń robić na masę mięśniową?",
        "Jakie ćwiczenia na mięśnie pleców?",
        "Co jest ważne przy treningu bicepsa?",
        "A przy treningu tricepsa?",
        "Jak powinna wyglądać rozgrzewka przed treningiem?",
        "Ile czasu odpoczywać między seriami?",
    ][:LONG_SESSION_MSGS]

    headers = auth_headers(TEST_TOKEN)
    times:   list[float] = []
    errors:  list[tuple] = []
    limited: list[int]   = []

    info(f"Wysyłam {len(messages)} wiadomości z ~13s przerwą (limit 5/min)...")

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=150)
    ) as session:
        for i, msg in enumerate(messages, 1):
            payload = {"message": msg}
            status, elapsed, body = await timed_post(
                session, f"{BASE_URL}/chat/",
                json=payload, headers=headers
            )

            if status == 200:
                times.append(elapsed)
                icon = "✓"
            elif status == 429:
                limited.append(i)
                icon = "⏱"
                info(f"  #{i:2d} {icon} Rate limited — czekam 20s...")
                await asyncio.sleep(20)
                # Ponów
                status2, elapsed2, _ = await timed_post(
                    session, f"{BASE_URL}/chat/",
                    json=payload, headers=headers
                )
                if status2 == 200:
                    times.append(elapsed2)
                else:
                    errors.append((i, status2))
                continue
            elif status == 0:
                errors.append((i, "TIMEOUT/CONNECTION_ERROR"))
                icon = "✗"
            else:
                errors.append((i, status))
                icon = "✗"

            dim(f"#{i:2d} {icon} {elapsed:6.0f}ms  {msg[:45]}")

            # Czekaj między wiadomościami żeby być poniżej 5/min
            if i < len(messages):
                await asyncio.sleep(13)

    r.metrics = {
        "messages": len(messages),
        "ok": len(times),
        "rate_limited": len(limited),
        "errors": len(errors),
        **pstats(times),
    }

    if len(times) >= 4:
        half = len(times) // 2
        avg_early = statistics.mean(times[:half])
        avg_late  = statistics.mean(times[half:])
        drift_pct = round((avg_late / avg_early - 1) * 100) if avg_early else 0

        r.metrics["drift_early_avg_ms"]  = round(avg_early)
        r.metrics["drift_late_avg_ms"]   = round(avg_late)
        r.metrics["drift_pct"]           = drift_pct

        if drift_pct > 50:
            warn(
                f"Drift latencji {drift_pct}%: "
                f"wczesne wiad.={avg_early:.0f}ms → późne={avg_late:.0f}ms"
            )
            r.issues.append(
                f"Drift latencji +{drift_pct}% w długiej sesji "
                f"({avg_early:.0f}ms → {avg_late:.0f}ms): "
                "możliwe narastanie background tasks (Uszatek klasyfikuje każdą wiad.), "
                "rosnący kontekst w systemprompcie, lub Supabase throttle."
            )
        else:
            ok(f"Brak znaczącego driftu: early={avg_early:.0f}ms → late={avg_late:.0f}ms (+{drift_pct}%)")

    r.passed = len(errors) == 0
    return r


# ══════════════════════════════════════════════════════════════════════════════
# S6 — SSE abrupt disconnect (zryw połączenia w trakcie streamowania)
# ══════════════════════════════════════════════════════════════════════════════
async def s6_sse_disconnect() -> Result:
    """
    Otwiera 5 połączeń SSE do /chat i zrywa je po ~2s (symuluje zamknięcie przeglądarki).
    Sprawdza czy serwer po tym nadal działa.

    ZNANY POTENCJALNY BUG:
      W chat.py: asyncio.create_task(run_agent()) uruchamia agenta jako task
      PRZED wysłaniem jakiejkolwiek odpowiedzi. Gdy klient zrywa połączenie,
      FastAPI anuluje generator, ale task agenta KONTYNUUJE w tle — wywołuje
      Anthropic API, zapisuje do Supabase, uruchamia background_tasks.
      Efekt: zasoby (tokeny Anthropic, wątki) są marnowane przy każdym zerwanym połączeniu.
    """
    r = Result(name="S6 — SSE abrupt disconnect (5 zerw. połączeń)")

    if not TEST_TOKEN:
        warn("TEST_TOKEN nie ustawiony — pomijam S6")
        r.skipped = True
        return r

    headers = auth_headers(TEST_TOKEN)
    payload = {"message": "Opisz szczegółowo jak poprawnie wykonać przysiad ze sztangą."}

    aborted = 0
    errors  = 0

    async def open_and_abort(session: aiohttp.ClientSession):
        nonlocal aborted, errors
        try:
            async with session.post(
                f"{BASE_URL}/chat/",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=4),   # zrywamy po 4s
            ) as resp:
                if resp.status == 200:
                    # Czytaj 2s, potem porzuć (nie wysyłamy FIN, po prostu timeout)
                    try:
                        await asyncio.wait_for(resp.content.read(), timeout=2.0)
                    except asyncio.TimeoutError:
                        aborted += 1
                elif resp.status in (429, 403):
                    pass  # rate limit / brak sub — oczekiwane
                else:
                    errors += 1
        except asyncio.TimeoutError:
            aborted += 1
        except aiohttp.ServerDisconnectedError:
            aborted += 1
        except Exception:
            errors += 1

    info("Otwieram 5 SSE connections i zrywam je po 2s...")
    conn = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=conn) as session:
        await asyncio.gather(*[open_and_abort(session) for _ in range(5)])

    info(f"Zeerwano: {aborted}  Błędy: {errors}")
    info("Czekam 3s i sprawdzam czy serwer żyje...")
    await asyncio.sleep(3)

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10)
    ) as session:
        h_status, h_ms = await timed_get(session, f"{BASE_URL}/health")

    r.metrics = {
        "connections_aborted": aborted,
        "errors": errors,
        "health_after_ms": round(h_ms),
        "health_status": h_status,
    }

    if h_status == 200:
        ok(f"Serwer żyje po {aborted} zerw. połączeniach  |  /health = {h_ms:.0f}ms")
        r.passed = True
    else:
        err(f"Serwer nie odpowiada po zerw. połączeniach! /health = {h_status}")
        r.issues.append(
            "Serwer niedostępny po burst SSE + disconnect — "
            "możliwy crash lub zbyt wiele wiszących task'ów agenta"
        )
        r.passed = False

    # Zawsze dodaj notatkę o architektonicznym problemie
    r.issues.append(
        "ARCHITEKTONICZNY: run_agent() w chat.py startuje jako asyncio.create_task() "
        "PRZED wysłaniem danych do klienta. Zryw połączenia nie anuluje tego tasku — "
        "agent kontynuuje wywołania Anthropic API i zapis do Supabase. "
        "Przy 100 userach zamykających kartę jednocześnie → 100 agentów wisi w tle. "
        "Fix: przekazać CancellationToken lub sprawdzać disconnection przez "
        "request.is_disconnected() w pętli keepalive."
    )

    return r


# ══════════════════════════════════════════════════════════════════════════════
# S7 — Payload fuzzing (/chat z dziwnymi danymi)
# ══════════════════════════════════════════════════════════════════════════════
async def s7_payload_fuzzing() -> Result:
    """
    Wysyła nieprawidłowe payloady do /chat.
    Oczekiwanie: ZAWSZE 4xx (lub 401/403 bez tokenu), NIGDY 500.
    """
    r = Result(name="S7 — Payload fuzzing: złe dane → 4xx, nigdy 500")

    headers = auth_headers(TEST_TOKEN) if TEST_TOKEN else {}

    cases = [
        ("pusty string",            {"message": ""},           [400]),
        ("tylko spacje",            {"message": "   "},        [400]),
        ("wiad. > 2000 znaków",     {"message": "A" * 2001},   [400]),
        ("brak pola 'message'",     {"tresc": "test"},         [422]),
        ("null message",            {"message": None},         [422]),
        ("liczba jako message",     {"message": 99999},        [422]),
        ("puste body",              {},                        [422]),
        # Unicode edge cases
        ("null byte w stringu",     {"message": "test\x00"},   [400, 200, 422]),
        ("tylko emoji",             {"message": "🏋️💪🔥"},   [200, 400, 403, 401]),
        ("string z max 2000 zn.",   {"message": "B" * 2000},   [200, 403, 401]),
    ]

    any_500 = False

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=15)
    ) as session:
        for name, payload, expected in cases:
            status, elapsed, body = await timed_post(
                session, f"{BASE_URL}/chat/",
                json=payload, headers=headers
            )

            acceptable = set(expected) | {401, 403}

            if status == 500:
                err(f"{'[' + name + ']':38s}  → {status} SERVER ERROR!  [{elapsed:.0f}ms]")
                r.issues.append(
                    f"HTTP 500 przy payload '{name}' — "
                    "niezabezpieczony wyjątek zamiast walidacji wejścia"
                )
                any_500 = True
            elif status in acceptable:
                ok(f"{'[' + name + ']':38s}  → {status}  [{elapsed:.0f}ms]")
            else:
                warn(f"{'[' + name + ']':38s}  → {status}  (oczekiwano {sorted(acceptable)})  [{elapsed:.0f}ms]")

    r.passed = not any_500
    return r


# ══════════════════════════════════════════════════════════════════════════════
# S8 — Guard DOS simulation (30 req bez tokenu)
# ══════════════════════════════════════════════════════════════════════════════
async def s8_guard_dos() -> Result:
    """
    30 równoległych requestów do /chat BEZ tokenu uwierzytelniającego.
    Symuluje bota próbującego masowo odpytywać endpoint.

    Oczekiwanie:
    - Wszystkie: 401 lub 422 (brak nagłówka Authorization)
    - Brak 200, brak 500
    - Szybkie odrzucanie (guard nie robi nic kosztownego przed weryfikacją)

    Potencjalny problem:
      Middleware weryfikuje token przez supabase.auth.get_user() — SYNCHRONICZNE
      wywołanie w async dependency. Przy 30 concurrent requestach bez tokenu
      FastAPI wprawdzie odrzuca wcześnie (brak nagłówka → 401), ale przy requestach
      Z nieprawidłowym tokenem wywołuje Supabase i blokuje event loop N × razy.
    """
    N = 30
    r = Result(name="S8 — Guard DOS simulation (30 req bez tokenu)")

    payload = {"message": "Jak trenować?"}

    conn = aiohttp.TCPConnector(limit=60)
    async with aiohttp.ClientSession(
        connector=conn, timeout=aiohttp.ClientTimeout(total=20)
    ) as session:
        t_wall = time.perf_counter()
        resps  = await asyncio.gather(*[
            timed_post(session, f"{BASE_URL}/chat/", json=payload)
            for _ in range(N)
        ])
        wall_ms = (time.perf_counter() - t_wall) * 1000

    statuses = [x[0] for x in resps]
    times    = [x[1] for x in resps]

    got_401 = statuses.count(401)
    got_422 = statuses.count(422)
    got_403 = statuses.count(403)
    got_500 = statuses.count(500)
    got_200 = statuses.count(200)
    got_0   = statuses.count(0)
    s       = pstats(times)

    r.metrics = {
        "requests": N,
        "401": got_401, "422": got_422, "403": got_403,
        "500": got_500, "200": got_200, "conn_err": got_0,
        "wall_ms": round(wall_ms),
        **s,
    }

    if got_200 > 0:
        err(f"{got_200} requestów przeszło bez tokenu — KRYTYCZNA LUKA AUTORYZACJI!")
        r.issues.append("KRYTYCZNE: /chat dostępny bez autoryzacji!")
        r.passed = False
    elif got_500 > 0:
        err(f"{got_500} × 500 — guard crasha przy masowym odpytywaniu bez auth!")
        r.issues.append(
            f"{got_500} × HTTP 500 przy DOS bez tokenu — "
            "guard nie obsługuje poprawnie braku nagłówka Authorization"
        )
        r.passed = False
    else:
        ok(
            f"Guard odrzuca poprawnie: {got_401}×401  {got_422}×422  "
            f"|  P50={s.get('p50','?')}ms  P95={s.get('p95','?')}ms"
        )
        r.passed = True

    if s.get("p95", 0) > 3000:
        warn(f"P95={s['p95']}ms — wolne odrzucanie requestów bez tokenu")
        r.issues.append(
            f"Wolny guard przy DOS (P95={s['p95']}ms): "
            "middleware.py — supabase.auth.get_user() i supabase_admin.table().execute() "
            "to SYNCHRONICZNE wywołania w async FastAPI dependency. "
            "Każdy request blokuje event loop na czas odpowiedzi Supabase. "
            "Fix: owinąć wywołania w run_in_threadpool() lub zastosować async Supabase client."
        )

    info(f"Wall-clock 30 requestów: {wall_ms:.0f}ms  (throughput: {N / (wall_ms/1000):.1f} req/s)")

    return r


# ══════════════════════════════════════════════════════════════════════════════
# Runner + raport końcowy
# ══════════════════════════════════════════════════════════════════════════════
async def run_all():
    print(f"\n{BOLD}{'═'*64}{RESET}")
    print(f"{BOLD}   STRESS TESTS — BEZ PIERDOLENIA backend{RESET}")
    print(f"{BOLD}{'═'*64}{RESET}")
    print(f"   BASE_URL : {BASE_URL}")
    if TEST_TOKEN:
        print(f"   TOKEN    : {TEST_TOKEN[:25]}...  (ustawiony)")
    else:
        print(f"   TOKEN    : {YELLOW}BRAK — scenariusze S3/S5/S6 będą pominięte{RESET}")
    print(f"{'─'*64}\n")

    # Sprawdź czy serwer żyje
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
        status, ms = await timed_get(s, f"{BASE_URL}/health")

    if status != 200:
        print(f"{RED}BŁĄD: Serwer nie odpowiada ({BASE_URL}/health → {status}){RESET}")
        print("Uruchom backend: cd backend && uvicorn main:app --reload")
        return

    ok(f"Serwer online — /health = {ms:.0f}ms\n")

    scenarios = [
        s1_concurrent_health,
        s2_auth_login_storm,
        s3_rate_limit_race,
        s4_latency_benchmark,
        s5_long_session_drift,
        s6_sse_disconnect,
        s7_payload_fuzzing,
        s8_guard_dos,
    ]

    results: list[Result] = []

    for fn in scenarios:
        print(f"\n{BOLD}{CYAN}── {fn.__name__.upper()} {'─'*(50-len(fn.__name__))}{RESET}")
        try:
            res = await fn()
            results.append(res)
        except Exception as exc:
            err(f"Nieoczekiwany wyjątek: {exc}")
            results.append(Result(name=fn.__name__, passed=False, issues=[str(exc)]))

    # ── Raport końcowy ────────────────────────────────────────────────────────
    print(f"\n\n{BOLD}{'═'*64}{RESET}")
    print(f"{BOLD}   RAPORT KOŃCOWY{RESET}")
    print(f"{BOLD}{'═'*64}{RESET}\n")

    all_issues: list[tuple[str, str]] = []
    passed = skipped = failed = 0

    for res in results:
        if res.skipped:
            label = f"{DIM}SKIP{RESET}"
            skipped += 1
        elif res.passed:
            label = f"{GREEN}PASS{RESET}"
            passed += 1
        else:
            label = f"{RED}FAIL{RESET}"
            failed += 1

        print(f"  {label}  {res.name}")
        for issue in res.issues:
            short = issue[:120] + "..." if len(issue) > 120 else issue
            print(f"        {YELLOW}⚠ {short}{RESET}")
            all_issues.append((res.name, issue))

    total = len(results)
    print(f"\n  {BOLD}Wynik: {passed} PASS  /  {failed} FAIL  /  {skipped} SKIP  "
          f"(z {total} scenariuszy){RESET}")

    if all_issues:
        print(f"\n{BOLD}Wszystkie znalezione problemy:{RESET}")
        for i, (name, issue) in enumerate(all_issues, 1):
            print(f"\n  {BOLD}{i}. [{name}]{RESET}")
            # Wyświetl pełny opis, zawinięty
            for chunk in [issue[j:j+100] for j in range(0, len(issue), 100)]:
                print(f"     {chunk}")
    else:
        print(f"\n  {GREEN}Brak wykrytych problemów.{RESET}")

    print(f"\n{BOLD}{'═'*64}{RESET}\n")

    # Zwróć exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(run_all())
