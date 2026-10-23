"""Index PDFs into pgvector.

Usage (from the project root, venv active):
    python -m ai_agents.index_pdfs data/pdfs

Safe to re-run: chunks get deterministic IDs, so they are updated, not duplicated.
"""
import sys
import time
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ai_agents.rag_engine import get_vectorstore

BATCH_SIZE = 20       # small batches to respect the Gemini free-tier rate limits
PAUSE_SECONDS = 2
MAX_RETRIES = 5


def load_chunks(pdf_path: Path):
    pages = PyPDFLoader(str(pdf_path)).load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(pages)

    ids = []
    for i, chunk in enumerate(chunks):
        page = chunk.metadata.get("page", 0) + 1  # PyPDF pages are 0-indexed
        chunk.metadata = {"file": pdf_path.name, "page": page}
        ids.append(f"{pdf_path.name}:{page}:{i}")
    return chunks, ids


def add_with_retry(store, docs, ids):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            store.add_documents(docs, ids=ids)
            return
        except Exception as exc:  # rate limit / transient error
            wait = 5 * attempt
            print(f"  ! {exc.__class__.__name__}, retry {attempt}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Indexing failed after several retries.")


def main(folder: str):
    pdfs = sorted(Path(folder).glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDF found in {folder}")

    store = get_vectorstore()
    for pdf in pdfs:
        chunks, ids = load_chunks(pdf)
        print(f"{pdf.name}: {len(chunks)} chunks")
        for start in range(0, len(chunks), BATCH_SIZE):
            add_with_retry(
                store,
                chunks[start:start + BATCH_SIZE],
                ids[start:start + BATCH_SIZE],
            )
            time.sleep(PAUSE_SECONDS)
    print("Done.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/pdfs")
