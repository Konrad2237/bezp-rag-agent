import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import supabase, supabase_admin
from services.memory import get_profile_changes as _fetch_profile_changes


BLACHA_SYSTEM = """Jesteś Blacha — piszesz podsumowanie rozmów użytkownika z trenerem Pitbul.

ZASADY
Max 250 słów. Pisz w trzeciej osobie ("User..."). Styl telegraficzny — fakty, nie opisy.
Zachowaj: postępy treningowe, kontuzje, zmiany celu, kiedy i dlaczego generowano plan, preferencje, o co Pitbul już pytał (żeby nie pytać dwa razy).
Usuń: pytania o technikę, ogólne rozmowy, info które są już w profilu usera.

Zwróć TYLKO tekst podsumowania, bez żadnych komentarzy ani nagłówków."""


_blacha_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=400,
)


def _get_recent_messages(user_id: str, limit: int = 15) -> str:
    result = supabase.table("messages")\
        .select("role, content, created_at")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    if not result.data:
        return "Brak wiadomości."

    msgs = list(reversed(result.data))
    return "\n".join(f"{m['role'].upper()} ({m['created_at'][:10]}): {m['content']}" for m in msgs)


def run_summarizer_agent(user_id: str) -> None:
    """Blacha — kondensuje historię rozmów do podsumowania. Jeden LLM call, bez tool calls."""
    try:
        print(f"\n[BLACHA] Aktualizuję podsumowanie dla user: {user_id[:8]}...")

        summary_res = supabase.table("conversation_summaries")\
            .select("id, summary_text, messages_summarized")\
            .eq("user_id", user_id)\
            .limit(1)\
            .execute()

        previous_summary = ""
        messages_summarized = 0
        summary_id = None
        if summary_res.data:
            previous_summary = summary_res.data[0].get("summary_text", "") or ""
            messages_summarized = summary_res.data[0].get("messages_summarized", 0) or 0
            summary_id = summary_res.data[0].get("id")

        recent_messages = _get_recent_messages(user_id, limit=15)
        profile_changes = _fetch_profile_changes(user_id, limit=10)

        human_content = f"""POPRZEDNIE PODSUMOWANIE:
{previous_summary or "Brak poprzedniego podsumowania."}

OSTATNIE WIADOMOŚCI:
{recent_messages}

OSTATNIE ZMIANY PROFILU:
{profile_changes}"""

        response = _blacha_model.invoke([
            SystemMessage(content=BLACHA_SYSTEM),
            HumanMessage(content=human_content),
        ])

        summary_text = response.content
        if isinstance(summary_text, list):
            summary_text = " ".join(b.get("text", "") for b in summary_text if isinstance(b, dict))
        summary_text = summary_text.strip()

        if summary_id:
            supabase.table("conversation_summaries").update({
                "summary_text": summary_text,
                "messages_summarized": messages_summarized + 15,
                "updated_at": "now()",
            }).eq("id", summary_id).execute()
        else:
            supabase_admin.table("conversation_summaries").insert({
                "user_id": user_id,
                "summary_text": summary_text,
                "messages_summarized": 15,
            }).execute()

        print(f"[BLACHA] Podsumowanie zapisane ({len(summary_text.split())} słów)")

    except Exception as e:
        print(f"[BLACHA] Błąd: {e}")
