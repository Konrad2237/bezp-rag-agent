import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv(Path(__file__).parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY]):
    print("BŁĄD: Brakuje kluczy w pliku .env")
    sys.exit(1)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000]
    )
    return response.data[0].embedding


def main():
    chunks_file = Path(__file__).parent.parent / "chunki" / "chunki_finalne.json"

    if not chunks_file.exists():
        print(f"BŁĄD: Nie znaleziono pliku {chunks_file}")
        sys.exit(1)

    data = json.loads(chunks_file.read_text(encoding="utf-8"))
    chunks = data["chunks"]
    print(f"Wczytano {len(chunks)} chunków z {chunks_file.name}")

    print(f"\nPodgląd:")
    for chunk in chunks:
        words = len(chunk["tresc"].split())
        print(f"  [{chunk['chunk_index']}] '{chunk['temat']}' — {words} słów")

    print(f"\nCzy wgrać {len(chunks)} chunków do Supabase? (t/n): ", end="")
    answer = input().strip().lower()
    if answer != "t":
        print("Anulowano.")
        sys.exit(0)

    print(f"\nWgrywam do Supabase...")
    for i, chunk in enumerate(chunks):
        print(f"  {i+1}/{len(chunks)}: '{chunk['temat']}' ", end="", flush=True)

        embedding = get_embedding(chunk["tresc"])

        supabase.table("knowledge_embeddings").insert({
            "content": chunk["tresc"],
            "embedding": embedding,
            "source": chunk["source"],
            "section_title": chunk["temat"],
            "chunk_index": chunk["chunk_index"],
        }).execute()

        print("✓")

    print(f"\nGotowe! Wgrano {len(chunks)} chunków.")


if __name__ == "__main__":
    main()
