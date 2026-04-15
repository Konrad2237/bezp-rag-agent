import pdfplumber
from pathlib import Path

pdf_path = Path(__file__).parent.parent / "ebook-bezp.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Liczba stron: {len(pdf.pages)}")
    for i in range(min(5, len(pdf.pages))):
        print(f"\n--- STRONA {i+1} ---")
        text = pdf.pages[i].extract_text()
        print(text)
