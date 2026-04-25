import json
import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import supabase, supabase_admin


USZATEK_SYSTEM = """Jesteś Uszatek — ekstrahujesz dane użytkownika z rozmowy z trenerem Pitbul.

CO ZAPISYWAĆ
Zapisuj gdy user podał lub zmienił: wagę ciała, wzrost, wiek, cel treningowy, liczbę dni, czas treningu, nową kontuzję lub dolegliwość (ZAWSZE), poziom zaawansowania, osiągnięcia treningowe, jakość snu, poziom stresu, dietę, aktywność codzienną.
NIE ZAPISUJ: pytań o technikę (wiedza ogólna), jednorazowych sytuacji ("dzisiaj słabo spałem" — chyba że regularny problem), emocji chwilowych.

WAGA vs CIĘŻAR: "Ważę X kg" / "zrzuciłem do X" → pole waga. "Robię X na ławce" / "wziąłem X" → pole osiagniecia. W razie wątpliwości — nie aktualizuj wagi.

KONFLIKTY: użyj conflicts gdy nowa wartość jest sprzeczna z profilem, zmiana wagi >10kg lub zmiana celu treningowego (np. masa → redukcja). Małe zmiany → updates.

DOSTĘPNE POLA: waga, wzrost, wiek, cel, dni_treningowe, czas_treningu, miejsce_treningu, dostepny_sprzet, kontuzje, kontuzje_przeszle, ograniczenia, leki, osiagniecia, notatki, jakosc_snu, poziom_stresu, dieta, aktywnosc_codzienna, poziom

FORMAT — WYŁĄCZNIE JSON, bez żadnego tekstu przed ani po:
{"updates": [{"field": "waga", "value": "85kg"}], "conflicts": [{"field": "cel", "old_value": "masa", "new_value": "redukcja", "description": "User zmienił cel"}]}

Jeśli nic do zapisania: {"updates": [], "conflicts": []}"""


_uszatek_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=400,
)


def run_extraction_agent(user_id: str, user_message: str, agent_response: str, user_profile: dict) -> None:
    """Uszatek — ekstrahuję dane z rozmowy i aktualizuję profil. Jeden LLM call, bez tool calls."""
    try:
        print(f"\n[USZATEK] Analizuję dla user: {user_id[:8]}...")

        profile_str = json.dumps(user_profile, ensure_ascii=False, separators=(',', ':'))
        human_content = f"""AKTUALNY PROFIL: {profile_str}

OSTATNIA WYMIANA:
User: {user_message}
Pitbul: {agent_response}"""

        response = _uszatek_model.invoke([
            SystemMessage(content=USZATEK_SYSTEM),
            HumanMessage(content=human_content),
        ])

        raw = response.content
        if isinstance(raw, list):
            raw = " ".join(b.get("text", "") for b in raw if isinstance(b, dict))
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[USZATEK] Błąd parsowania JSON: {e} — pomijam")
            return

        updates = {u["field"]: u["value"] for u in result.get("updates", []) if u.get("field") and u.get("value")}
        conflicts = result.get("conflicts", [])

        if updates:
            fields_str = ", ".join(updates.keys())
            current = supabase.table("user_profiles").select(fields_str).eq("user_id", user_id).execute()
            old_vals = current.data[0] if current.data else {}

            supabase_admin.table("user_profiles").update(updates).eq("user_id", user_id).execute()

            audit_rows = [{
                "user_id": user_id,
                "field": f,
                "old_value": str(old_vals.get(f, "") or ""),
                "new_value": str(v),
                "source": "extraction_agent",
            } for f, v in updates.items()]
            supabase_admin.table("profile_changes").insert(audit_rows).execute()

            for f, v in updates.items():
                print(f"[USZATEK] {f}: '{old_vals.get(f, '')}' → '{v}'")

        for c in conflicts:
            if not c.get("field"):
                continue
            supabase_admin.table("pending_conflicts").insert({
                "user_id": user_id,
                "field": c["field"],
                "old_value": c.get("old_value", ""),
                "new_value": c.get("new_value", ""),
                "description": c.get("description", ""),
                "resolved": False,
            }).execute()
            print(f"[USZATEK] Konflikt: {c['field']} '{c.get('old_value')}' → '{c.get('new_value')}'")

        if not updates and not conflicts:
            print(f"[USZATEK] Nic do zapisania")

    except Exception as e:
        print(f"[USZATEK] Błąd: {e}")
