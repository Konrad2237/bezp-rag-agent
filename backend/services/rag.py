from config import supabase, openai_client


def get_embedding(text: str) -> list[float]:
    """Generuje embedding przez OpenAI text-embedding-3-small."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:1000]
    )
    return response.data[0].embedding


def search_knowledge(query: str, top_k: int = 5, threshold: float = 0.3) -> str:
    """
    Similarity search w Supabase pgvector.
    Zwraca sformatowany string z chunkami lub info o braku wyników.
    """
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
            f"Fragment (temat: {r['section_title']}):\n{r['content']}"
        )

    return "\n\n---\n\n".join(chunks)
