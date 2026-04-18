from config import supabase, supabase_admin
from datetime import datetime, timezone


def get_or_create_session(user_id: str) -> str:
    result = supabase.table("conversation_sessions")\
        .select("*")\
        .eq("user_id", user_id)\
        .eq("is_active", True)\
        .order("last_activity_at", desc=True)\
        .limit(1)\
        .execute()

    if result.data:
        session = result.data[0]
        last_activity = datetime.fromisoformat(
            session["last_activity_at"].replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)
        diff_minutes = (now - last_activity).total_seconds() / 60

        if diff_minutes <= 30:
            return session["id"]
        else:
            supabase.table("conversation_sessions")\
                .update({"is_active": False})\
                .eq("id", session["id"])\
                .execute()

    new_session = supabase_admin.table("conversation_sessions").insert({
        "user_id": user_id,
        "is_active": True,
        "message_count": 0,
    }).execute()

    return new_session.data[0]["id"]


def get_conversation_history(user_id: str, limit: int = 20) -> list[dict]:
    """Zwraca ostatnie N wiadomości użytkownika (niezależnie od sesji)."""
    result = supabase.table("messages")\
        .select("role, content")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    data = result.data or []
    return list(reversed(data))


def get_user_profile(user_id: str) -> dict:
    result = supabase.table("user_profiles")\
        .select("*")\
        .eq("user_id", user_id)\
        .limit(1)\
        .execute()

    return result.data[0] if result.data else {}


def get_memory_summary(user_id: str) -> str:
    result = supabase.table("conversation_summaries")\
        .select("summary_text")\
        .eq("user_id", user_id)\
        .limit(1)\
        .execute()

    if result.data and result.data[0]["summary_text"]:
        return result.data[0]["summary_text"]
    return ""


def get_message_count(user_id: str) -> int:
    """Zwraca łączną liczbę wiadomości usera (do triggerowania Summarizera)."""
    result = supabase.table("messages")\
        .select("id", count="exact")\
        .eq("user_id", user_id)\
        .eq("role", "user")\
        .execute()

    return result.count or 0


def save_messages(user_id: str, session_id: str, user_message: str, agent_response: str, prompt_version: str = "v1.0"):
    """Zapisuje wiadomości do bazy i aktualizuje sesję."""
    supabase_admin.table("messages").insert([
        {
            "user_id": user_id,
            "session_id": session_id,
            "role": "user",
            "content": user_message,
            "prompt_version": prompt_version,
        },
        {
            "user_id": user_id,
            "session_id": session_id,
            "role": "assistant",
            "content": agent_response,
            "prompt_version": prompt_version,
        }
    ]).execute()

    # Aktualizuj sesję
    current = supabase.table("conversation_sessions")\
        .select("message_count")\
        .eq("id", session_id)\
        .execute()

    current_count = current.data[0]["message_count"] if current.data else 0

    supabase.table("conversation_sessions")\
        .update({
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
            "message_count": current_count + 2,
        })\
        .eq("id", session_id)\
        .execute()
