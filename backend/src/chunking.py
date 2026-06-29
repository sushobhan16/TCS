from pathlib import Path
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import json

PDF_FOLDER = Path("data/raw_pdfs")
OUTPUT_FOLDER = Path("data/processed")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "chunks.json"


def get_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF."""
    try:
        reader = PdfReader(pdf_path)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text

        return text

    except Exception as e:
        print(f"Error reading {pdf_path.name}: {e}")
        return ""


def main():

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )

    print("--- STARTING DOCUMENT CHUNKING SYSTEM ---")

    all_chunks = []

    total_chunks = 0
    total_documents = 0

    for pdf_file in PDF_FOLDER.glob("*.pdf"):

        raw_text = get_pdf_text(pdf_file)

        if not raw_text.strip():
            print(f"Skipping empty file: {pdf_file.name}")
            continue

        total_documents += 1

        chunks = text_splitter.split_text(raw_text)

        total_chunks += len(chunks)

        print(f"\nDocument: {pdf_file.name}")
        print(f"Original Characters: {len(raw_text)}")
        print(f"Generated Chunks: {len(chunks)}")

        avg_chunk_size = sum(len(chunk) for chunk in chunks) / len(chunks)

        print(f"Average Chunk Size: {avg_chunk_size:.2f}")

        if chunks:
            print("\nSample Chunk Preview:")
            print(chunks[0][:200])

        for idx, chunk in enumerate(chunks):

            chunk_record = {
                "source": pdf_file.name,
                "chunk_id": idx,
                "text": chunk
            }

            all_chunks.append(chunk_record)

        print("-" * 50)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print("\n--- CHUNKING COMPLETE ---")
    print(f"Documents Processed: {total_documents}")
    print(f"Total Chunks Generated: {total_chunks}")
    print(f"Chunks Saved To: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()