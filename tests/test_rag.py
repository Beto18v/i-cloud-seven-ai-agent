"""Pruebas unitarias para el servicio RAG (ingesta, segmentación y recuperación)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import NormalizedDeterministicEmbeddings

from app.core.config import Settings
from app.models.chat import SourceReference
from app.services.rag import IngestSummary, RAGService
from app.services.vector_store import VectorStoreService


@pytest.fixture
def rag_service(
    settings: Settings, fake_embeddings: NormalizedDeterministicEmbeddings
) -> RAGService:
    """Proporciona una instancia de RAGService con almacén vectorial aislado en memoria/tmp."""
    vector_store = VectorStoreService(settings=settings, embeddings=fake_embeddings)
    return RAGService(settings=settings, vector_store=vector_store)


def test_rag_ingest_missing_or_empty_directory(rag_service: RAGService, tmp_path: Path) -> None:
    """Valida el manejo defensivo ante directorios inexistentes o sin archivos markdown."""
    missing_dir = tmp_path / "non_existent"
    summary_missing = rag_service.ingest_documents(docs_dir=missing_dir)
    assert summary_missing.total_files == 0
    assert summary_missing.total_chunks == 0

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    summary_empty = rag_service.ingest_documents(docs_dir=empty_dir)
    assert summary_empty.total_files == 0
    assert summary_empty.total_chunks == 0


def test_rag_ingest_documents(rag_service: RAGService, tmp_path: Path) -> None:
    """Comprueba la segmentación semántica y la inserción indexada con metadatos."""
    test_docs_dir = tmp_path / "docs"
    test_docs_dir.mkdir()

    doc1 = test_docs_dir / "doc1.md"
    doc1.write_text(
        "# Procedimiento A\n\nEste es el contenido del procedimiento operativo A.\n\n"
        "## Subsección 1\n\nPasos detallados para ejecutar la acción correctamente.",
        encoding="utf-8",
    )

    doc2 = test_docs_dir / "doc2.md"
    doc2.write_text(
        "# Políticas B\n\nInformación sobre niveles de servicio y escalamiento.",
        encoding="utf-8",
    )

    summary: IngestSummary = rag_service.ingest_documents(docs_dir=test_docs_dir)
    assert summary.total_files == 2
    assert summary.total_chunks >= 2
    assert "doc1.md" in summary.documents
    assert "doc2.md" in summary.documents
    assert rag_service.vector_store.count() == summary.total_chunks

    # Prueba de force_reindex
    summary_reindex = rag_service.ingest_documents(docs_dir=test_docs_dir, force_reindex=True)
    assert summary_reindex.total_files == 2
    assert rag_service.vector_store.count() == summary_reindex.total_chunks


def test_rag_retrieve_formatting(rag_service: RAGService, tmp_path: Path) -> None:
    """Verifica que retrieve mapee adecuadamente a SourceReference con scores acotados."""
    test_docs_dir = tmp_path / "docs"
    test_docs_dir.mkdir()
    (test_docs_dir / "manual_operaciones.md").write_text(
        "# Manual\n\nProcedimiento operativo para reiniciar el servicio de sincronización legado.",
        encoding="utf-8",
    )
    rag_service.ingest_documents(docs_dir=test_docs_dir)

    sources = rag_service.retrieve(
        query="Procedimiento operativo para reiniciar el servicio de sincronización legado",
        top_k=2,
    )
    assert len(sources) >= 1
    first = sources[0]
    assert isinstance(first, SourceReference)
    assert first.document == "manual_operaciones.md"
    assert "manual_operaciones" in first.chunk_id
    assert 0.0 <= first.score <= 1.0
    assert len(first.excerpt) <= 500


def test_rag_retrieve_empty_query_returns_empty(rag_service: RAGService) -> None:
    """Asegura que consultas vacías o de puros espacios retornen lista vacía."""
    assert rag_service.retrieve("") == []
    assert rag_service.retrieve("   ") == []


def test_rag_is_grounded_evaluation(rag_service: RAGService) -> None:
    """Valida la regla determinista de fundamentación D11 según similarity_threshold."""
    threshold = rag_service.settings.similarity_threshold  # default 0.70

    # Sin fuentes
    assert rag_service.is_grounded([]) is False

    # Fuentes por debajo del umbral
    low_sources = [
        SourceReference(
            document="d1.md",
            chunk_id="c1",
            score=round(threshold - 0.05, 4),
            excerpt="texto",
        )
    ]
    assert rag_service.is_grounded(low_sources) is False

    # Fuentes por encima o iguales al umbral
    high_sources = [
        SourceReference(
            document="d1.md",
            chunk_id="c1",
            score=round(threshold + 0.05, 4),
            excerpt="texto",
        )
    ]
    assert rag_service.is_grounded(high_sources) is True


@pytest.mark.asyncio
async def test_rag_async_methods(rag_service: RAGService, tmp_path: Path) -> None:
    """Verifica que las variantes asíncronas no bloqueantes funcionen correctamente."""
    test_docs_dir = tmp_path / "docs_async"
    test_docs_dir.mkdir()
    (test_docs_dir / "async_manual.md").write_text(
        "# Async Title\n\nContenido de prueba asíncrona.", encoding="utf-8"
    )

    summary = await rag_service.aingest_documents(docs_dir=test_docs_dir)
    assert summary.total_files == 1

    results = await rag_service.aretrieve("Contenido de prueba asíncrona")
    assert len(results) >= 1
