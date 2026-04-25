import os
import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from config import supabase, supabase_admin
from services.memory import get_profile_changes as _fetch_profile_changes


# Statyczna część — cachowana między wywołaniami w tej samej sesji
BLACHA_SYSTEM_PROMPT_STATIC = """Jesteś Blacha — agent zarządzania pamięcią w systemie Bez Pierdolenia.

TWÓJ PROCES
1. Wywołaj get_recent_messages — pobierz ostatnie wiadomości
2. Wywołaj get_profile_changes — sprawdź co Uszatek zaktualizował w profilu
3. Stwórz zaktualizowane podsumowanie i zapisz przez update_summary
4. Po zapisaniu — zakończ. Nie pisz żadnych dodatkowych wiadomości.

ZASADY PODSUMOWANIA
Max 250 słów. Pisz w trzeciej osobie ("User..."). Styl telegraficzny — fakty, nie opisy.
Zachowaj: postępy treningowe, kontuzje, zmiany celu, kiedy i dlaczego generowano plan, preferencje, o co Pitbul już pytał (żeby nie pytać dwa razy).
Usuń: pytania o technikę, ogólne rozmowy, info które są już w profilu usera."""


class BlachaState(TypedDict):
    user_id: str
    previous_summary: str
    messages: Annotated[list, operator.add]


def _make_blacha_tools(user_id: str):
    @tool
    def get_recent_messages(limit: int = 15) -> str:
        """Pobiera ostatnie wiadomości z rozmów użytkownika z Pitbulem."""
        result = supabase.table("messages")\
            .select("role, content, created_at")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()

        if not result.data:
            return "Brak wiadomości."

        msgs = list(reversed(result.data))
        lines = [f"{m['role'].upper()} ({m['created_at'][:10]}): {m['content']}" for m in msgs]
        return "\n".join(lines)

    @tool
    def get_profile_changes(limit: int = 10) -> str:
        """Pobiera ostatnie zmiany w profilu użytkownika zapisane przez Uszatka."""
        return _fetch_profile_changes(user_id, limit)

    @tool
    def update_summary(summary_text: str) -> str:
        """Zapisuje zaktualizowane podsumowanie rozmów do bazy danych."""
        summary_res = supabase.table("conversation_summaries")\
            .select("id, messages_summarized")\
            .eq("user_id", user_id)\
            .limit(1)\
            .execute()

        if summary_res.data:
            summary_id = summary_res.data[0]["id"]
            messages_summarized = summary_res.data[0].get("messages_summarized", 0) or 0
            supabase.table("conversation_summaries")\
                .update({
                    "summary_text": summary_text,
                    "messages_summarized": messages_summarized + 15,
                    "updated_at": "now()",
                })\
                .eq("id", summary_id)\
                .execute()
        else:
            supabase_admin.table("conversation_summaries").insert({
                "user_id": user_id,
                "summary_text": summary_text,
                "messages_summarized": 15,
            }).execute()

        print(f"[BLACHA] Podsumowanie zapisane ({len(summary_text.split())} słów)")
        return "Podsumowanie zapisane pomyślnie."

    return [get_recent_messages, get_profile_changes, update_summary]


_blacha_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=600,
)


def _blacha_setup(state: BlachaState) -> BlachaState:
    """Buduje initial messages. System prompt cachowany, previous_summary w human message."""
    previous_summary = state["previous_summary"] or "Brak poprzedniego podsumowania."
    messages = [
        SystemMessage(content=[{
            "type": "text",
            "text": BLACHA_SYSTEM_PROMPT_STATIC,
            "cache_control": {"type": "ephemeral"},
        }]),
        HumanMessage(content=f"POPRZEDNIE PODSUMOWANIE:\n{previous_summary}\n\nPobierz wiadomości i zaktualizuj podsumowanie."),
    ]
    return {**state, "messages": messages}


def _blacha_agent(state: BlachaState) -> BlachaState:
    tools = _make_blacha_tools(state["user_id"])
    model = _blacha_model.bind_tools(tools)
    print(f"[BLACHA] agent myśli...")
    response = model.invoke(state["messages"])
    return {**state, "messages": [response]}


def _blacha_should_continue(state: BlachaState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _blacha_after_tools(state: BlachaState) -> str:
    """Po update_summary kończ od razu — nie wracaj do agenta po potwierdzenie."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage) and "Podsumowanie zapisane" in str(msg.content):
            return END
    return "agent"


def _blacha_tool_dispatcher(state: BlachaState) -> BlachaState:
    tools = _make_blacha_tools(state["user_id"])
    tool_map = {t.name: t for t in tools}
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        fn = tool_map.get(tc["name"])
        if fn is None:
            results.append(ToolMessage(content=f"Nieznane narzędzie: {tc['name']}", tool_call_id=tc["id"]))
            continue
        try:
            result = fn.invoke(tc["args"])
        except Exception as e:
            print(f"[BLACHA] Błąd narzędzia {tc['name']}: {e}")
            result = f"Błąd: {e}"
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {**state, "messages": results}


# ─── GRAPH ───────────────────────────────────────────────
_builder = StateGraph(BlachaState)
_builder.add_node("setup", _blacha_setup)
_builder.add_node("agent", _blacha_agent)
_builder.add_node("tools", _blacha_tool_dispatcher)

_builder.set_entry_point("setup")
_builder.add_edge("setup", "agent")
_builder.add_conditional_edges("agent", _blacha_should_continue, {
    "tools": "tools",
    END: END,
})
_builder.add_conditional_edges("tools", _blacha_after_tools, {
    "agent": "agent",
    END: END,
})

blacha_graph = _builder.compile()


def run_summarizer_agent(user_id: str) -> None:
    """
    Blacha — kondensuje historię rozmów do podsumowania.
    Uruchamiany w tle gdy nazbierało się >=15 nowych wiadomości od ostatniego podsumowania.
    """
    try:
        print(f"\n[BLACHA] Aktualizuję podsumowanie dla user: {user_id[:8]}...")

        summary_res = supabase.table("conversation_summaries")\
            .select("summary_text")\
            .eq("user_id", user_id)\
            .limit(1)\
            .execute()
        previous_summary = ""
        if summary_res.data:
            previous_summary = summary_res.data[0].get("summary_text", "") or ""

        blacha_graph.invoke(
            {
                "user_id": user_id,
                "previous_summary": previous_summary,
                "messages": [],
            },
            config={"recursion_limit": 8},
        )
    except Exception as e:
        print(f"[BLACHA] Błąd: {e}")
