import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from docx import Document

load_dotenv(Path(__file__).parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY]):
    print("BŁĄD: Brakuje kluczy w pliku .env")
    sys.exit(1)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def extract_text_from_docx(docx_path: str) -> str:
    """Wyciąga cały tekst z docx."""
    doc = Document(docx_path)
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def semantic_chunk_with_gpt(text: str) -> list[dict]:
    """
    Wysyła cały tekst do GPT-4o-mini z instrukcją semantycznego chunkowania.
    GPT zwraca JSON z listą chunków pogrupowanych tematycznie.
    """
    print("Wysyłam tekst do GPT-4o-mini — czekam na semantyczne chunki...")

    prompt = """Jesteś ekspertem od przetwarzania dokumentów dla systemów RAG.

Poniżej masz treść ebooka o treningu siłowym dla początkujących.

Twoim zadaniem jest podzielenie tego tekstu na SEMANTYCZNE CHUNKI — czyli grupy informacji o tym samym TEMACIE.

Zasady:
1. Jeden chunk = jeden zamknięty temat (np. "progresja obciążeń", "rozgrzewka", "plan FBW 3x")
2. Jeśli informacje o tym samym temacie są w różnych miejscach — zbierz je do jednego chunku
3. Każdy chunk powinien mieć 100-800 słów
4. Chunk powinien być samowystarczalny — ktoś czytający tylko ten fragment powinien zrozumieć temat
5. Nie dziel mechanicznie po rozdziałach — dziel po SENSIE

Odpowiedz WYŁĄCZNIE w formacie JSON, bez żadnego tekstu przed ani po:
{
  "chunks": [
    {
      "section_title": "Krótki tytuł tematu (max 60 znaków)",
      "content": "Pełna treść chunku — wszystkie informacje o tym temacie zebrane razem"
    }
  ]
}

TREŚĆ EBOOKA:
""" + text

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=16000,
    )

    raw = response.choices[0].message.content.strip()

    # Usuń ewentualne backticki
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    data = json.loads(raw)
    chunks = data["chunks"]

    # Dodaj index i source
    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i
        chunk["source"] = "ebook"

    print(f"GPT podzielił na {len(chunks)} semantycznych chunków")
    return chunks


def get_embedding(text: str) -> list[float]:
    text = text[:8000]
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def upload_chunks_to_supabase(chunks: list[dict]):
    print(f"\nWgrywam {len(chunks)} chunków do Supabase...")
    for i, chunk in enumerate(chunks):
        title_preview = chunk['section_title'][:50]
        print(f"  Chunk {i+1}/{len(chunks)}: '{title_preview}' ", end="", flush=True)
        embedding = get_embedding(chunk["content"])
        supabase.table("knowledge_embeddings").insert({
            "content": chunk["content"],
            "embedding": embedding,
            "source": chunk["source"],
            "section_title": chunk["section_title"],
            "chunk_index": chunk["chunk_index"],
        }).execute()
        print("✓")
    print(f"\nGotowe! Wgrano {len(chunks)} chunków.")


def main():
    docx_path = Path(__file__).parent.parent / "ebook-bezp.docx"

    if not docx_path.exists():
        print(f"BŁĄD: Nie znaleziono pliku {docx_path}")
        sys.exit(1)

    print("Wyciągam tekst z docx...")
    text = extract_text_from_docx(str(docx_path))
    print(f"Wyciągnięto {len(text.split())} słów")

    chunks = semantic_chunk_with_gpt(text)

    print(f"\nPodgląd wszystkich chunków:")
    for chunk in chunks:
        words = len(chunk["content"].split())
        print(f"  [{chunk['chunk_index']}] '{chunk['section_title']}' — {words} słów")

    print(f"\nCzy wgrać {len(chunks)} chunków do Supabase? (t/n): ", end="")
    answer = input().strip().lower()

    if answer != "t":
        print("Anulowano.")
        sys.exit(0)

    upload_chunks_to_supabase(chunks)


if __name__ == "__main__":
    main()
