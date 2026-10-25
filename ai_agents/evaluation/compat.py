"""Compatibility shim: import this module BEFORE importing ragas.

ragas 0.4.x imports Vertex AI classes from langchain-community, which no longer
ships them (langchain-community 0.4.x). We never use Vertex AI, so we register
harmless placeholders and ragas imports normally.
"""
import sys
import types


class _VertexUnavailable:
    """Placeholder for a Vertex AI class that is not used in this project."""


def install() -> None:
    name = "langchain_community.chat_models.vertexai"
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.ChatVertexAI = _VertexUnavailable
        sys.modules[name] = module
    import langchain_community.llms as llms

    if not hasattr(llms, "VertexAI"):
        llms.VertexAI = _VertexUnavailable


install()
