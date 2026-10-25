"""Shared Gemini chat model helper (with retry on temporary overload / quota errors)."""
import os
import sys
import time
from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash")
# Lighter model for simple decisions (router, chart spec). Falls back to LLM_MODEL.
LLM_MODEL_FAST = os.getenv("LLM_MODEL_FAST", LLM_MODEL)

RETRY_WAITS = (5, 15, 30)  # seconds before retry 1, 2, 3
TRANSIENT_MARKERS = ("503", "429", "504", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED")


@lru_cache(maxsize=4)
def get_llm(model: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=model, temperature=0, timeout=60, max_retries=0)


def as_text(content) -> str:
    """Gemini may return a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)


def ask(prompt: str, fast: bool = False) -> str:
    """Call the model; retry a few times when Google is overloaded or the quota is hit."""
    llm = get_llm(LLM_MODEL_FAST if fast else LLM_MODEL)
    for wait in (*RETRY_WAITS, None):
        try:
            return as_text(llm.invoke(prompt).content).strip()
        except Exception as exc:
            transient = any(marker in str(exc) for marker in TRANSIENT_MARKERS)
            if wait is None or not transient:
                raise
            print(f"  (model busy, retrying in {wait}s...)", file=sys.stderr)
            time.sleep(wait)
