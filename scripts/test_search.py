import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv(Path(__file__).parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def search(query: str, top_k: int = 3, threshold: float = 0.3):
    # Embedding pytania
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=query[:1000]
    )
    embedding = response.data[0].embedding

    # Similarity search w Supabase
    result = supabase.rpc("match_knowledge", {
        "query_embedding": embedding,
        "match_threshold": threshold,
        "match_count": top_k
    }).execute()

    return result.data


def main():
    print("=== TEST SIMILARITY SEARCH ===")
    print("Wpisz pytanie (lub 'q' żeby wyjść)\n")

    while True:
        query = input("Pytanie: ").strip()
        if query.lower() == "q":
            break
        if not query:
            continue

        results = search(query)

        if not results:
            print("  Brak wyników powyżej progu 0.3\n")
            continue

        print(f"\n  Top {len(results)} chunków:")
        for r in results:
            print(f"  [{r['similarity']:.3f}] {r['section_title']}")
            print(f"           {r['content'][:150]}...")
            print()


if __name__ == "__main__":
    main()
