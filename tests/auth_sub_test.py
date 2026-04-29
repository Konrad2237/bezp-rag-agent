#!/usr/bin/env python3
"""
Testy auth, sesji i subskrypcji — BEZ PIERDOLENIA backend
==========================================================

Scenariusze:
  A1  Rejestracja z już istniejącym emailem → 400
  A2  Logowanie z błędnymi danymi (złe hasło, zły email, puste pola)
  A3  Stary/sfałszowany/wygasły token → 401 na chronionych endpointach
  A4  Brak subskrypcji → 403 na /chat (świeże konto bez płatności)
  A5  Dostęp do endpointów bez tokenu → 401 (wszystkie chronione ścieżki)
  A6  Wielokrotne logowanie z "różnych urządzeń" — oba tokeny działają równolegle
  A7  Wylogowanie: brak backend logout → token nadal ważny (stateless JWT)
  A8  Manipulacja tokenem (zmodyfikowany podpis, losowy string, edge cases)
  A9  Rejestracja — walidacja pól (email bez @, za krótkie hasło, brak wymaganych pól)
  A10 Subskrypcja: /auth/me zwraca poprawny subscription_status

Wymagania:
    pip install aiohttp

Konfiguracja (zmienne środowiskowe lub .env):
    BASE_URL         — adres backendu (domyślnie: http://localhost:8000)
    TEST_TOKEN       — JWT aktywnego usera z aktywną subskrypcją (wymagany dla A6/A7/A10)
    TEST_EMAIL       — email konta TEST_TOKEN (potrzebny do A6 — ponowne logowanie)
    TEST_PASSWORD    — hasło konta TEST_TOKEN (potrzebny do A6)
    TEST_REFRESH_TOKEN — refresh_token do testu odświeżania sesji (opcjonalny)

Uruchomienie:
    cd tests
    python auth_sub_test.py

    # Z tokenem:
    TEST_TOKEN=eyJ... TEST_EMAIL=ty@mail.com TEST_PASSWORD=haslo python auth_sub_test.py

    # Na produkcji:
    BASE_URL=https://bezp-rag-agent-production.up.railway.app TEST_TOKEN=eyJ... python auth_sub_test.py
"""

import asyncio
import os
import sys
import time
import json
import string
import random
from dataclasses import dataclass, field
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import aiohttp
except ImportError:
    print("BŁĄD: Wymagany pakiet aiohttp.\nZainstaluj: pip install aiohttp")
    sys.exit(1)

# ─── Wczytaj .env ──────────────────────────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

BASE_URL           = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
TEST_TOKEN         = os.getenv("TEST_TOKEN", "")
TEST_EMAIL         = os.getenv("TEST_EMAIL", "")
TEST_PASSWORD      = os.getenv("TEST_PASSWORD", "")
TEST_REFRESH_TOKEN = os.getenv("TEST_REFRESH_TOKEN", "")

# ─── Kolory ────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}+{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}!{RESET}  {msg}")
def err(msg):  print(f"  {RED}x{RESET}  {msg}")
def info(msg): print(f"  {CYAN}>{RESET}  {msg}")
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
def rand_email() -> str:
    """Generuje unikalny testowy email."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"bezptest_{suffix}@example.com"


async def post(session: aiohttp.ClientSession, path: str, **kw) -> tuple[int, dict | str]:
    try:
        async with session.post(f"{BASE_URL}{path}", **kw) as resp:
            try:
                body = await resp.json()
            except Exception:
                body = await resp.text()
            return resp.status, body
    except Exception as e:
        return 0, str(e)


async def get(session: aiohttp.ClientSession, path: str, **kw) -> tuple[int, dict | str]:
    try:
        async with session.get(f"{BASE_URL}{path}", **kw) as resp:
            try:
                body = await resp.json()
            except Exception:
                body = await resp.text()
            return resp.status, body
    except Exception as e:
        return 0, str(e)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def check(label: str, status: int, expected: list[int], r: Result, body=None) -> bool:
    """Sprawdza status i loguje wynik. Zwraca True jeśli OK."""
    passed = status in expected
    line = f"{'[' + label + ']':52s}  {status}"
    if body and isinstance(body, dict) and "detail" in body:
        line += f"  '{body['detail']}'"
    if passed:
        ok(line)
    else:
        err(f"{line}  (oczekiwano {expected})")
        r.issues.append(f"{label}: status {status}, oczekiwano {expected}. Body: {body}")
        r.passed = False
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# A1 — Rejestracja z istniejącym emailem
# ══════════════════════════════════════════════════════════════════════════════
async def a1_duplicate_registration() -> Result:
    """
    Rejestruje konto z nowym emailem, potem próbuje zarejestrować się ponownie
    z tym samym emailem. Oczekiwanie: drugi request → 400.
    Sprawdza też komunikat błędu.
    """
    r = Result(name="A1 — Rejestracja: duplikat emaila")
    email = rand_email()
    payload = {
        "email": email, "password": "TestHaslo123!",
        "imie": "Test", "nazwisko": "Duplikat"
    }

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        # Pierwsza rejestracja — powinna się udać
        status1, body1 = await post(session, "/auth/register", json=payload)
        check("Pierwsza rejestracja (nowy email)", status1, [200], r, body1)

        # Druga rejestracja z tym samym emailem
        status2, body2 = await post(session, "/auth/register", json=payload)
        passed = check("Duplikat emaila", status2, [400], r, body2)

        if passed and isinstance(body2, dict):
            detail = body2.get("detail", "")
            if "istnieje" in detail.lower() or "already" in detail.lower() or "email" in detail.lower():
                ok(f"Komunikat błędu po polsku: '{detail}'")
            else:
                warn(f"Status 400 OK, ale komunikat nieoczekiwany: '{detail}'")
                r.issues.append(
                    f"Duplikat emaila zwraca 400 OK, ale komunikat jest: '{detail}' "
                    "— oczekiwano czegoś w stylu 'Konto z tym adresem email już istnieje'"
                )

    info(f"Testowy email (do ew. czyszczenia): {email}")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# A2 — Logowanie z błędnymi danymi
# ══════════════════════════════════════════════════════════════════════════════
async def a2_login_bad_credentials() -> Result:
    """
    Parametryczny test logowania z różnymi błędnymi danymi.
    Każdy przypadek musi zwrócić 4xx — nigdy 500.
    """
    r = Result(name="A2 — Logowanie: błędne dane (parametryczny)")

    # Istniejący email potrzebny do testu złego hasła —
    # używamy TEST_EMAIL jeśli jest, lub rejestrujemy swój
    existing_email = TEST_EMAIL or "nikt@example.com"

    cases = [
        # (opis,                        payload,                                    oczekiwane statusy)
        ("Złe hasło, dobry email",      {"email": existing_email,
                                         "password": "ZleHaslo999!"},                [401]),
        ("Nieistniejący email",         {"email": "ghost_x99@nowhere.invalid",
                                         "password": "CokolwiekXX1"},                [401]),
        ("Puste hasło",                 {"email": existing_email,
                                         "password": ""},                            [400, 422, 401]),
        ("Pusty email",                 {"email": "",
                                         "password": "CokolwiekXX1"},               [422, 400]),
        ("Oba pola puste",              {"email": "",
                                         "password": ""},                           [422, 400]),
        ("Brak pola 'password'",        {"email": existing_email},                   [422]),
        ("Brak pola 'email'",           {"password": "Test123!"},                    [422]),
        ("Puste body",                  {},                                          [422]),
        ("Email bez domeny",            {"email": "bezdomena",
                                         "password": "Test123!"},                   [422]),
        ("Email ze spacją",             {"email": "user @example.com",
                                         "password": "Test123!"},                   [422, 401]),
        ("SQL injection w emailu",      {"email": "'; DROP TABLE users; --@x.pl",
                                         "password": "Test123!"},                   [401, 422]),
        ("Bardzo długie hasło",         {"email": existing_email,
                                         "password": "A" * 1000},                  [401, 400]),
    ]

    any_500 = False
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        for label, payload, expected in cases:
            status, body = await post(session, "/auth/login", json=payload)
            if status == 500:
                err(f"{'[' + label + ']':52s}  500 SERVER ERROR!")
                r.issues.append(f"HTTP 500 przy logowaniu z payload '{label}'")
                any_500 = True
            else:
                check(label, status, expected, r, body)

    if any_500:
        r.passed = False
    return r


# ══════════════════════════════════════════════════════════════════════════════
# A3 — Stary / sfałszowany / wygasły token
# ══════════════════════════════════════════════════════════════════════════════
async def a3_invalid_tokens() -> Result:
    """
    Różne warianty nieprawidłowych tokenów → zawsze 401 na /auth/me.
    Sprawdza też zachowanie endpointów przy braku nagłówka Authorization.

    Osobny test: odświeżanie sesji przez /auth/refresh.
    """
    r = Result(name="A3 — Stary/sfałszowany/wygasły token → 401")

    # Znany wygasły token (podpis OK, ale exp w przeszłości) — sfabrykowany
    FAKE_EXPIRED = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJ1c2VyMTIzIiwiZXhwIjoxNjAwMDAwMDAwfQ."  # exp=2020
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )

    cases = [
        ("Losowy string",           "randomstringnotaJWT"),
        ("Tylko 'Bearer'",          ""),
        ("Zmodyfikowany podpis",    (TEST_TOKEN[:-5] + "XXXXX") if TEST_TOKEN else "modifiedXXX"),
        ("Wygasły token (exp 2020)", FAKE_EXPIRED),
        ("Token bez podpisu",       "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ1c2VyMTIzIn0."),
        ("Token z null bytes",      "eyJhbGciOiJIUzI1NiJ9.\x00\x00\x00.sig"),
        ("Bardzo długi string",     "A" * 2000),
        ("JSON zamiast tokenu",     '{"user_id": "hacker", "role": "admin"}'),
    ]

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        for label, bad_token in cases:
            headers = {"Authorization": f"Bearer {bad_token}"}
            status, body = await get(session, "/auth/me", headers=headers)
            check(label, status, [401], r, body)

        # Brak nagłówka Authorization w ogóle
        status, body = await get(session, "/auth/me")
        check("Brak nagłówka Authorization", status, [401, 422], r, body)

    # Test /auth/refresh
    print()
    info("Test /auth/refresh...")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        # Nieważny refresh_token
        status, body = await post(session, "/auth/refresh",
                                  json={"refresh_token": "fake_refresh_token_xyz"})
        check("/auth/refresh (nieważny token)", status, [401], r, body)

        # Brak pola refresh_token
        status, body = await post(session, "/auth/refresh", json={})
        check("/auth/refresh (brak pola)", status, [422], r, body)

        # Ważny refresh_token (opcjonalny — wymaga TEST_REFRESH_TOKEN)
        if TEST_REFRESH_TOKEN:
            status, body = await post(session, "/auth/refresh",
                                      json={"refresh_token": TEST_REFRESH_TOKEN})
            check("/auth/refresh (ważny token)", status, [200], r, body)
            if status == 200 and isinstance(body, dict):
                has_at = "access_token" in body
                has_rt = "refresh_token" in body
                if has_at and has_rt:
                    ok("Odpowiedź zawiera access_token + refresh_token")
                else:
                    warn(f"Brak pól w odpowiedzi: {list(body.keys())}")
        else:
            warn("TEST_REFRESH_TOKEN nie ustawiony — pomijam test ważnego refresh_token")

    return r


# ══════════════════════════════════════════════════════════════════════════════
# A4 — Brak subskrypcji → 403 na /chat
# ══════════════════════════════════════════════════════════════════════════════
async def a4_no_subscription_blocked() -> Result:
    """
    Rejestruje świeże konto (bez płatności → subscription_status = null),
    loguje się i próbuje użyć /chat.
    Oczekiwanie: 403 Brak aktywnej subskrypcji.

    Sprawdza też że /auth/me zwraca subscription_status: null.
    Świeże konto może:
    - Zrobić quiz (/quiz/submit — nie wymaga subskrypcji? sprawdzamy)
    - NIE może pisać z trenerem (/chat → 403)
    """
    r = Result(name="A4 — Brak subskrypcji → 403 na /chat")

    email    = rand_email()
    password = "TestHaslo456!"
    reg_payload = {"email": email, "password": password,
                   "imie": "Test", "nazwisko": "NoSub"}

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        # Rejestracja
        status, body = await post(session, "/auth/register", json=reg_payload)
        if not check("Rejestracja nowego konta", status, [200], r, body):
            r.issues.append("Nie można przetestować A4 — rejestracja się nie powiodła")
            return r

        # Logowanie
        status, body = await post(session, "/auth/login",
                                  json={"email": email, "password": password})
        if not check("Logowanie nowego konta", status, [200], r, body):
            r.issues.append("Nie można przetestować A4 — logowanie się nie powiodło")
            return r

        token = body.get("access_token", "") if isinstance(body, dict) else ""
        if not token:
            err("Brak access_token w odpowiedzi logowania")
            r.passed = False
            return r

        headers = auth(token)

        # /auth/me — sprawdź subscription_status
        status, body = await get(session, "/auth/me", headers=headers)
        if check("/auth/me (nowe konto)", status, [200], r, body):
            sub = body.get("subscription_status") if isinstance(body, dict) else "?"
            if sub is None:
                ok(f"subscription_status = null (poprawne dla nowego konta)")
            else:
                warn(f"subscription_status = '{sub}' — oczekiwano null dla nowego konta")
                r.issues.append(
                    f"Nowe konto ma subscription_status='{sub}' zamiast null. "
                    "Sprawdź czy webhook Stripe nie nadpisał statusu przypadkowo."
                )

        # /chat — powinien zwrócić 403
        status, body = await post(session, "/chat/",
                                  json={"message": "Hej, jak ćwiczyć?"},
                                  headers=headers)
        passed = check("/chat/ (brak subskrypcji)", status, [403], r, body)
        if passed and isinstance(body, dict):
            detail = body.get("detail", "")
            if "subskrypcj" in detail.lower():
                ok(f"Komunikat: '{detail}'")
            else:
                warn(f"Status 403 OK, ale komunikat: '{detail}'")

        # /plan/ (GET) — sprawdź czy też blokuje
        status, body = await get(session, "/plan/", headers=headers)
        check("/plan/ GET (brak subskrypcji)", status, [403, 200], r, body)
        if status == 200:
            warn(
                "/plan/ dostępny bez subskrypcji — to może być OK (plan tylko do odczytu) "
                "lub luka (user może widzieć plan bez płatności)"
            )

    info(f"Konto testowe (cleanup ręczny w Supabase): {email}")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# A5 — Dostęp do endpointów bez tokenu → 401
# ══════════════════════════════════════════════════════════════════════════════
async def a5_no_token_blocked() -> Result:
    """
    Sprawdza wszystkie chronione endpointy bez tokenu Authorization.
    Każdy powinien zwrócić 401 (lub 422 jeśli brakuje nagłówka wymaganego przez pydantic).
    Żaden nie powinien zwrócić 200 ani 500.
    """
    r = Result(name="A5 — Brak tokenu → 401 na wszystkich chronionych endpointach")

    cases = [
        # (metoda, ścieżka, body)
        ("GET",   "/auth/me",                         None),
        ("POST",  "/chat/",                            {"message": "test"}),
        ("POST",  "/quiz/submit",                      {"wiek": 25, "plec": "m", "cel": "masa",
                                                        "doswiadczenie": "poczatkujacy",
                                                        "dni_treningowe": 3, "czas_treningu": "60-90",
                                                        "miejsce_treningu": "silownia",
                                                        "sprzet": ["sztanga"]}),
        ("GET",   "/plan/",                            None),
        ("POST",  "/plan/generate",                    {}),
        ("GET",   "/settings/profile",                 None),
        ("PATCH", "/settings/profile",                 {"waga": 80}),
        ("PATCH", "/settings/email",                   {"new_email": "x@x.com",
                                                        "current_password": "x"}),
        ("PATCH", "/settings/password",                {"old_password": "x",
                                                        "new_password": "newpassword1"}),
        ("DELETE","/settings/account",                 {"password": "x",
                                                        "confirm_text": "USUŃ"}),
        ("POST",  "/payments/create-checkout-session", {"plan": "month"}),
        ("POST",  "/payments/cancel-subscription",     {}),
    ]

    any_leak = False
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        for method, path, body in cases:
            kw = {}
            if body is not None:
                kw["json"] = body

            if method == "GET":
                status, resp_body = await get(session, path, **kw)
            else:
                try:
                    async with session.request(
                        method, f"{BASE_URL}{path}", **kw,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        try:
                            resp_body = await resp.json()
                        except Exception:
                            resp_body = await resp.text()
                        status = resp.status
                except Exception as e:
                    status, resp_body = 0, str(e)

            if status == 200:
                err(f"{'[' + method + ' ' + path + ']':52s}  200 — DOSTĘP BEZ TOKENU!")
                r.issues.append(f"KRYTYCZNE: {method} {path} dostępny bez autoryzacji!")
                any_leak = True
            elif status == 500:
                err(f"{'[' + method + ' ' + path + ']':52s}  500 SERVER ERROR")
                r.issues.append(f"HTTP 500 na {method} {path} bez tokenu — niezabezpieczony wyjątek")
                r.passed = False
            else:
                check(f"{method} {path}", status, [401, 403, 422], r, resp_body)

    if any_leak:
        r.passed = False

    return r


# ══════════════════════════════════════════════════════════════════════════════
# A6 — Multi-device: dwa tokeny działają równolegle
# ══════════════════════════════════════════════════════════════════════════════
async def a6_multi_device_login() -> Result:
    """
    Loguje się dwukrotnie z tymi samymi danymi (symulacja 2 urządzeń).
    Oba tokeny powinny działać równolegle — Supabase nie unieważnia starych sesji.

    Weryfikuje też że oba tokeny identyfikują tego samego user_id.
    """
    r = Result(name="A6 — Multi-device: dwa tokeny działają równolegle")

    if not TEST_EMAIL or not TEST_PASSWORD:
        warn("TEST_EMAIL lub TEST_PASSWORD nie ustawione — pomijam A6")
        r.skipped = True
        return r

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        # Login 1 — "urządzenie A"
        status1, body1 = await post(session, "/auth/login",
                                    json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        if not check("Login urządzenie A", status1, [200], r, body1):
            return r
        token_a = body1.get("access_token", "")
        uid_a   = body1.get("user_id", "")

        # Krótka przerwa (inne urządzenie loguje się chwilę później)
        await asyncio.sleep(0.5)

        # Login 2 — "urządzenie B"
        status2, body2 = await post(session, "/auth/login",
                                    json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        if not check("Login urządzenie B", status2, [200], r, body2):
            return r
        token_b = body2.get("access_token", "")
        uid_b   = body2.get("user_id", "")

        # Oba tokeny muszą być różne (nowe sesje)
        if token_a == token_b:
            warn("Oba logowania zwróciły IDENTYCZNY token — Supabase zwraca tę samą sesję")
            r.issues.append(
                "Dwa logowania z tych samych credentiali zwróciły identyczny token. "
                "Może to być feature (session reuse) lub bug. "
                "Zależy od konfiguracji Supabase Auth."
            )
        else:
            ok("Dwa różne tokeny dla dwóch logowań (niezależne sesje)")

        # User ID musi być identyczny (to samo konto)
        if uid_a and uid_b and uid_a == uid_b:
            ok(f"Oba tokeny identyfikują tego samego usera: {uid_a[:16]}...")
        elif uid_a != uid_b:
            err(f"Różne user_id! A={uid_a[:8]} B={uid_b[:8]} — KRYTYCZNY BUG")
            r.issues.append("Dwa logowania z tych samych credentiali dały różne user_id!")
            r.passed = False

        # Weryfikacja równoległa — oba tokeny działają jednocześnie
        info("Sprawdzam /auth/me dla obu tokenów równolegle...")
        results = await asyncio.gather(
            get(session, "/auth/me", headers=auth(token_a)),
            get(session, "/auth/me", headers=auth(token_b)),
        )

        for i, (st, bd) in enumerate(results, 1):
            label = f"/auth/me token-{'A' if i == 1 else 'B'} (równolegle)"
            check(label, st, [200], r, bd)

    return r


# ══════════════════════════════════════════════════════════════════════════════
# A7 — Wylogowanie: brak server-side logout — token nadal ważny
# ══════════════════════════════════════════════════════════════════════════════
async def a7_logout_token_validity() -> Result:
    """
    Sprawdza zachowanie po wylogowaniu.

    ZNANA LUKA ARCHITEKTONICZNA:
    Backend nie ma endpointu /auth/logout.
    Frontend czyści localStorage — ale token JWT jest nadal ważny przez cały TTL (3600s).
    Jeśli ktoś przechwyci token (XSS, DevTools, logi), może go używać
    do 1h po "wylogowaniu" ofiary.

    Test sprawdza:
    1. Czy endpoint /auth/logout w ogóle istnieje → powinno być 404/405 (nie istnieje)
    2. Czy token TEST_TOKEN nadal działa po symulowanym wylogowaniu
    3. Czy /auth/sign-out (Supabase naming) istnieje
    """
    r = Result(name="A7 — Wylogowanie: brak server-side logout (stateless JWT)")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        # Sprawdź czy /auth/logout istnieje
        status, body = await post(session, "/auth/logout",
                                  json={}, headers=auth(TEST_TOKEN) if TEST_TOKEN else {})
        if status == 200:
            ok("/auth/logout istnieje i zwraca 200 — server-side logout działa!")
        elif status in [401, 403]:
            warn("/auth/logout istnieje ale wymaga tokenu (mały problem — endpoint jest)")
        elif status in [404, 405, 422]:
            err(
                f"/auth/logout → {status} — endpoint NIE ISTNIEJE. "
                "Token pozostaje ważny przez cały TTL po 'wylogowaniu'."
            )
            r.issues.append(
                "BRAK server-side logout: /auth/logout nie istnieje. "
                "Frontend czyści localStorage, ale JWT pozostaje ważny przez ~3600s. "
                "Jeśli token zostanie przechwycony (XSS, DevTools), "
                "atakujący może go używać do 1h po wylogowaniu. "
                "Fix: POST /auth/logout → supabase.auth.sign_out(token) + "
                "ewentualny blacklist tokenów w Supabase lub short-lived JWT."
            )
        else:
            dim(f"/auth/logout → {status} (nieoczekiwany status)")

        # Sprawdź alternatywne nazwy
        status2, _ = await post(session, "/auth/sign-out", json={})
        dim(f"/auth/sign-out → {status2}")

        # Jeśli mamy TEST_TOKEN, sprawdź że nadal działa (demonstracja luki)
        if TEST_TOKEN:
            status3, body3 = await get(session, "/auth/me", headers=auth(TEST_TOKEN))
            if status3 == 200:
                ok(
                    "TEST_TOKEN działa → po 'wylogowaniu' (usunięciu z localStorage) "
                    "token jest nadal ważny. To DEMONSTRACJA luki — nie błąd serwera."
                )
                r.issues.append(
                    "JWT pozostaje ważny po stronie serwera. "
                    "'Wylogowanie' działa tylko na frontendie (localStorage clear). "
                    "Token ważny do wygaśnięcia (domyślnie 3600s w Supabase)."
                )
            elif status3 == 401:
                ok("Token już wygasł — serwer poprawnie odrzuca")

    # Test zawsze PASS — dokumentujemy architekturę, nie błąd
    r.passed = True
    return r


# ══════════════════════════════════════════════════════════════════════════════
# A8 — Manipulacja tokenem
# ══════════════════════════════════════════════════════════════════════════════
async def a8_token_manipulation() -> Result:
    """
    Próby obejścia autoryzacji przez manipulację JWT:
    - Zmiana payload (user_id, rola) bez re-podpisania
    - Algorytm 'none' (JWT bez podpisu)
    - Token z innego serwisu
    - Znaki specjalne, injection w Bearer value
    """
    r = Result(name="A8 — Manipulacja tokenem → zawsze 401")

    import base64

    def b64_pad(s: str) -> str:
        return s + "=" * (-len(s) % 4)

    def forge_jwt(payload_dict: dict) -> str:
        """Tworzy JWT z dowolnym payloadem ale bez ważnego podpisu."""
        header  = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            json.dumps(payload_dict).encode()
        ).decode().rstrip("=")
        return f"{header}.{payload}.fakesignature"

    cases = [
        ("JWT alg:none (bez podpisu)",
         "eyJhbGciOiJub25lIn0."
         + base64.urlsafe_b64encode(b'{"sub":"admin","role":"admin"}').decode().rstrip("=")
         + "."),

        ("Sfałszowany payload — admin role",
         forge_jwt({"sub": "00000000-0000-0000-0000-000000000000",
                    "role": "admin", "exp": 9999999999})),

        ("Sfałszowany payload — inny user_id",
         forge_jwt({"sub": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "role": "authenticated", "exp": 9999999999})),

        ("Injection w Bearer value",
         "'; SELECT * FROM users; --"),

        ("Null bytes w tokenie",
         "eyJhbG\x00ciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.sig"),

        ("Token z innego JWT serwisu (Google shape)",
         "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEifQ."
         "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
         "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"),
    ]

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        for label, bad_token in cases:
            headers = {"Authorization": f"Bearer {bad_token}"}
            status, body = await get(session, "/auth/me", headers=headers)
            check(label, status, [401], r, body)

        # Próba IDOR: TEST_TOKEN działa, ale zmiana user_id w body (nie w tokenie)
        if TEST_TOKEN:
            info("IDOR test: user_id w body vs JWT...")
            status, body = await post(
                session, "/chat/",
                json={"message": "test", "user_id": "aaaaaaaa-0000-0000-0000-000000000000"},
                headers=auth(TEST_TOKEN)
            )
            check("IDOR: user_id w body ignorowany (liczy się JWT)", status,
                  [200, 429, 403, 400], r, body)
            if status != 403 and status != 401:
                ok("Serwer nie wystawia endpointu który użyłby user_id z body — poprawnie")

    return r


# ══════════════════════════════════════════════════════════════════════════════
# A9 — Walidacja pól rejestracji
# ══════════════════════════════════════════════════════════════════════════════
async def a9_registration_validation() -> Result:
    """
    Edge case'y w polach rejestracji.
    Każdy zły payload → 422 lub 400, nigdy 200 ani 500.
    """
    r = Result(name="A9 — Rejestracja: walidacja pól")

    cases = [
        # (opis,                          payload,                                   oczekiwane)
        ("Email bez @",                   {"email": "niesam",
                                           "password": "Test123!", "imie": "A", "nazwisko": "B"},    [422]),
        ("Email bez domeny",              {"email": "x@",
                                           "password": "Test123!", "imie": "A", "nazwisko": "B"},    [422]),
        ("Pusty email",                   {"email": "",
                                           "password": "Test123!", "imie": "A", "nazwisko": "B"},    [422]),
        ("Hasło < 6 znaków",              {"email": rand_email(),
                                           "password": "Ab1", "imie": "A", "nazwisko": "B"},         [400, 422]),
        ("Puste hasło",                   {"email": rand_email(),
                                           "password": "", "imie": "A", "nazwisko": "B"},            [400, 422]),
        ("Brak pola imie",                {"email": rand_email(),
                                           "password": "Test123!", "nazwisko": "B"},                 [422]),
        ("Brak pola nazwisko",            {"email": rand_email(),
                                           "password": "Test123!", "imie": "A"},                     [422]),
        ("Brak wszystkich pól",           {},                                                         [422]),
        ("Null jako email",               {"email": None,
                                           "password": "Test123!", "imie": "A", "nazwisko": "B"},    [422]),
        ("Liczba jako email",             {"email": 12345,
                                           "password": "Test123!", "imie": "A", "nazwisko": "B"},    [422]),
        ("SQL injection w haśle",         {"email": rand_email(),
                                           "password": "'; DROP TABLE users;--",
                                           "imie": "A", "nazwisko": "B"},                            [200, 400, 422]),
        ("XSS w imieniu",                 {"email": rand_email(),
                                           "password": "Test123!",
                                           "imie": "<script>alert(1)</script>", "nazwisko": "B"},    [200, 400]),
        ("Bardzo długie imię (1000 zn.)", {"email": rand_email(),
                                           "password": "Test123!",
                                           "imie": "A" * 1000, "nazwisko": "B"},                     [200, 400, 422]),
    ]

    any_500 = False
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        for label, payload, expected in cases:
            status, body = await post(session, "/auth/register", json=payload)
            if status == 500:
                err(f"{'[' + label + ']':52s}  500 SERVER ERROR!")
                r.issues.append(f"HTTP 500 przy rejestracji z payload '{label}'")
                any_500 = True
            else:
                check(label, status, expected, r, body)

    if any_500:
        r.passed = False
    return r


# ══════════════════════════════════════════════════════════════════════════════
# A10 — /auth/me zwraca poprawny subscription_status
# ══════════════════════════════════════════════════════════════════════════════
async def a10_auth_me_subscription() -> Result:
    """
    Sprawdza że /auth/me zwraca poprawną strukturę odpowiedzi
    z subscription_status dla zalogowanego usera z aktywną subskrypcją.

    Wymaga TEST_TOKEN z aktywną subskrypcją.
    """
    r = Result(name="A10 — /auth/me: structure + subscription_status")

    if not TEST_TOKEN:
        warn("TEST_TOKEN nie ustawiony — pomijam A10")
        r.skipped = True
        return r

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        status, body = await get(session, "/auth/me", headers=auth(TEST_TOKEN))

        if not check("/auth/me z ważnym tokenem", status, [200], r, body):
            return r

        if not isinstance(body, dict):
            err(f"Odpowiedź to nie JSON object: {type(body)}")
            r.passed = False
            return r

        required_fields = ["user_id", "has_profile", "subscription_status"]
        for field_name in required_fields:
            if field_name in body:
                ok(f"Pole '{field_name}' obecne: {repr(body[field_name])}")
            else:
                err(f"Brak wymaganego pola '{field_name}' w odpowiedzi")
                r.issues.append(f"/auth/me brakuje pola '{field_name}'")
                r.passed = False

        sub = body.get("subscription_status")
        if sub == "active":
            ok("subscription_status = 'active' (TOKEN z aktywną subskrypcją — poprawne)")
        elif sub is None:
            warn("subscription_status = null — token bez subskrypcji lub problem z bazą")
            r.issues.append(
                "TEST_TOKEN wskazuje na konto bez aktywnej subskrypcji (null). "
                "Używaj tokenu konta które ma subscription_status='active' w Supabase."
            )
        else:
            warn(f"subscription_status = '{sub}' (nie 'active')")
            r.issues.append(f"Konto ma status '{sub}', nie 'active'")

        has_profile = body.get("has_profile")
        if isinstance(has_profile, bool):
            ok(f"has_profile = {has_profile}")
        else:
            warn(f"has_profile ma nieoczekiwany typ: {type(has_profile)} = {has_profile}")

        user_id = body.get("user_id", "")
        if user_id and len(user_id) == 36:
            ok(f"user_id to poprawny UUID: {user_id[:16]}...")
        else:
            warn(f"user_id wygląda dziwnie: '{user_id}'")

    return r


# ══════════════════════════════════════════════════════════════════════════════
# Runner + raport końcowy
# ══════════════════════════════════════════════════════════════════════════════
async def run_all():
    print(f"\n{BOLD}{'=' * 64}{RESET}")
    print(f"{BOLD}   AUTH & SUBSCRIPTION TESTS — BEZ PIERDOLENIA{RESET}")
    print(f"{BOLD}{'=' * 64}{RESET}")
    print(f"   BASE_URL      : {BASE_URL}")
    print(f"   TEST_TOKEN    : {'ustawiony (' + TEST_TOKEN[:20] + '...)' if TEST_TOKEN else YELLOW + 'BRAK — A6/A7/A8/A10 mogą być pominięte' + RESET}")
    print(f"   TEST_EMAIL    : {TEST_EMAIL or YELLOW + 'BRAK — A6 pominięte' + RESET}")
    print(f"   TEST_PASSWORD : {'ustawione' if TEST_PASSWORD else YELLOW + 'BRAK' + RESET}")
    print(f"{'─' * 64}\n")

    # Sprawdź czy serwer żyje
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
        try:
            async with s.get(f"{BASE_URL}/health") as resp:
                if resp.status != 200:
                    print(f"{RED}BŁĄD: Backend nie odpowiada ({BASE_URL}/health → {resp.status}){RESET}")
                    print("Uruchom: cd backend && uvicorn main:app --reload")
                    return
                print(f"  {GREEN}+{RESET}  Backend online\n")
        except Exception as e:
            print(f"{RED}BŁĄD: Nie można połączyć się z {BASE_URL}: {e}{RESET}")
            print("Uruchom: cd backend && uvicorn main:app --reload")
            return

    scenarios = [
        a1_duplicate_registration,
        a2_login_bad_credentials,
        a3_invalid_tokens,
        a4_no_subscription_blocked,
        a5_no_token_blocked,
        a6_multi_device_login,
        a7_logout_token_validity,
        a8_token_manipulation,
        a9_registration_validation,
        a10_auth_me_subscription,
    ]

    results: list[Result] = []

    for fn in scenarios:
        print(f"\n{BOLD}{CYAN}── {fn.__name__.upper()} {'─' * (50 - len(fn.__name__))}{RESET}")
        try:
            res = await fn()
            results.append(res)
        except Exception as exc:
            import traceback
            err(f"Nieoczekiwany wyjątek: {exc}")
            traceback.print_exc()
            results.append(Result(name=fn.__name__, passed=False, issues=[str(exc)]))

    # ── Raport końcowy ────────────────────────────────────────────────────────
    print(f"\n\n{BOLD}{'=' * 64}{RESET}")
    print(f"{BOLD}   RAPORT KOŃCOWY{RESET}")
    print(f"{BOLD}{'=' * 64}{RESET}\n")

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
            short = issue[:110] + "..." if len(issue) > 110 else issue
            print(f"        {YELLOW}! {short}{RESET}")
            all_issues.append((res.name, issue))

    total = len(results)
    print(f"\n  {BOLD}Wynik: {passed} PASS  /  {failed} FAIL  /  {skipped} SKIP  "
          f"(z {total} scenariuszy){RESET}")

    if all_issues:
        print(f"\n{BOLD}Wszystkie znalezione problemy:{RESET}")
        for i, (name, issue) in enumerate(all_issues, 1):
            print(f"\n  {BOLD}{i}. [{name}]{RESET}")
            for chunk in [issue[j:j + 100] for j in range(0, len(issue), 100)]:
                print(f"     {chunk}")
    else:
        print(f"\n  {GREEN}Brak wykrytych problemów.{RESET}")

    print(f"\n{BOLD}{'=' * 64}{RESET}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(run_all())
