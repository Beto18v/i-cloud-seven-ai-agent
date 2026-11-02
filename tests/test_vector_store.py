"""Pruebas unitarias para el servicio de almacén vectorial persistente (ChromaDB)."""

from __future__ import annotations

import pytest
from langchain_core.documents import Document
from tests.conftest import NormalizedDeterministicEmbeddings

from app.core.config import Settings
from app.services.vector_store import VectorStoreService


def test_vector_store_initialization(
    settings: Settings, fake_embeddings: NormalizedDeterministicEmbeddings
) -> None:
    """Verifica que el servicio vectorial inicializa correctamente la colección."""
    service = VectorStoreService(settings=settings, embeddings=fake_embeddings)
    assert service.settings == settings
    assert service.embeddings == fake_embeddings
    assert service.count() == 0


def test_vector_store_add_documents_and_count(
    settings: Settings, fake_embeddings: NormalizedDeterministicEmbeddings
) -> None:
    """Valida la inserción de documentos y el conteo exacto de elementos."""
    service = VectorStoreService(settings=settings, embeddings=fake_embeddings)
    docs = [
        Document(page_content="Procedimiento de reinicio 1", metadata={"source": "m1.md"}),
        Document(page_content="Procedimiento de reinicio 2", metadata={"source": "m2.md"}),
    ]
    ids = service.add_documents(docs)
    assert len(ids) == 2
    assert service.count() == 2

    empty_ids = service.add_documents([])
    assert empty_ids == []
    assert service.count() == 2


def test_vector_store_similarity_search(
    settings: Settings, fake_embeddings: NormalizedDeterministicEmbeddings
) -> None:
    """Comprueba que la búsqueda retorne tuplas de documento y puntuación normalizada."""
    service = VectorStoreService(settings=settings, embeddings=fake_embeddings)
    docs = [
        Document(page_content="reinicio de servicio legado", metadata={"source": "sync.md"}),
        Document(page_content="consulta de base de datos", metadata={"source": "db.md"}),
    ]
    service.add_documents(docs)

    results = service.similarity_search_with_relevance_scores("reinicio de servicio legado", k=1)
    assert len(results) == 1
    doc, score = results[0]
    assert doc.metadata["source"] == "sync.md"
    assert 0.0 <= score <= 1.0


def test_vector_store_empty_or_blank_query_returns_empty(
    settings: Settings, fake_embeddings: NormalizedDeterministicEmbeddings
) -> None:
    """Asegura que consultas vacías o de puros espacios no fallen y retornen lista vacía."""
    service = VectorStoreService(settings=settings, embeddings=fake_embeddings)
    assert service.similarity_search_with_relevance_scores("") == []
    assert service.similarity_search_with_relevance_scores("   ") == []


def test_vector_store_reset(
    settings: Settings, fake_embeddings: NormalizedDeterministicEmbeddings
) -> None:
    """Valida que el reseteo purgue por completo la colección activa."""
    service = VectorStoreService(settings=settings, embeddings=fake_embeddings)
    service.add_documents([Document(page_content="temp", metadata={"source": "temp.md"})])
    assert service.count() == 1

    service.reset()
    assert service.count() == 0


@pytest.mark.asyncio
async def test_vector_store_async_methods(
    settings: Settings, fake_embeddings: NormalizedDeterministicEmbeddings
) -> None:
    """Verifica que las variantes asíncronas no bloqueantes funcionen como se espera."""
    service = VectorStoreService(settings=settings, embeddings=fake_embeddings)
    docs = [Document(page_content="async doc", metadata={"source": "async.md"})]

    ids = await service.aadd_documents(docs)
    assert len(ids) == 1

    total = await service.acount()
    assert total == 1

    results = await service.asimilarity_search_with_relevance_scores("async doc", k=1)
    assert len(results) == 1

    await service.areset()
    assert await service.acount() == 0
