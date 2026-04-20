import os
from tavily import TavilyClient

_client = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY nie ustawiony")
        _client = TavilyClient(api_key=api_key)
    return _client


def search_web(query: str, max_results: int = 3) -> str:
    """Przeszukuje internet przez Tavily API. Zwraca tekstowe wyniki."""
    try:
        results = _get_client().search(query, max_results=max_results)
        if not results.get("results"):
            return "Brak wyników web search dla tego zapytania."

        parts = []
        for r in results["results"]:
            title = r.get("title", "")
            content = r.get("content", "")
            url = r.get("url", "")
            parts.append(f"**{title}**\n{content}\nŹródło: {url}")

        return "\n\n---\n\n".join(parts)

    except Exception as e:
        print(f"[SEARCH_WEB] Błąd: {e}")
        return f"Błąd web search: {e}"
