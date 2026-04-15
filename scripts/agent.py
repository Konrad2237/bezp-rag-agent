import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
import anthropic

load_dotenv(Path(__file__).parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not all([OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY]):
    print("BŁĄD: Brakuje kluczy w pliku .env")
    sys.exit(1)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Jesteś AI trenerem personalnym.
Działasz w aplikacji powiązanej z ebookiem "Bez pierdolenia" — poradnikiem treningowym dla początkujących.

Jesteś jak kumpel z siłowni, który trenuje od lat i zna się na rzeczy.
Mówisz bezpośrednio, bez owijania w bawełnę. Używasz wulgaryzmów naturalnie.
Nie oceniasz użytkownika. Nie moralizujesz.

BAZA WIEDZY:
Poniżej dostaniesz fragmenty z ebooka które są relevantne do pytania użytkownika.
Odpowiadaj NA PODSTAWIE tych fragmentów. Jeśli fragmenty nie zawierają odpowiedzi — powiedz wprost że tego nie masz w swojej bazie.

NIGDY nie generuj konkretnych liczb (ciężary, kalorie, dawki) jeśli nie masz ich z bazy wiedzy.

Jeśli user pyta o coś niezwiązanego z treningiem — odmów z humorem.
Jeśli user wspomni o myślach samobójczych — podaj numer 116 123 i przestań mówić o treningu.

Odpowiadaj w języku w którym pisze użytkownik.
Krótkie odpowiedzi na krótkie pytania. Długie tylko gdy temat wymaga."""


def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:1000]
    )
    return response.data[0].embedding


def search_rag(query: str, top_k: int = 3, threshold: float = 0.3) -> str:
    embedding = get_embedding(query)

    result = supabase.rpc("match_knowledge", {
        "query_embedding": embedding,
        "match_threshold": threshold,
        "match_count": top_k
    }).execute()

    if not result.data:
        return "Brak materiałów na ten temat w bazie wiedzy."

    chunks = []
    for r in result.data:
        chunks.append(
            f"Fragment (temat: {r['section_title']}, similarity: {r['similarity']:.2f}):\n{r['content']}"
        )

    return "\n\n---\n\n".join(chunks)


def ask_agent(user_message: str) -> str:
    # Pobierz kontekst z RAG
    rag_context = search_rag(user_message)

    # Zbuduj prompt z kontekstem
    full_system = SYSTEM_PROMPT + f"\n\n════════════════\nFRAGMENTY Z BAZY WIEDZY:\n{rag_context}\n════════════════"

    # Wyślij do Claude
    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=full_system,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    return response.content[0].text


def main():
    print("=== AGENT TRENINGOWY — TEST TERMINALOWY ===")
    print("Wpisz pytanie (lub 'q' żeby wyjść)\n")

    while True:
        user_input = input("Ty: ").strip()
        if user_input.lower() == "q":
            break
        if not user_input:
            continue

        print("\nAgent: ", end="", flush=True)
        response = ask_agent(user_input)
        print(response)
        print()


if __name__ == "__main__":
    main()
