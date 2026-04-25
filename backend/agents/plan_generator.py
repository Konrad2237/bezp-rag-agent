import json
import os
import operator
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from services.rag import search_knowledge as rag_search
from services.memory import (
    get_user_profile,
    get_memory_summary,
    get_plan_history as _fetch_plan_history,
    save_to_plan_history,
)
from config import supabase_admin


SZYBCIOR_STATIC_PROMPT = """Jesteś Szybcior — agent generowania planów treningowych w systemie Bez Pierdolenia.

Masz wszystkie potrzebne dane w kontekście: profil, historię planów i fragmenty bazy wiedzy.
Wygeneruj plan JSON jako jedyną odpowiedź — wyłącznie JSON, bez tekstu przed ani po.

ZASADY TWORZENIA PLANU
- Liczba dni = profil.dni_treningowe
- Czas 30-45 min → max 5-6 ćwiczeń; 60-90 min → 7-9 ćwiczeń
- Uwzględnij dostępny sprzęt i miejsce treningu
- Kontuzje → bezpieczne alternatywy, omijaj ćwiczenia ryzykowne dla danej dolegliwości
- Poziom początkujący → FBW zamiast split
- Wzorce ruchowe: push, pull, nogi, core
- Serie/powtórzenia wg celu: masa 3-4×8-12 | siła 4-5×4-6 | redukcja 3-4×12-15
- Historia planów jest w kontekście — wybierz inne ćwiczenia niż poprzednio

FORMAT — WYŁĄCZNIE JSON (bez żadnego tekstu przed ani po):

{
  "plan_name": "FBW 3x tydzień — Masa",
  "goal": "masa",
  "frequency_per_week": 3,
  "duration_weeks": 4,
  "notes": "Krótki opis planu",
  "days": [
    {
      "day_label": "Trening A",
      "scheduled_days": ["poniedziałek", "środa", "piątek"],
      "exercises": [
        {
          "name": "Przysiad ze sztangą",
          "muscle_group": "nogi",
          "sets": 3,
          "reps": "8-10",
          "rest_seconds": 90,
          "notes": "Zejdź do równoległej"
        }
      ]
    }
  ]
}"""

REQUIRED_FIELDS = ["cel", "dni_treningowe", "czas_treningu", "poziom"]


class SzybciorState(TypedDict):
    user_id: str
    generation_reason: str
    user_profile: dict
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


def _build_rag_query(profile: dict) -> str:
    """Buduje query RAG z profilu usera dla generowania planu."""
    goal = profile.get("cel", "trening siłowy")
    level = profile.get("poziom", "")
    equipment = profile.get("dostepny_sprzet", "")
    injuries = profile.get("kontuzje", "")
    parts = [goal, "ćwiczenia", level]
    if equipment:
        parts.append(str(equipment)[:50])
    if injuries:
        parts.append(f"omijaj {str(injuries)[:30]}")
    return " ".join(p for p in parts if p).strip()


def _szybcior_setup(state: SzybciorState) -> SzybciorState:
    """Wstrzykuje profil, historię planów i RAG w kontekst — bez żadnych tool calls w LLM."""
    user_id = state["user_id"]
    print(f"\n[SZYBCIOR] setup: {user_id[:8]}...")

    # Profil przekazany przez run_plan_generator — brak dodatkowego DB query
    profile = state["user_profile"] or get_user_profile(user_id)
    rag_query = _build_rag_query(profile)

    # Faza 2: summary, plan_history i RAG równolegle
    def _summary(): return get_memory_summary(user_id)
    def _history(): return _fetch_plan_history(user_id)
    def _rag(): return rag_search(rag_query)

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_summary = ex.submit(_summary)
        f_history = ex.submit(_history)
        f_rag = ex.submit(_rag)
        summary = f_summary.result()
        plan_history = f_history.result()
        rag_knowledge = f_rag.result()

    print(f"[SZYBCIOR] RAG query: '{rag_query[:60]}...'")

    SKIP = {"id", "user_id", "created_at", "updated_at"}
    profile_lines = [f"  {k}: {v}" for k, v in profile.items() if v and k not in SKIP]
    profile_str = "\n".join(profile_lines) if profile_lines else "Brak danych."

    dynamic_context = f"""PROFIL:
{profile_str}

BAZA WIEDZY TRENINGOWEJ (użyj tych ćwiczeń jako podstawy planu):
{rag_knowledge}

HISTORIA PLANÓW (nie powtarzaj tych samych ćwiczeń):
{plan_history}

KONTEKST ROZMÓW:
{summary or "Brak."}

POWÓD GENEROWANIA: {state["generation_reason"]}

Wygeneruj plan JSON. Wszystkie potrzebne dane masz powyżej."""

    messages = [
        SystemMessage(content=[{
            "type": "text",
            "text": SZYBCIOR_STATIC_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }]),
        HumanMessage(content=dynamic_context),
    ]
    return {**state, "messages": messages}


_szybcior_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=2048,
)


def _szybcior_agent(state: SzybciorState) -> SzybciorState:
    print(f"[SZYBCIOR] generuję plan...")
    response = _szybcior_model.invoke(state["messages"])
    return {**state, "messages": [response]}


def _szybcior_should_continue(state: SzybciorState) -> str:
    last = state["messages"][-1]
    content = last.content if hasattr(last, "content") else ""
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    if not content.strip():
        return "retry"
    return "finalize"


def _szybcior_retry(state: SzybciorState) -> SzybciorState:
    """Wymusza JSON gdy agent zwrócił pustą odpowiedź."""
    print(f"[SZYBCIOR] Pusta odpowiedź — wymuszam JSON")
    return {**state, "messages": [HumanMessage(content="Odpowiedz WYŁĄCZNIE JSON planu treningowego, bez żadnego tekstu.")]}


def _szybcior_finalize(state: SzybciorState) -> SzybciorState:
    """Parsuje JSON z odpowiedzi i zapisuje plan do bazy."""
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

    save_to_plan_history(user_id, plan_data, source="szybcior", generation_reason=generation_reason)

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
# Uproszczony graf: setup → agent → finalize (bez pętli tool calls)
_builder = StateGraph(SzybciorState)
_builder.add_node("setup", _szybcior_setup)
_builder.add_node("agent", _szybcior_agent)
_builder.add_node("retry", _szybcior_retry)
_builder.add_node("finalize", _szybcior_finalize)

_builder.set_entry_point("setup")
_builder.add_edge("setup", "agent")
_builder.add_conditional_edges("agent", _szybcior_should_continue, {
    "finalize": "finalize",
    "retry": "retry",
})
_builder.add_edge("retry", "agent")
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
            "user_profile": profile,
            "messages": [],
            "result": {},
        },
        config={"recursion_limit": 5},
    )
    return result.get("result", {"error": "Brak wyniku"})
