import json
import os
import anthropic
from services.rag import search_knowledge
from services.memory import get_user_profile, get_memory_summary
from config import supabase, supabase_admin

PROMPT_04 = """Jesteś Szybcior — system generowania planów treningowych. Twoim zadaniem jest
stworzenie spersonalizowanego planu na podstawie profilu użytkownika i dostępnej wiedzy.

PROFIL UŻYTKOWNIKA:
{user_profile}

KONTEKST Z HISTORII ROZMÓW:
{memory_summary}

WIEDZA Z BAZY MATERIAŁÓW:
{rag_context}

POWÓD GENEROWANIA PLANU:
{generation_reason}

════════════════════════════════════════
ZASADY TWORZENIA PLANU
════════════════════════════════════════

1. Dopasuj plan do liczby dni treningowych z profilu.
2. Dopasuj czas treningu — jeśli user ma 30-45 min, max 5-6 ćwiczeń.
   Jeśli 60-90 min, może być 7-9.
3. Uwzględnij DOSTĘPNY SPRZĘT — nie proponuj ćwiczeń na maszynie
   jeśli user trenuje w domu z hantlami.
4. Uwzględnij MIEJSCE TRENINGU — siłownia domowa ma inne możliwości
   niż komercyjna.
5. Uwzględnij kontuzje — omijaj ćwiczenia które mogą je pogorszyć,
   proponuj bezpieczne alternatywy.
6. Dla początkujących (poziom: poczatkujacy): FBW (Full Body Workout)
   jest lepszym wyborem niż split. Nie komplikuj.
7. Liczba ćwiczeń per sesja: 5-7 dla początkujących, max 9 dla
   średniozaawansowanych.
8. Zawsze uwzględnij główne wzorce ruchowe: push, pull, nogi, core.
9. Serie i powtórzenia dopasuj do celu:
   - Masa: 3-4 serie × 8-12 powtórzeń
   - Siła: 4-5 serii × 4-6 powtórzeń
   - Kondycja/redukcja: 3-4 serie × 12-15 powtórzeń
10. Używaj tylko wiedzy z bazy materiałów dla konkretnych ćwiczeń.
    Jeśli baza jest pusta — użyj ogólnej wiedzy o treningu siłowym,
    ale trzymaj się sprawdzonych, podstawowych ćwiczeń.

════════════════════════════════════════
FORMAT ODPOWIEDZI — WYŁĄCZNIE JSON
════════════════════════════════════════

Odpowiedz WYŁĄCZNIE w formacie JSON. Bez tekstu przed ani po.

{{
  "plan_name": "FBW 3x tydzień — Masa",
  "goal": "masa",
  "frequency_per_week": 3,
  "duration_weeks": 4,
  "notes": "Plan dla początkującego, skupiony na podstawowych wzorcach ruchowych.",
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
          "notes": "Zejdź do równoległej, kolana nad palcami"
        }}
      ]
    }}
  ]
}}
"""

REQUIRED_FIELDS = ["cel", "dni_treningowe", "czas_treningu", "poziom"]


def check_missing_fields(profile: dict) -> list[str]:
    """Sprawdza czy profil ma wystarczające dane do wygenerowania planu."""
    FIELD_LABELS = {
        "cel": "cel treningowy (masa/redukcja/siła/kondycja)",
        "dni_treningowe": "liczba dni treningowych w tygodniu",
        "czas_treningu": "dostępny czas na trening",
        "poziom": "poziom zaawansowania",
    }
    return [FIELD_LABELS[f] for f in REQUIRED_FIELDS if not profile.get(f)]


def run_plan_generator(user_id: str, generation_reason: str = "user poprosił o plan") -> dict:
    """
    Szybcior — generuje spersonalizowany plan treningowy.
    Zwraca dict z kluczem 'plan' (JSON) lub 'missing_fields' (lista brakujących pól).
    """
    print(f"\n[SZYBCIOR] Generuję plan dla user: {user_id[:8]}...")

    profile = get_user_profile(user_id)
    missing = check_missing_fields(profile)
    if missing:
        print(f"[SZYBCIOR] Brakujące pola: {missing}")
        return {"missing_fields": missing}

    summary = get_memory_summary(user_id)

    # RAG — pobierz wiedzę o planach treningowych
    rag_context = search_knowledge("plan treningowy ćwiczenia progresja serie powtórzenia")
    print(f"[SZYBCIOR] RAG pobrany")

    # Zbuduj profil string
    SKIP_FIELDS = {"id", "user_id", "created_at", "updated_at"}
    profile_lines = [
        f"- {k}: {v}" for k, v in profile.items()
        if v and k not in SKIP_FIELDS
    ]
    profile_str = "\n".join(profile_lines)

    prompt = PROMPT_04.format(
        user_profile=profile_str,
        memory_summary=summary or "Brak historii rozmów.",
        rag_context=rag_context,
        generation_reason=generation_reason,
    )

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    print(f"[SZYBCIOR] Plan wygenerowany ({len(raw)} znaków)")

    # Parsuj JSON — obsłuż markdown code fences (```json ... ```)
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    plan_data = json.loads(raw)

    # Zapisz do bazy — update jeśli istnieje, insert jeśli nie
    existing = supabase_admin.table("training_plans").select("id").eq("user_id", user_id).execute()
    if existing.data:
        save_res = supabase_admin.table("training_plans").update({
            "plan_data": plan_data,
            "generation_reason": generation_reason,
        }).eq("user_id", user_id).execute()
        if not save_res.data:
            print(f"[SZYBCIOR] BŁĄD: update nie zwrócił danych")
            return {"error": "Zapis planu nie powiódł się"}
    else:
        save_res = supabase_admin.table("training_plans").insert({
            "user_id": user_id,
            "plan_data": plan_data,
            "generation_reason": generation_reason,
        }).execute()
        if not save_res.data:
            print(f"[SZYBCIOR] BŁĄD: insert nie zwrócił danych")
            return {"error": "Zapis planu nie powiódł się"}

    print(f"[SZYBCIOR] Plan zapisany do bazy, id: {save_res.data[0].get('id', '?')}")
    return {"plan": plan_data}
