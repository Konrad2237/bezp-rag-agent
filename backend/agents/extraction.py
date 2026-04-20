import json
import os
import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from services.rag import search_knowledge as rag_search
from config import supabase, supabase_admin


USZATEK_SYSTEM_PROMPT = """Jesteś Uszatek — agent ekstrakcji danych użytkownika w systemie "Bez Pierdolenia".

AKTUALNY PROFIL UŻYTKOWNIKA:
{user_profile}

OSTATNIA WYMIANA WIADOMOŚCI:
User: {user_message}
Pitbul: {agent_response}

════════════════════════════════════════
TWOJE ZADANIE
════════════════════════════════════════

Przeanalizuj wymianę wiadomości. Zdecyduj:
1. Czy pojawiły się nowe informacje o użytkowniku warte zapisania?
2. Jeśli tak — użyj narzędzi żeby je zapisać lub oznaczyć konflikt
3. Jeśli nie ma nic do zapisania — zakończ bez działań

════════════════════════════════════════
CO ZAPISYWAĆ
════════════════════════════════════════

Zapisuj gdy user podał lub zmienił:
- Wagę ciała, wzrost, wiek
- Cel treningowy, liczbę dni, czas treningu
- Nową kontuzję lub dolegliwość (ZAWSZE zapisuj)
- Zmianę poziomu zaawansowania
- Osiągnięcia treningowe (nowe rekordy, pierwszy pull-up itp.)
- Jakość snu, poziom stresu, dietę, aktywność codzienną

NIE ZAPISUJ:
- Pytań o technikę ćwiczeń (wiedza ogólna, nie dane o userze)
- Jednorazowych sytuacji ("dzisiaj słabo spałem") — chyba że to regularny problem
- Emocji chwilowych

════════════════════════════════════════
WAGA CIAŁA vs CIĘŻAR TRENINGOWY
════════════════════════════════════════

"Ważę X kg" / "zrzuciłem do X" → waga ciała → pole: waga
"Wziąłem X kg" / "robię X na ławce" → ciężar treningowy → pole: osiagniecia
W razie wątpliwości: NIE aktualizuj wagi ciała.

════════════════════════════════════════
KIEDY FLAGOWAĆ KONFLIKT
════════════════════════════════════════

Użyj create_conflict gdy:
- Nowa wartość sprzeczna z profilem
- Zmiana wagi ciała >10kg vs profil
- Zmiana celu treningowego (np. masa → redukcja)

Małe zmiany (dni treningowe, drobne korekty) → update_user_profile bezpośrednio.
Nie jesteś pewien czy info jest realistyczne → verify_with_knowledge.

════════════════════════════════════════
DOSTĘPNE POLA
════════════════════════════════════════

waga, wzrost, wiek, cel, dni_treningowe, czas_treningu, miejsce_treningu,
dostepny_sprzet, kontuzje, kontuzje_przeszle, ograniczenia, leki,
osiagniecia, notatki, jakosc_snu, poziom_stresu, dieta, aktywnosc_codzienna, poziom"""


class UszatekState(TypedDict):
    user_id: str
    user_message: str
    agent_response: str
    user_profile: dict
    messages: Annotated[list, operator.add]


def _make_uszatek_tools(user_id: str):
    @tool
    def update_user_profile(field: str, value: str) -> str:
        """
        Aktualizuje konkretne pole w profilu użytkownika i zapisuje do audit logu.
        field: nazwa pola (np. 'waga', 'cel', 'kontuzje')
        value: nowa wartość jako string
        """
        # Pobierz aktualną wartość świeżo z bazy
        current = supabase.table("user_profiles").select(field).eq("user_id", user_id).execute()
        old_value = ""
        if current.data and field in current.data[0]:
            old_value = str(current.data[0][field] or "")

        update_res = supabase_admin.table("user_profiles")\
            .update({field: value})\
            .eq("user_id", user_id)\
            .execute()

        if not update_res.data:
            return f"BŁĄD: Nie udało się zaktualizować {field}."

        supabase_admin.table("profile_changes").insert({
            "user_id": user_id,
            "field": field,
            "old_value": old_value,
            "new_value": str(value),
            "source": "extraction_agent",
        }).execute()

        print(f"[USZATEK] {field}: '{old_value}' → '{value}'")
        return f"Zaktualizowano {field}: '{value}'"

    @tool
    def create_conflict(field: str, old_value: str, new_value: str, description: str) -> str:
        """
        Flaguje konflikt gdy nowa informacja jest sprzeczna z profilem.
        Nie nadpisuje profilu — Pitbul zapyta usera o potwierdzenie w następnej wiadomości.
        field: nazwa pola
        old_value: obecna wartość z profilu
        new_value: nowa wartość podana przez usera
        description: opis konfliktu i pytanie dla usera
        """
        supabase_admin.table("pending_conflicts").insert({
            "user_id": user_id,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "description": description,
            "resolved": False,
        }).execute()

        print(f"[USZATEK] Konflikt: {field} '{old_value}' → '{new_value}'")
        return f"Konflikt zapisany dla pola {field}. Pitbul zapyta usera o potwierdzenie."

    @tool
    def verify_with_knowledge(claim: str) -> str:
        """
        Weryfikuje czy informacja od usera jest realistyczna.
        Przeszukuje bazę wiedzy treningowej.
        Używaj gdy nie jesteś pewien czy podana wartość jest prawdopodobna.
        """
        print(f"[USZATEK] verify_with_knowledge: '{claim}'")
        return rag_search(claim)

    return [update_user_profile, create_conflict, verify_with_knowledge]


_uszatek_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=500,
)


def _uszatek_setup(state: UszatekState) -> UszatekState:
    """Buduje initial messages."""
    profile_str = json.dumps(state["user_profile"], ensure_ascii=False, separators=(',', ':'))
    system_content = USZATEK_SYSTEM_PROMPT.format(
        user_profile=profile_str,
        user_message=state["user_message"],
        agent_response=state["agent_response"],
    )
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content="Przeanalizuj wymianę wiadomości i wykonaj potrzebne aktualizacje profilu."),
    ]
    return {**state, "messages": messages}


def _uszatek_agent(state: UszatekState) -> UszatekState:
    tools = _make_uszatek_tools(state["user_id"])
    model = _uszatek_model.bind_tools(tools)
    print(f"[USZATEK] agent myśli...")
    response = model.invoke(state["messages"])
    return {**state, "messages": [response]}


def _uszatek_should_continue(state: UszatekState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _uszatek_tool_dispatcher(state: UszatekState) -> UszatekState:
    tools = _make_uszatek_tools(state["user_id"])
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
            print(f"[USZATEK] Błąd narzędzia {tc['name']}: {e}")
            result = f"Błąd: {e}"
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {**state, "messages": results}


# ─── GRAPH ───────────────────────────────────────────────
_builder = StateGraph(UszatekState)
_builder.add_node("setup", _uszatek_setup)
_builder.add_node("agent", _uszatek_agent)
_builder.add_node("tools", _uszatek_tool_dispatcher)

_builder.set_entry_point("setup")
_builder.add_edge("setup", "agent")
_builder.add_conditional_edges("agent", _uszatek_should_continue, {
    "tools": "tools",
    END: END,
})
_builder.add_edge("tools", "agent")

uszatek_graph = _builder.compile()


def run_extraction_agent(user_id: str, user_message: str, agent_response: str, user_profile: dict) -> None:
    """
    Uszatek — wyciąga informacje o userze z rozmowy i aktualizuje profil.
    Uruchamiany w tle po każdej wiadomości (gdy classifier wykryje info o userze).
    """
    try:
        print(f"\n[USZATEK] Analizuję wiadomość dla user: {user_id[:8]}...")
        uszatek_graph.invoke(
            {
                "user_id": user_id,
                "user_message": user_message,
                "agent_response": agent_response,
                "user_profile": user_profile,
                "messages": [],
            },
            config={"recursion_limit": 10},
        )
    except Exception as e:
        print(f"[USZATEK] Błąd: {e}")
