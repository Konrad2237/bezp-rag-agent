import os
import sys
import json
import time
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

SOURCES_DIR = Path(__file__).parent.parent / "sources"
PROGRESS_FILE = Path(__file__).parent.parent / "sources" / "_progress.json"
CHARS_PER_TOKEN = 4
MAX_TOKENS_PER_CHUNK = 3000
MAX_CHARS_PER_CHUNK = MAX_TOKENS_PER_CHUNK * CHARS_PER_TOKEN
MAX_RETRIES = 3


# ── Mechaniczne cięcie ──────────────────────────────────────────────────────

def split_into_parts(text: str) -> list[str]:
    """Tnie tekst na kawałki ~3000 tokenów, zawsze kończąc na granicy akapitu."""
    parts = []
    current = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        current.append(line)
        current_len += len(line)

        if current_len >= MAX_CHARS_PER_CHUNK and line.strip() == "":
            parts.append("".join(current).strip())
            current = []
            current_len = 0

    if current:
        parts.append("".join(current).strip())

    return [p for p in parts if p]


# ── GPT chunking + tłumaczenie ──────────────────────────────────────────────

def chunk_with_gpt(text: str, source_name: str) -> list[dict]:
    """Wysyła kawałek tekstu do GPT-4o-mini — semantyczne chunki po polsku."""
    prompt = f"""Jesteś ekspertem od przetwarzania dokumentów dla systemów RAG.

Poniżej masz fragment anglojęzycznego tekstu o treningu, żywieniu lub regeneracji.

Twoje zadanie:
1. Podziel tekst na semantycznie spójne chunki — jeden chunk = jedna zamknięta myśl/koncepcja
2. Przetłumacz każdy chunk na język polski (naturalny, nie dosłowny)
3. Każdy chunk powinien mieć 150-500 tokenów po polsku
4. Każdy chunk powinien być samowystarczalny — czytelnik rozumie go bez kontekstu
5. Określ temat: "trening", "zywienic", "regeneracja" lub "ogolne"
6. Wyciągnij 3-5 słów kluczowych po polsku

Odpowiedz WYŁĄCZNIE w formacie JSON, zero tekstu przed ani po, zero backtick:
{{
  "chunks": [
    {{
      "section_title": "Krótki tytuł po polsku (max 60 znaków)",
      "content": "Przetłumaczona treść chunku po polsku",
      "topic": "trening",
      "keywords": ["słowo1", "słowo2", "słowo3"]
    }}
  ]
}}

TEKST:
{text}"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=8000,
            )
            raw = response.choices[0].message.content.strip()

            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:])
                raw = raw.rsplit("```", 1)[0].strip()

            data = json.loads(raw)
            chunks = data["chunks"]

            for chunk in chunks:
                chunk["source"] = source_name

            return chunks

        except (json.JSONDecodeError, KeyError) as e:
            print(f"    BŁĄD parsowania JSON (próba {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)
        except Exception as e:
            print(f"    BŁĄD API (próba {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(5)

    print(f"    Pominięto kawałek po {MAX_RETRIES} nieudanych próbach")
    return []


# ── Embeddingi ──────────────────────────────────────────────────────────────

def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000],
    )
    return response.data[0].embedding


# ── Supabase ─────────────────────────────────────────────────────────────────

def upload_chunk(chunk: dict, chunk_index: int):
    embedding = get_embedding(chunk["content"])
    supabase.table("knowledge_embeddings").insert({
        "content": chunk["content"],
        "embedding": embedding,
        "source": chunk["source"],
        "section_title": chunk.get("section_title", ""),
        "chunk_index": chunk_index,
    }).execute()


def delete_existing_source(source_name: str):
    result = supabase.table("knowledge_embeddings").select("id").eq("source", source_name).execute()
    if result.data:
        print(f"  Usuwam {len(result.data)} istniejących chunków dla '{source_name}'...")
        supabase.table("knowledge_embeddings").delete().eq("source", source_name).execute()


# ── Progress ─────────────────────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {}


def save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────

def process_file(txt_file: Path, progress: dict) -> int:
    source_name = txt_file.stem
    print(f"\n{'='*60}")
    print(f"Plik: {txt_file.name}  →  source: '{source_name}'")

    text = txt_file.read_text(encoding="utf-8", errors="replace")
    parts = split_into_parts(text)
    print(f"Mechaniczne cięcie: {len(parts)} kawałków")

    if source_name not in progress:
        progress[source_name] = {"done_parts": [], "total_chunks": 0}
        delete_existing_source(source_name)
        save_progress(progress)

    done_parts = set(progress[source_name]["done_parts"])
    chunk_index = progress[source_name]["total_chunks"]
    new_chunks = 0

    for i, part in enumerate(parts):
        if i in done_parts:
            print(f"  Kawałek {i+1}/{len(parts)}: pominięty (już przetworzony)")
            continue

        words = len(part.split())
        print(f"  Kawałek {i+1}/{len(parts)} (~{words} słów): ", end="", flush=True)

        chunks = chunk_with_gpt(part, source_name)
        print(f"{len(chunks)} chunków → uploading...", end="", flush=True)

        for chunk in chunks:
            upload_chunk(chunk, chunk_index)
            chunk_index += 1
            new_chunks += 1

        print(" ✓")

        progress[source_name]["done_parts"].append(i)
        progress[source_name]["total_chunks"] = chunk_index
        save_progress(progress)

    print(f"Gotowe: {new_chunks} nowych chunków dla '{source_name}'")
    return new_chunks


def main():
    if not SOURCES_DIR.exists():
        print(f"BŁĄD: Folder {SOURCES_DIR} nie istnieje")
        sys.exit(1)

    txt_files = sorted(SOURCES_DIR.glob("*.txt"))
    if not txt_files:
        print(f"Brak plików .txt w {SOURCES_DIR}")
        sys.exit(1)

    print(f"Znaleziono {len(txt_files)} plików:")
    for f in txt_files:
        size_kb = f.stat().st_size // 1024
        print(f"  {f.name} ({size_kb} KB)")

    progress = load_progress()
    already_done = [f for f in txt_files if f.stem in progress and
                    len(progress[f.stem]["done_parts"]) == len(split_into_parts(f.read_text(encoding="utf-8", errors="replace")))]

    if already_done:
        print(f"\nJuż przetworzone (pomijam): {[f.name for f in already_done]}")

    remaining = [f for f in txt_files if f not in already_done]
    if not remaining:
        print("\nWszystkie pliki już przetworzone.")
        return

    print(f"\nDo przetworzenia: {len(remaining)} plików")

    # Test na pierwszym pliku
    if not progress:
        first = remaining[0]
        print(f"\nZaczynam od pliku testowego: {first.name}")
        print("Po przetworzeniu sprawdź jakość chunków w Supabase.")
        print("Kontynuować tylko ten plik? (t/n): ", end="")
        if input().strip().lower() != "t":
            print("Anulowano.")
            return

        process_file(first, progress)
        remaining = remaining[1:]

        if remaining:
            print(f"\nSprawdź jakość. Przetworzyć pozostałe {len(remaining)} plików? (t/n): ", end="")
            if input().strip().lower() != "t":
                print("OK. Uruchom skrypt ponownie gdy będziesz gotowy — postęp jest zapisany.")
                return

    total = 0
    for txt_file in remaining:
        total += process_file(txt_file, progress)

    print(f"\n{'='*60}")
    print(f"KONIEC. Wgrano łącznie {total} nowych chunków.")
    print(f"Aby zresetować postęp: usuń plik {PROGRESS_FILE.name}")


if __name__ == "__main__":
    main()
