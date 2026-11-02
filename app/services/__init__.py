"""Capa de servicios del Enterprise Legacy Assistant.

Expone los componentes de persistencia vectorial y el pipeline RAG para
la recuperación contextual y fundamentación de respuestas.
"""

from __future__ import annotations

from app.services.rag import IngestSummary, RAGService
from app.services.vector_store import VectorStoreService

__all__ = [
    "IngestSummary",
    "RAGService",
    "VectorStoreService",
]
