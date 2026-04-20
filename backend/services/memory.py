from config import supabase, supabase_admin
from datetime import datetime, timezone
import json


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


def get_plan_history(user_id: str, limit: int = 5) -> str:
    """Zwraca skróconą historię planów treningowych usera."""
    result = supabase_admin.table("plan_history")\
        .select("plan_data, source, generation_reason, created_at")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    if not result.data:
        return "Brak historii planów — to będzie pierwszy plan użytkownika."

    lines = []
    for i, row in enumerate(result.data, 1):
        plan = row["plan_data"]
        exercises = []
        for day in plan.get("days", [])[:2]:
            for ex in day.get("exercises", [])[:3]:
                exercises.append(ex.get("name", ""))
        ex_str = ", ".join(exercises[:6]) if exercises else "brak"
        lines.append(
            f"Plan {i} ({row['created_at'][:10]}, {row.get('source', '?')}): "
            f"{plan.get('plan_name', '?')} — cel: {plan.get('goal', '?')}, "
            f"{plan.get('frequency_per_week', '?')}x/tydzień. "
            f"Przykładowe ćwiczenia: {ex_str}."
        )

    return "\n".join(lines)


def save_to_plan_history(user_id: str, plan_data: dict, source: str, generation_reason: str = "") -> None:
    """Zapisuje snapshot planu do historii."""
    supabase_admin.table("plan_history").insert({
        "user_id": user_id,
        "plan_data": plan_data,
        "source": source,
        "generation_reason": generation_reason,
    }).execute()


def get_unsummarized_count(user_id: str) -> int:
    """Zwraca liczbę wiadomości od ostatniego podsumowania."""
    summary = supabase.table("conversation_summaries")\
        .select("messages_summarized")\
        .eq("user_id", user_id)\
        .limit(1)\
        .execute()

    messages_summarized = 0
    if summary.data:
        messages_summarized = summary.data[0].get("messages_summarized", 0) or 0

    total = get_message_count(user_id)
    return max(0, total - messages_summarized)


def get_profile_changes(user_id: str, limit: int = 10) -> str:
    """Zwraca ostatnie zmiany w profilu usera zapisane przez Uszatka."""
    result = supabase.table("profile_changes")\
        .select("field, old_value, new_value, created_at")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    if not result.data:
        return "Brak zmian w profilu."

    lines = []
    for r in result.data:
        lines.append(
            f"- {r['created_at'][:10]}: {r['field']}: "
            f"'{r.get('old_value', '?')}' → '{r['new_value']}'"
        )
    return "\n".join(lines)


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
