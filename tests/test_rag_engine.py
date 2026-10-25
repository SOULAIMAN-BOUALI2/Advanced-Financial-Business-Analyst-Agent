"""Unit tests for the year-aware retrieval. A fake vector store replaces the database and the API.

Run from the project root:  python -m pytest tests/test_rag_engine.py -v
"""
from types import SimpleNamespace

import pytest

from ai_agents import rag_engine

ROWS = [  # (file, page, text, distance)
    ("annual_report_2024.pdf", 48, "resultat net 2024 : 1 826 MDH", 0.30),
    ("annual_report_2024.pdf", 49, "dividende 70 DH", 0.35),
    ("annual_report_2025.pdf", 54, "resultat net 2025 : 2 166 MDH", 0.32),
    ("annual_report_2025.pdf", 55, "dividende 96 DH", 0.40),
    ("annual_report_2025.pdf", 56, "dividende 96 DH", 0.41),  # same text as page 55 (overlap)
    ("tsaks.pdf", 3, "noeud routeur", 0.50),
]


class FakeStore:
    def similarity_search_with_score_by_vector(self, vector, k=4, filter=None):
        rows = ROWS
        if filter:
            pattern = filter["file"]["$like"].strip("%")
            rows = [r for r in rows if pattern in r[0]]
        rows = sorted(rows, key=lambda r: r[3])[:k]
        return [(SimpleNamespace(page_content=r[2], metadata={"file": r[0], "page": r[1]}), r[3]) for r in rows]


@pytest.fixture(autouse=True)
def fake_backend(monkeypatch):
    monkeypatch.setattr(rag_engine, "get_vectorstore", lambda: FakeStore())
    monkeypatch.setattr(rag_engine, "get_embeddings", lambda: SimpleNamespace(embed_query=lambda q: [0.0]))


def files(chunks):
    return {c["file"] for c in chunks}


def test_a_year_restricts_the_search_to_that_report():
    chunks = rag_engine.search("Quel dividende pour l'exercice 2025 ?", k=3)
    assert files(chunks) == {"annual_report_2025.pdf"}


def test_two_years_give_each_report_its_share():
    chunks = rag_engine.search("Compare le résultat net de 2024 et de 2025", k=4)
    assert files(chunks) == {"annual_report_2024.pdf", "annual_report_2025.pdf"}


def test_a_year_with_no_report_is_ignored():
    chunks = rag_engine.search("Que prévoit la stratégie pour 2030 ?", k=4)
    assert len(chunks) == 4  # plain search over every document


def test_a_year_with_no_report_next_to_a_real_year():
    chunks = rag_engine.search("résultat net 2024 par rapport à 2023", k=3)
    assert files(chunks) == {"annual_report_2024.pdf"}


def test_without_a_year_every_document_is_searched():
    chunks = rag_engine.search("noeud routeur", k=6)
    assert "tsaks.pdf" in files(chunks)


def test_duplicated_text_is_returned_once():
    chunks = rag_engine.search("dividende 2025", k=5)
    assert [c["snippet"] for c in chunks].count("dividende 96 DH") == 1


def test_results_are_sorted_by_similarity():
    chunks = rag_engine.search("résultat net", k=5)
    distances = [c["distance"] for c in chunks]
    assert distances == sorted(distances)
