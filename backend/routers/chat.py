from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from middleware import get_current_user, require_active_subscription
from agents.graph import stream_agent
from agents.extraction import run_extraction_agent
from agents.summarizer import run_summarizer_agent
from services.memory import get_user_profile, get_unsummarized_count
from config import supabase, claude_client
from datetime import datetime, timezone, timedelta
import asyncio
import json
import os

router = APIRouter()

# Atomowy licznik in-flight requestów per user — chroni przed race condition
# w rate limiterze (DB odczyt przed zapisem wiadomości)
_in_flight: dict[str, int] = {}
_rate_lock = asyncio.Lock()


class ChatRequest(BaseModel):
    message: str


class SessionEndRequest(BaseModel):
    token: str


async def _should_run_extraction(user_message: str) -> bool:
    """Haiku klasyfikuje czy wiadomość zawiera informacje o userze warte zapisania."""
    try:
        response = await run_in_threadpool(
            lambda: claude_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{"role": "user", "content":
                    f"Czy ta wiadomość zawiera informacje o użytkowniku "
                    f"(waga, cel, kontuzja, trening, sprzęt, sen, dieta, osiągnięcia)? "
                    f"Odpowiedz tylko: tak lub nie.\n\n{user_message}"
                }]
            )
        )
        return "tak" in response.content[0].text.lower()
    except Exception as e:
        print(f"[CLASSIFIER] Błąd: {e} — pomijam Uszatka")
        return False


async def background_tasks(user_id: str, user_message: str, agent_response: str, user_profile: dict):
    """Uruchamia Uszatka (gdy classifier wykryje info o userze) i Blachę (gdy >=15 nowych wiad.)."""
    if await _should_run_extraction(user_message):
        await run_in_threadpool(run_extraction_agent, user_id, user_message, agent_response, user_profile)

    unsummarized = await run_in_threadpool(get_unsummarized_count, user_id)
    if unsummarized >= 15:
        await run_in_threadpool(run_summarizer_agent, user_id)


DAILY_LIMIT     = int(os.getenv("RATE_DAILY_LIMIT", "100"))
PER_MINUTE_LIMIT = int(os.getenv("RATE_PER_MINUTE_LIMIT", "5"))


async def check_rate_limit(user_id: str):
    """
    Sprawdza rate limit: max DAILY_LIMIT wiadomości dziennie + max PER_MINUTE_LIMIT na minutę.
    Per-minutowy limit jest atomowy: liczy DB + in-flight requesty pod lockiem
    żeby uniknąć race condition przy concurrent requestach.
    Po powrocie z tej funkcji _in_flight[user_id] jest zwiększony o 1 —
    wywołujący MUSI wywołać _release_rate_limit_claim() po zakończeniu requestu.
    Limity konfigurowalne przez env: RATE_DAILY_LIMIT, RATE_PER_MINUTE_LIMIT.
    """
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat()
    minute_ago = (now - timedelta(minutes=1)).isoformat()

    daily = await run_in_threadpool(
        lambda: supabase.table("messages")
            .select("id", count="exact")
            .eq("user_id", user_id).eq("role", "user")
            .gte("created_at", day_ago).execute()
    )
    if daily.count and daily.count >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Dzienny limit wiadomości wyczerpany. Wróć jutro."
        )

    per_minute = await run_in_threadpool(
        lambda: supabase.table("messages")
            .select("id", count="exact")
            .eq("user_id", user_id).eq("role", "user")
            .gte("created_at", minute_ago).execute()
    )
    db_count = per_minute.count or 0

    # Atomowe sprawdzenie: DB count + in-flight musi być < PER_MINUTE_LIMIT
    async with _rate_lock:
        in_flight = _in_flight.get(user_id, 0)
        if db_count + in_flight >= PER_MINUTE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Za dużo wiadomości naraz. Poczekaj chwilę."
            )
        _in_flight[user_id] = in_flight + 1


def _release_rate_limit_claim(user_id: str):
    """Zwalnia slot w_in_flight po zakończeniu requestu."""
    _in_flight[user_id] = max(0, _in_flight.get(user_id, 0) - 1)


@router.post("/")
async def chat(
    request: Request,
    body: ChatRequest,
    user_id: str = Depends(require_active_subscription)
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Wiadomość nie może być pusta")
    if len(body.message) > 2000:
        raise HTTPException(status_code=400, detail="Wiadomość za długa (max 2000 znaków)")

    # get_user_profile przed check_rate_limit — jeśli tu wybuchnie, claim nie był ustawiony
    user_profile = await run_in_threadpool(get_user_profile, user_id)
    await check_rate_limit(user_id)  # od tu _in_flight[user_id] += 1

    async def generate():
        full_response = ""
        agent_exception = None

        async def run_agent():
            nonlocal full_response, agent_exception
            try:
                async for token in stream_agent(user_id, body.message, user_profile=user_profile):
                    full_response += token
            except Exception as e:
                agent_exception = e

        agent_task = asyncio.create_task(run_agent())

        try:
            # Co 20s keepalive żeby Railway/proxy nie zamknęło połączenia
            # (szczególnie ważne przy generowaniu planu — 3 wywołania Claude)
            while not agent_task.done():
                if await request.is_disconnected():
                    agent_task.cancel()
                    # Blacha musi się odpalić mimo disconnectu — zlecamy background
                    # task z tym co zebraliśmy, żeby Blacha miała szansę uruchomić się
                    asyncio.create_task(background_tasks(user_id, body.message, full_response, user_profile))
                    return
                try:
                    await asyncio.wait_for(asyncio.shield(agent_task), timeout=20.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _release_rate_limit_claim(user_id)

        if agent_exception:
            yield f"data: {json.dumps({'error': str(agent_exception)})}\n\n"
            return

        if full_response:
            yield f"data: {json.dumps({'token': full_response})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"
        asyncio.create_task(background_tasks(user_id, body.message, full_response, user_profile))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/session-end")
async def session_end(body: SessionEndRequest, bg: BackgroundTasks):
    """Wywoływany przez frontend przy zamknięciu strony (beforeunload + sendBeacon).
    Odpala Blachę jeśli zostały niespodsumowane wiadomości (< 15, bo >= 15 obsługuje per-message trigger).
    Token idzie w body bo sendBeacon nie obsługuje custom headers.
    """
    try:
        response = supabase.auth.get_user(body.token)
        if not response.user:
            return {"status": "unauthorized"}
        user_id = response.user.id
    except Exception:
        return {"status": "unauthorized"}

    unsummarized = await run_in_threadpool(get_unsummarized_count, user_id)
    if unsummarized <= 0 or unsummarized >= 15:
        return {"status": "skipped"}

    # Cooldown — jeśli Blacha działała < 30 min temu, pomijamy
    summary = supabase.table("conversation_summaries")\
        .select("updated_at")\
        .eq("user_id", user_id)\
        .limit(1)\
        .execute()

    if summary.data and summary.data[0].get("updated_at"):
        last_updated = datetime.fromisoformat(
            summary.data[0]["updated_at"].replace("Z", "+00:00")
        )
        if (datetime.now(timezone.utc) - last_updated) < timedelta(minutes=30):
            return {"status": "cooldown"}

    bg.add_task(run_summarizer_agent, user_id)
    print(f"[SESSION-END] Odpalam Blachę dla user: {user_id[:8]}... ({unsummarized} wiad.)")
    return {"status": "ok"}
