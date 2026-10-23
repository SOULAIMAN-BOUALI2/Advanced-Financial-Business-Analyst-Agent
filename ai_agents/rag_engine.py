"""RAG engine: semantic search over PDF chunks stored in PostgreSQL (pgvector).

Public API used by workflow.py:
    search(query, k=4) -> list[dict]   # each: {file, page, snippet, distance}
"""
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

COLLECTION_NAME = os.getenv("PDF_COLLECTION", "pdf_chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")


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


def search(query: str, k: int = 4) -> list[dict]:
    """Return the k most similar PDF chunks with their sources."""
    results = get_vectorstore().similarity_search_with_score(query, k=k)
    chunks = []
    for doc, distance in results:
        chunks.append(
            {
                "file": doc.metadata.get("file", "unknown"),
                "page": doc.metadata.get("page"),
                "snippet": doc.page_content,
                "distance": float(distance),  # lower = more similar (cosine)
            }
        )
    return chunks


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "What are the main risks?"
    for i, c in enumerate(search(q), 1):
        print(f"\n[{i}] {c['file']} p.{c['page']} (distance={c['distance']:.3f})")
        print(c["snippet"][:300].replace("\n", " "))
