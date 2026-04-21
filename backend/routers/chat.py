from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from middleware import get_current_user
from agents.graph import stream_agent
from agents.extraction import run_extraction_agent
from agents.summarizer import run_summarizer_agent
from services.memory import get_user_profile, get_unsummarized_count
from config import supabase, claude_client
from datetime import datetime, timezone, timedelta
import asyncio
import json

router = APIRouter()


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


def check_rate_limit(user_id: str):
    """
    Sprawdza rate limit: max 30 wiadomości dziennie + max 5 na minutę.
    Rzuca HTTPException 429 jeśli limit przekroczony.
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat()
    minute_ago = (now - timedelta(minutes=1)).isoformat()

    daily = supabase.table("messages")\
        .select("id", count="exact")\
        .eq("user_id", user_id)\
        .eq("role", "user")\
        .gte("created_at", day_ago)\
        .execute()

    if daily.count and daily.count >= 100:
        raise HTTPException(
            status_code=429,
            detail="Dzienny limit wiadomości wyczerpany. Wróć jutro."
        )

    per_minute = supabase.table("messages")\
        .select("id", count="exact")\
        .eq("user_id", user_id)\
        .eq("role", "user")\
        .gte("created_at", minute_ago)\
        .execute()

    if per_minute.count and per_minute.count >= 5:
        raise HTTPException(
            status_code=429,
            detail="Za dużo wiadomości naraz. Poczekaj chwilę."
        )


@router.post("/")
async def chat(
    body: ChatRequest,
    user_id: str = Depends(get_current_user)
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Wiadomość nie może być pusta")
    if len(body.message) > 2000:
        raise HTTPException(status_code=400, detail="Wiadomość za długa (max 2000 znaków)")

    check_rate_limit(user_id)
    user_profile = await run_in_threadpool(get_user_profile, user_id)

    async def generate():
        full_response = ""
        agent_exception = None

        async def run_agent():
            nonlocal full_response, agent_exception
            try:
                async for token in stream_agent(user_id, body.message):
                    full_response += token
            except Exception as e:
                agent_exception = e

        agent_task = asyncio.create_task(run_agent())

        # Co 20s wysyłaj keepalive żeby Railway/proxy nie zamknęło połączenia
        # (szczególnie ważne przy generowaniu planu — 3 wywołania Claude)
        while not agent_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(agent_task), timeout=20.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

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
