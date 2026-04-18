import json
from config import claude_client, supabase, supabase_admin

SUMMARIZER_PROMPT = """Jesteś Blacha — system zarządzania pamięcią w aplikacji "Bez Pierdolenia".
Twoim zadaniem jest zaktualizowanie podsumowania rozmów użytkownika z Pitbulem
(AI trenerem personalnym) na podstawie nowych wiadomości.

System składa się z agentów: Pitbul (główny agent konwersacyjny), Szybcior (generuje plany
treningowe), Blacha (to Ty — zarządzasz pamięcią), Uszatek (wkrótce — analiza postępów).

POPRZEDNIE PODSUMOWANIE:
{previous_summary}

NOWE WIADOMOŚCI (ostatnie 10):
{recent_messages}

════════════════════════════════════════
TWOJE ZADANIE
════════════════════════════════════════

Stwórz nowe, zaktualizowane podsumowanie które:
1. Zachowuje ważne fakty z poprzedniego podsumowania (jeśli nadal aktualne)
2. Dodaje nowe ważne informacje z ostatnich wiadomości
3. Usuwa informacje które zostały zaktualizowane lub są już nieaktualne
4. Ma maksymalnie 250 słów

════════════════════════════════════════
CO WARTO ZACHOWAĆ W PODSUMOWANIU
════════════════════════════════════════

✓ Postępy treningowe (nowe rekordy, osiągnięcia)
✓ Kiedy Szybcior wygenerował lub zmodyfikował plan (i dlaczego)
✓ Aktualne kontuzje lub dolegliwości
✓ Zmiany celu lub motywacji
✓ Ważny kontekst ("user wrócił po 2 tygodniach choroby")
✓ Rzeczy które user lubi lub nie lubi robić
✓ Specyficzne preferencje dotyczące treningu
✓ O co Pitbul dopytywał (żeby nie pytać dwa razy o to samo)

✗ NIE ZACHOWUJ: pytań o technikę ćwiczeń
✗ NIE ZACHOWUJ: ogólnych rozmów bez znaczenia dla przyszłych sesji
✗ NIE ZACHOWUJ: informacji które są już w profilu usera

════════════════════════════════════════
FORMAT ODPOWIEDZI
════════════════════════════════════════

Odpowiedz WYŁĄCZNIE treścią podsumowania. Bez nagłówków, bez JSON,
bez komentarzy. Pisz w trzeciej osobie ("User...", "Użytkownik...").
Zachowaj styl telegraficzny — fakty, nie opisy.

Przykład dobrego podsumowania:
"User trenuje od 3 tygodni wg planu FBW 3x tydzień wygenerowanego przez Szybciora.
Zaczął od 40kg na ławce, aktualnie robi 55kg. Dwa tygodnie temu skarżył się na ból
barku lewego przy wyciskaniu — Pitbul zaproponował wyciskanie hantlami zamiast
sztangi, user potwierdził że pomogło. Celem jest masa mięśniowa. User preferuje
krótkie treningi (45-60 min). Nie lubi przysiadu — pracują nad techniką.
Ostatnio dodał kreatynę do suplementacji. Pitbul pytał już o sen (7h, dobrze)
i dietę (nie pilnuje)." """


def run_summarizer_agent(user_id: str):
    """
    Summarizer Agent — uruchamiany w tle co 10 wiadomości.
    Kondensuje historię rozmów do krótkiego podsumowania.
    """
    try:
        # Pobierz poprzednie podsumowanie
        summary_result = supabase.table("conversation_summaries")\
            .select("*")\
            .eq("user_id", user_id)\
            .limit(1)\
            .execute()

        previous_summary = ""
        messages_summarized = 0
        summary_id = None

        if summary_result.data:
            previous_summary = summary_result.data[0].get("summary_text", "") or ""
            messages_summarized = summary_result.data[0].get("messages_summarized", 0) or 0
            summary_id = summary_result.data[0]["id"]

        # Pobierz ostatnie 10 wiadomości (wszystkie sesje)
        messages_result = supabase.table("messages")\
            .select("role, content, created_at")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(10)\
            .execute()

        if not messages_result.data:
            print(f"[SUMMARIZER] Brak wiadomości dla usera")
            return

        # Odwróć żeby były chronologicznie
        recent_messages = list(reversed(messages_result.data))
        messages_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in recent_messages
        ])

        prompt = SUMMARIZER_PROMPT.format(
            previous_summary=previous_summary if previous_summary else "Brak poprzedniego podsumowania.",
            recent_messages=messages_text,
        )

        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )

        new_summary = response.content[0].text.strip()

        # Zapisz lub zaktualizuj podsumowanie
        if summary_id:
            supabase.table("conversation_summaries")\
                .update({
                    "summary_text": new_summary,
                    "messages_summarized": messages_summarized + 10,
                    "updated_at": "now()",
                })\
                .eq("id", summary_id)\
                .execute()
        else:
            supabase_admin.table("conversation_summaries").insert({
                "user_id": user_id,
                "summary_text": new_summary,
                "messages_summarized": 10,
            }).execute()

        print(f"[SUMMARIZER] Podsumowanie zaktualizowane ({len(new_summary.split())} słów)")

    except Exception as e:
        print(f"[SUMMARIZER] Błąd: {e}")
