"""RAG engine: semantic search over PDF chunks stored in PostgreSQL (pgvector).

Public API used by workflow.py:
    search(query, k=4) -> list[dict]   # each: {file, page, snippet, distance}
"""
import math
import os
import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

COLLECTION_NAME = os.getenv("PDF_COLLECTION", "pdf_chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
DEFAULT_K = int(os.getenv("RAG_TOP_K", "5"))
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def _connection_string() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (check your .env file).")
    # langchain-postgres needs the psycopg3 driver, not psycopg2.
    return url.replace("postgresql+psycopg2://", "postgresql+psycopg://")


@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    # Reads GOOGLE_API_KEY from the environment.
    return GoogleGenerativeAIEmbeddings(model=f"models/{EMBEDDING_MODEL}")


@lru_cache(maxsize=1)
def get_vectorstore() -> PGVector:
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=COLLECTION_NAME,
        connection=_connection_string(),
        use_jsonb=True,
    )


def _as_chunk(doc, distance: float) -> dict:
    return {
        "file": doc.metadata.get("file", "unknown"),
        "page": doc.metadata.get("page"),
        "snippet": doc.page_content,
        "distance": float(distance),  # lower = more similar (cosine)
    }


def search(query: str, k: int | None = None) -> list[dict]:
    """Return the k most similar PDF chunks with their sources.

    When the question names a year (e.g. 2025), the search is restricted to the documents
    whose file name contains that year, so a 2024 report cannot answer a 2025 question.
    Several years (a comparison) give each year its share of the results.
    A year without a matching document (e.g. 2030) is ignored.
    """
    k = k or DEFAULT_K
    store = get_vectorstore()
    vector = get_embeddings().embed_query(query)  # embedded once: saves embedding quota

    per_year: dict[str, list] = {}
    for year in sorted(set(YEAR_PATTERN.findall(query))):
        try:
            found = store.similarity_search_with_score_by_vector(
                vector, k=k, filter={"file": {"$like": f"%{year}%"}}
            )
        except Exception:
            found = []  # filter not supported: fall back to the plain search below
        if found:
            per_year[year] = found

    if per_year:
        share = k if len(per_year) == 1 else max(2, math.ceil(k / len(per_year)))
        candidates = [r for found in per_year.values() for r in found[:share * 2]]  # spare for duplicates
        limit = share * len(per_year)
    else:
        candidates = store.similarity_search_with_score_by_vector(vector, k=k * 2)
        limit = k

    chunks, seen = [], set()
    for doc, distance in sorted(candidates, key=lambda r: r[1]):
        text = doc.page_content.strip()
        if text in seen:  # overlapping chunks can repeat the same text
            continue
        seen.add(text)
        chunks.append(_as_chunk(doc, distance))
    return chunks[:limit]


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "What are the main risks?"
    for i, c in enumerate(search(q), 1):
        print(f"\n[{i}] {c['file']} p.{c['page']} (distance={c['distance']:.3f})")
        print(c["snippet"][:300].replace("\n", " "))
