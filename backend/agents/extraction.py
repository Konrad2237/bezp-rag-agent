import json
from config import claude_client, supabase

EXTRACTION_PROMPT = """Jesteś systemem ekstrakcji danych. Przeanalizuj ostatnią wymianę wiadomości i zdecyduj czy pojawiły się nowe ważne informacje o użytkowniku.

AKTUALNY PROFIL UŻYTKOWNIKA:
{user_profile}

OSTATNIA WYMIANA WIADOMOŚCI:
User: {user_message}
Agent: {agent_response}

════════════════════════════════════════
CO JEST WARTE ZAPISANIA
════════════════════════════════════════

Zapisuj jeśli użytkownik podał lub zmienił:
- Wagę ciała, wzrost, wiek
- Cel treningowy (masa / redukcja / siła / kondycja)
- Liczbę dni treningowych
- Nową kontuzję lub dolegliwość
- Wyzdrowienie z kontuzji
- Nowe ograniczenia
- Osiągnięcie treningowe (rekord, pierwszy pull-up itp.)
- Informację o jakości snu (pole: jakosc_snu)
- Informację o poziomie stresu (pole: poziom_stresu)
- Informację o diecie (pole: dieta)
- Informację o codziennej aktywności (pole: aktywnosc_codzienna)
- Przeszłe kontuzje (pole: kontuzje_przeszle)
- Leki (pole: leki)

WAŻNE: Rozróżniaj wagę ciała od ciężaru treningowego:
- "Ważę X kg" → waga ciała → pole: waga
- "Podnoszę X kg / robię X na ławce" → osiągnięcie → pole: osiagniecia

NIE ZAPISUJ:
- Pytań o technikę (wiedza ogólna, nie dane o userze)
- Jednorazowych sytuacji ("dzisiaj słabo spałem") chyba że regularny problem
- Emocji chwilowych

WYKRYWANIE KONFLIKTÓW:
Oznacz konflikt jeśli:
- Zmiana wagi ciała > 10kg vs profil
- Zmiana celu (np. z masy na redukcję)

KONTUZJE — ZAWSZE ZAPISUJ, nawet jeśli nie pewien czy trwałe.

════════════════════════════════════════
FORMAT ODPOWIEDZI — WYŁĄCZNIE JSON
════════════════════════════════════════

Jeśli nie ma nic do zapisania:
{{"has_updates": false}}

Jeśli są aktualizacje:
{{"has_updates": true, "updates": {{"pole": "wartość"}}, "conflict_with_profile": false, "conflict_description": null}}

Jeśli konflikt:
{{"has_updates": true, "updates": {{"pole": "wartość"}}, "conflict_with_profile": true, "conflict_description": "Opis konfliktu"}}

Możliwe pola w updates:
waga, wzrost, wiek, cel, dni_treningowe, czas_treningu, miejsce_treningu,
dostepny_sprzet, kontuzje, kontuzje_przeszle, ograniczenia, leki,
osiagniecia, notatki, jakosc_snu, poziom_stresu, dieta, aktywnosc_codzienna, poziom"""


def run_extraction_agent(user_id: str, user_message: str, agent_response: str, user_profile: dict):
    """
    Extraction Agent — uruchamiany w tle po każdej odpowiedzi agenta.
    Wyciąga info o userze z rozmowy i aktualizuje profil.
    """
    try:
        # Kompaktowy JSON — oszczędność ~50% tokenów vs indent=2
        profile_str = json.dumps(user_profile, ensure_ascii=False, separators=(',', ':'))

        prompt = EXTRACTION_PROMPT.format(
            user_profile=profile_str,
            user_message=user_message,
            agent_response=agent_response,
        )

        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()

        # Usuń backticki jeśli są
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            raw = raw.rsplit("```", 1)[0].strip()

        data = json.loads(raw)

        if not data.get("has_updates"):
            print(f"[EXTRACTION] Brak aktualizacji profilu")
            return

        updates = data.get("updates", {})
        conflict = data.get("conflict_with_profile", False)
        conflict_desc = data.get("conflict_description")

        if conflict:
            supabase.table("pending_conflicts").insert({
                "user_id": user_id,
                "field": list(updates.keys())[0] if updates else "unknown",
                "old_value": str(user_profile.get(list(updates.keys())[0], "")) if updates else "",
                "new_value": str(list(updates.values())[0]) if updates else "",
                "description": conflict_desc,
                "resolved": False,
            }).execute()
            print(f"[EXTRACTION] Konflikt wykryty: {conflict_desc}")
            return

        if updates:
            for field, new_value in updates.items():
                old_value = user_profile.get(field, "")
                supabase.table("profile_changes").insert({
                    "user_id": user_id,
                    "field": field,
                    "old_value": str(old_value) if old_value else "",
                    "new_value": str(new_value),
                    "source": "extraction_agent",
                }).execute()

            supabase.table("user_profiles")\
                .update(updates)\
                .eq("user_id", user_id)\
                .execute()

            print(f"[EXTRACTION] Zaktualizowano profil: {list(updates.keys())}")

    except json.JSONDecodeError as e:
        print(f"[EXTRACTION] Błąd parsowania JSON: {e}")
    except Exception as e:
        print(f"[EXTRACTION] Błąd: {e}")
