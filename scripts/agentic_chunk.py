import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("BŁĄD: Brakuje OPENAI_API_KEY w pliku .env")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

PARTS_DIR = Path(__file__).parent.parent / "ebook-parts"
OUTPUT_DIR = Path(__file__).parent.parent / "chunki"
OUTPUT_DIR.mkdir(exist_ok=True)

TOKEN_LIMIT = 30000


def count_tokens_approx(text: str) -> int:
    """Przybliżona liczba tokenów: ~1 token = 4 znaki."""
    return len(text) // 4


def chunk_part_with_gpt(text: str, part_name: str) -> list[dict]:
    """Wysyła część ebooka do GPT i zwraca semantyczne chunki."""
    tokens = count_tokens_approx(text)
    print(f"  Szacowana liczba tokenów: ~{tokens}")
    if tokens > TOKEN_LIMIT:
        print(f"  OSTRZEŻENIE: Plik przekracza {TOKEN_LIMIT} tokenów!")

    prompt = f"""Jesteś ekspertem od przetwarzania dokumentów dla systemów RAG (Retrieval-Augmented Generation).

Poniżej masz fragment ebooka o treningu siłowym dla początkujących.

Twoim zadaniem jest:
1. Przeczytaj całość uważnie
2. Zidentyfikuj tematy — jeden temat to jedna zamknięta idea (np. "progresja obciążeń", "plan FBW", "rozgrzewka")
3. Zbierz WSZYSTKIE informacje o tym samym temacie w jeden chunk — nawet jeśli temat pojawia się w kilku miejscach
4. Każdy chunk powinien być samowystarczalny — czytelnik rozumie go bez kontekstu
5. Rozmiar chunku: 100-800 słów

Odpowiedz WYŁĄCZNIE w formacie JSON, zero tekstu przed ani po, zero backtick:
{{
  "chunks": [
    {{
      "temat": "Krótka nazwa tematu 2-5 słów",
      "rozdzialy": [1, 2],
      "slowa_kluczowe": ["słowo1", "słowo2", "słowo3", "słowo4", "słowo5"],
      "tresc": "Pełna treść chunku ze wszystkimi informacjami o tym temacie"
    }}
  ]
}}

TREŚĆ:
{text}"""

    print(f"  Wysyłam do GPT-4o-mini...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=16000,
    )

    raw = response.choices[0].message.content.strip()

    # Usuń backticki jeśli są
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
        chunks = data["chunks"]
        print(f"  GPT zwrócił {len(chunks)} chunków")
        return chunks
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  BŁĄD parsowania JSON: {e}")
        print(f"  Odpowiedź GPT (pierwsze 500 znaków): {raw[:500]}")
        return []


def merge_chunks_with_gpt(all_chunks: list[dict]) -> list[dict]:
    """Scala chunki z różnych części — łączy te o tym samym temacie."""
    chunks_json = json.dumps(all_chunks, ensure_ascii=False, indent=2)
    tokens = count_tokens_approx(chunks_json)
    print(f"\nŁączna wielkość chunków przed scalaniem: ~{tokens} tokenów")

    if tokens > TOKEN_LIMIT:
        print("Przekracza limit — scalanie parami...")
        mid = len(all_chunks) // 2
        part_a = merge_chunks_with_gpt(all_chunks[:mid])
        part_b = merge_chunks_with_gpt(all_chunks[mid:])
        all_chunks = part_a + part_b
        chunks_json = json.dumps(all_chunks, ensure_ascii=False, indent=2)

    print("Wysyłam do GPT-4o-mini — scalanie tematów...")

    prompt = f"""Masz listę chunków z ebooka o treningu siłowym. Chunki powstały z różnych części ebooka.

Twoim zadaniem:
1. Znajdź chunki które dotyczą tego samego tematu
2. Scal je w jeden chunk zachowując CAŁĄ treść (nie skracaj!)
3. Zaktualizuj metadane: temat, rozdzialy (suma), slowa_kluczowe (suma unikalnych)
4. Chunki o różnych tematach zostaw bez zmian

Odpowiedz WYŁĄCZNIE w formacie JSON, zero tekstu przed ani po, zero backtick:
{{
  "chunks": [
    {{
      "temat": "Nazwa tematu",
      "rozdzialy": [1, 2, 3],
      "slowa_kluczowe": ["słowo1", "słowo2"],
      "tresc": "Pełna scalona treść"
    }}
  ]
}}

CHUNKI DO SCALENIA:
{chunks_json}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=16000,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
        chunks = data["chunks"]
        print(f"Po scaleniu: {len(chunks)} chunków")
        return chunks
    except (json.JSONDecodeError, KeyError) as e:
        print(f"BŁĄD parsowania JSON przy scalaniu: {e}")
        print(f"Odpowiedź (pierwsze 500 znaków): {raw[:500]}")
        return all_chunks  # Zwróć oryginalne jeśli scalanie failuje


def print_summary(parts_counts: dict, final_chunks: list[dict]):
    """Wyświetla podsumowanie w terminalu."""
    print("\n" + "="*60)
    print("PODSUMOWANIE")
    print("="*60)
    print("\nChunki z każdej części:")
    for part, count in parts_counts.items():
        print(f"  {part}: {count} chunków")

    print(f"\nPo scalaniu: {len(final_chunks)} chunków")
    print("\nLista tematów:")
    for i, chunk in enumerate(final_chunks):
        rozdzialy = ", ".join(str(r) for r in chunk.get("rozdzialy", []))
        print(f"  [{i+1}] {chunk['temat']} (rozdz: {rozdzialy})")
    print("="*60)


def main():
    # Sprawdź czy folder z częściami istnieje
    if not PARTS_DIR.exists():
        PARTS_DIR.mkdir(exist_ok=True)
        print(f"Stworzono folder: {PARTS_DIR}")
        print("Wrzuć pliki czesc1.txt, czesc2.txt, czesc3.txt, czesc4.txt do folderu ebook-parts/")
        sys.exit(0)

    # Znajdź pliki części
    part_files = sorted(PARTS_DIR.glob("czesc*.txt"))
    if not part_files:
        print(f"Brak plików czesc*.txt w folderze {PARTS_DIR}")
        print("Wrzuć pliki czesc1.txt, czesc2.txt itd. do folderu ebook-parts/")
        sys.exit(1)

    print(f"Znaleziono {len(part_files)} części: {[f.name for f in part_files]}")

    # KROK 1 — Chunking każdej części osobno
    print("\n" + "="*60)
    print("KROK 1: Chunking każdej części")
    print("="*60)

    all_chunks = []
    parts_counts = {}

    for part_file in part_files:
        print(f"\nPrzetwarzam: {part_file.name}")
        text = part_file.read_text(encoding="utf-8")
        print(f"  Rozmiar: {len(text)} znaków, ~{len(text.split())} słów")

        chunks = chunk_part_with_gpt(text, part_file.stem)

        if chunks:
            # Zapisz wynik części
            output_file = OUTPUT_DIR / f"chunki_{part_file.stem}.json"
            output_file.write_text(
                json.dumps({"chunks": chunks}, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"  Zapisano do: {output_file.name}")
            parts_counts[part_file.name] = len(chunks)
            all_chunks.extend(chunks)
        else:
            print(f"  BŁĄD: Brak chunków dla {part_file.name}")
            parts_counts[part_file.name] = 0

    print(f"\nŁącznie chunków przed scalaniem: {len(all_chunks)}")

    # KROK 2 — Scalanie
    print("\n" + "="*60)
    print("KROK 2: Scalanie chunków między częściami")
    print("="*60)

    final_chunks = merge_chunks_with_gpt(all_chunks)

    # Dodaj indeksy i source
    for i, chunk in enumerate(final_chunks):
        chunk["chunk_index"] = i
        chunk["source"] = "ebook"

    # Zapisz finalne chunki
    final_file = OUTPUT_DIR / "chunki_finalne.json"
    final_file.write_text(
        json.dumps({"chunks": final_chunks}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Zapisano finalne chunki do: {final_file}")

    # KROK 3 — Walidacja i podsumowanie
    print_summary(parts_counts, final_chunks)


if __name__ == "__main__":
    main()
