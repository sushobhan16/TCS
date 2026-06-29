from pathlib import Path
from pypdf import PdfReader

PDF_FOLDER = Path("data/raw_pdfs")

total_docs = 0
total_pages = 0

for pdf_file in PDF_FOLDER.glob("*.pdf"):
    try:
        reader = PdfReader(pdf_file)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text

        total_docs += 1
        total_pages += len(reader.pages)

        print(f"\n{pdf_file.name}")
        print(f"Pages: {len(reader.pages)}")
        print(f"Characters: {len(text)}")

    except Exception as e:
        print(f"Error reading {pdf_file.name}: {e}")

print("\nSUMMARY")
print(f"Total Documents: {total_docs}")
print(f"Total Pages: {total_pages}")