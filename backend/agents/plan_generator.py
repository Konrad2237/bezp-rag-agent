import json
import os
import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from services.rag import search_knowledge as rag_search
from services.search import search_web as web_search
from services.memory import (
    get_user_profile,
    get_memory_summary,
    get_plan_history as _fetch_plan_history,
    save_to_plan_history,
)
from config import supabase_admin


SZYBCIOR_SYSTEM_PROMPT = """Jesteś Szybcior — wyspecjalizowany agent generowania planów treningowych w systemie "Bez Pierdolenia".

PROFIL UŻYTKOWNIKA:
{user_profile}

KONTEKST Z ROZMÓW:
{memory_summary}

POWÓD GENEROWANIA:
{generation_reason}

════════════════════════════════════════
TWÓJ PROCES
════════════════════════════════════════

1. Wywołaj get_plan_history — sprawdź poprzednie plany żeby nie powtarzać ćwiczeń
2. Wywołaj search_knowledge — znajdź odpowiednie ćwiczenia w bazie wiedzy
3. Jeśli baza wiedzy niewystarczająca — wywołaj search_web
4. Na podstawie zebranych danych wygeneruj plan JSON jako OSTATNIĄ odpowiedź (bez tekstu przed ani po)

════════════════════════════════════════
ZASADY TWORZENIA PLANU
════════════════════════════════════════

1. Dopasuj liczbę dni do profilu (dni_treningowe)
2. Czas 30-45 min → max 5-6 ćwiczeń; 60-90 min → 7-9 ćwiczeń
3. Uwzględnij dostępny sprzęt i miejsce treningu
4. Uwzględnij kontuzje — bezpieczne alternatywy
5. Dla początkujących: FBW > split
6. Wzorce ruchowe: push, pull, nogi, core
7. Serie × powtórzenia wg celu: masa 3-4×8-12 | siła 4-5×4-6 | redukcja 3-4×12-15
8. NIE powtarzaj ćwiczeń z poprzednich planów — sprawdź historię

════════════════════════════════════════
FORMAT KOŃCOWEJ ODPOWIEDZI — WYŁĄCZNIE JSON
════════════════════════════════════════

{{
  "plan_name": "FBW 3x tydzień — Masa",
  "goal": "masa",
  "frequency_per_week": 3,
  "duration_weeks": 4,
  "notes": "Krótki opis planu",
  "days": [
    {{
      "day_label": "Trening A",
      "scheduled_days": ["poniedziałek", "środa", "piątek"],
      "exercises": [
        {{
          "name": "Przysiad ze sztangą",
          "muscle_group": "nogi",
          "sets": 3,
          "reps": "8-10",
          "rest_seconds": 90,
          "notes": "Zejdź do równoległej"
        }}
      ]
    }}
  ]
}}"""

REQUIRED_FIELDS = ["cel", "dni_treningowe", "czas_treningu", "poziom"]


class SzybciorState(TypedDict):
    user_id: str
    generation_reason: str
    messages: Annotated[list, operator.add]
    result: dict


def check_missing_fields(profile: dict) -> list[str]:
    FIELD_LABELS = {
        "cel": "cel treningowy (masa/redukcja/siła/kondycja)",
        "dni_treningowe": "liczba dni treningowych w tygodniu",
        "czas_treningu": "dostępny czas na trening",
        "poziom": "poziom zaawansowania",
    }
    return [FIELD_LABELS[f] for f in REQUIRED_FIELDS if not profile.get(f)]


def _szybcior_setup(state: SzybciorState) -> SzybciorState:
    """Buduje initial messages z profilu i kontekstu."""
    user_id = state["user_id"]
    print(f"\n[SZYBCIOR] setup dla user: {user_id[:8]}...")

    profile = get_user_profile(user_id)
    summary = get_memory_summary(user_id)

    SKIP = {"id", "user_id", "created_at", "updated_at"}
    profile_lines = [f"- {k}: {v}" for k, v in profile.items() if v and k not in SKIP]
    profile_str = "\n".join(profile_lines) if profile_lines else "Brak danych profilu."

    system_content = SZYBCIOR_SYSTEM_PROMPT.format(
        user_profile=profile_str,
        memory_summary=summary or "Brak historii rozmów.",
        generation_reason=state["generation_reason"],
    )

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content="Wygeneruj plan treningowy. Zacznij od sprawdzenia historii planów."),
    ]
    return {**state, "messages": messages}


def _make_szybcior_tools(user_id: str):
    @tool
    def search_knowledge(query: str) -> str:
        """Przeszukuje bazę wiedzy treningowej z ebooka. Używaj do znajdowania ćwiczeń i zasad."""
        print(f"[SZYBCIOR] search_knowledge: '{query}'")
        return rag_search(query)

    @tool
    def search_web(query: str) -> str:
        """Przeszukuje internet gdy baza wiedzy nie ma wystarczających informacji."""
        print(f"[SZYBCIOR] search_web: '{query}'")
        return web_search(query)

    @tool
    def get_plan_history(reason: str = "") -> str:
        """Pobiera historię poprzednich planów treningowych — żeby nie powtarzać ćwiczeń."""
        print(f"[SZYBCIOR] get_plan_history")
        return _fetch_plan_history(user_id)

    return [search_knowledge, search_web, get_plan_history]


_szybcior_model = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=4096,
)


def _szybcior_agent(state: SzybciorState) -> SzybciorState:
    tools = _make_szybcior_tools(state["user_id"])
    model = _szybcior_model.bind_tools(tools)
    print(f"[SZYBCIOR] agent myśli...")
    response = model.invoke(state["messages"])
    return {**state, "messages": [response]}


def _szybcior_should_continue(state: SzybciorState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    # Jeśli content pusty — wymuś jeszcze jedną rundę z instrukcją
    content = last.content if hasattr(last, "content") else ""
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    if not content.strip():
        return "retry"
    return "finalize"


def _szybcior_retry(state: SzybciorState) -> SzybciorState:
    """Wymusza wygenerowanie JSON gdy agent zwrócił pustą odpowiedź."""
    from langchain_core.messages import HumanMessage as HM
    print(f"[SZYBCIOR] Pusta odpowiedź — wymuszam generowanie JSON")
    return {**state, "messages": [HM(content="Masz już wszystkie potrzebne informacje. Odpowiedz WYŁĄCZNIE JSON planu treningowego, bez żadnego tekstu przed ani po.")]}


def _szybcior_tool_dispatcher(state: SzybciorState) -> SzybciorState:
    tools = _make_szybcior_tools(state["user_id"])
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
            result = f"Błąd narzędzia: {e}"
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {**state, "messages": results}


def _szybcior_finalize(state: SzybciorState) -> SzybciorState:
    """Parsuje plan JSON z ostatniej wiadomości i zapisuje do bazy."""
    last = state["messages"][-1]
    raw = last.content if hasattr(last, "content") else ""
    if isinstance(raw, list):
        raw = " ".join(b.get("text", "") for b in raw if isinstance(b, dict))
    raw = raw.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        plan_data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[SZYBCIOR] Błąd parsowania JSON: {e}")
        return {**state, "result": {"error": f"Błąd parsowania planu: {e}"}}

    user_id = state["user_id"]
    generation_reason = state["generation_reason"]

    # Zapisz do historii planów
    save_to_plan_history(user_id, plan_data, source="szybcior", generation_reason=generation_reason)

    # Update lub insert w training_plans (aktywny plan)
    existing = supabase_admin.table("training_plans").select("id").eq("user_id", user_id).execute()
    if existing.data:
        save_res = supabase_admin.table("training_plans").update({
            "plan_data": plan_data,
            "generation_reason": generation_reason,
        }).eq("user_id", user_id).execute()
    else:
        save_res = supabase_admin.table("training_plans").insert({
            "user_id": user_id,
            "plan_data": plan_data,
            "generation_reason": generation_reason,
        }).execute()

    if not save_res.data:
        print(f"[SZYBCIOR] BŁĄD: zapis nie powiódł się")
        return {**state, "result": {"error": "Zapis planu nie powiódł się"}}

    print(f"[SZYBCIOR] Plan zapisany: {plan_data.get('plan_name', '?')}")
    return {**state, "result": {"plan": plan_data}}


# ─── GRAPH ───────────────────────────────────────────────
_builder = StateGraph(SzybciorState)
_builder.add_node("setup", _szybcior_setup)
_builder.add_node("agent", _szybcior_agent)
_builder.add_node("tools", _szybcior_tool_dispatcher)
_builder.add_node("retry", _szybcior_retry)
_builder.add_node("finalize", _szybcior_finalize)

_builder.set_entry_point("setup")
_builder.add_edge("setup", "agent")
_builder.add_conditional_edges("agent", _szybcior_should_continue, {
    "tools": "tools",
    "finalize": "finalize",
    "retry": "retry",
})
_builder.add_edge("retry", "agent")
_builder.add_edge("tools", "agent")
_builder.add_edge("finalize", END)

szybcior_graph = _builder.compile()


def run_plan_generator(user_id: str, generation_reason: str = "user poprosił o plan") -> dict:
    """
    Szybcior — generuje spersonalizowany plan treningowy.
    Zwraca dict z kluczem 'plan' lub 'missing_fields' lub 'error'.
    """
    profile = get_user_profile(user_id)
    missing = check_missing_fields(profile)
    if missing:
        print(f"[SZYBCIOR] Brakujące pola: {missing}")
        return {"missing_fields": missing}

    print(f"\n[SZYBCIOR] Generuję plan dla user: {user_id[:8]}...")
    result = szybcior_graph.invoke(
        {
            "user_id": user_id,
            "generation_reason": generation_reason,
            "messages": [],
            "result": {},
        },
        config={"recursion_limit": 10},
    )
    return result.get("result", {"error": "Brak wyniku"})
