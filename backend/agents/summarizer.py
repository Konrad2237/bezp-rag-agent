import json
from config import claude_client, supabase

SUMMARIZER_PROMPT = """Jesteś systemem zarządzania pamięcią dla AI trenera personalnego.
Zaktualizuj podsumowanie rozmów użytkownika na podstawie nowych wiadomości.

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
3. Usuwa informacje które są już nieaktualne
4. Ma maksymalnie 250 słów

CO WARTO ZACHOWAĆ:
✓ Postępy treningowe (rekordy, osiągnięcia)
✓ Zmiany w planie i ich powody
✓ Aktualne kontuzje
✓ Zmiany celu lub motywacji
✓ Rzeczy które user lubi lub nie lubi
✓ O co agent dopytywał (żeby nie pytać dwa razy)

NIE ZACHOWUJ:
✗ Pytań o technikę ćwiczeń (wiedza ogólna)
✗ Rozmów bez znaczenia dla przyszłych sesji
✗ Informacji które są już w profilu usera

FORMAT: Odpowiedz WYŁĄCZNIE treścią podsumowania.
Bez nagłówków, bez JSON. Pisz w trzeciej osobie ("User...").
Styl telegraficzny — fakty, nie opisy."""


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
            supabase.table("conversation_summaries").insert({
                "user_id": user_id,
                "summary_text": new_summary,
                "messages_summarized": 10,
            }).execute()

        print(f"[SUMMARIZER] Podsumowanie zaktualizowane ({len(new_summary.split())} słów)")

    except Exception as e:
        print(f"[SUMMARIZER] Błąd: {e}")
