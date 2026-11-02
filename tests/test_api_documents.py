"""Pruebas de integración para el endpoint de ingesta documental (/api/v1/documents/ingest).

Valida la invocación asíncrona de ingestión, la propagación del flag force_reindex
y la validación del esquema IngestSummary devuelto por la API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rag_service
from app.services.rag import IngestSummary, RAGService


def test_documents_ingest_without_force_reindex(client: TestClient) -> None:
    """Verifica que POST /api/v1/documents/ingest responda 200 con force_reindex=False."""
    mock_rag = MagicMock(spec=RAGService)
    expected_summary = IngestSummary(
        total_files=3,
        total_chunks=12,
        documents=["manual_ops.md", "guia_ldap.md", "procedimiento_vpn.md"],
    )
    mock_rag.aingest_documents = AsyncMock(return_value=expected_summary)

    client.app.dependency_overrides[get_rag_service] = lambda: mock_rag
    try:
        response = client.post("/api/v1/documents/ingest")
        assert response.status_code == 200

        data: dict[str, Any] = response.json()
        assert data["total_files"] == 3
        assert data["total_chunks"] == 12
        assert len(data["documents"]) == 3
        assert "manual_ops.md" in data["documents"]

        mock_rag.aingest_documents.assert_awaited_once_with(force_reindex=False)
    finally:
        client.app.dependency_overrides.pop(get_rag_service, None)


@pytest.mark.parametrize(
    ("query_param", "expected_flag"),
    [
        ("?force_reindex=true", True),
        ("?force_reindex=1", True),
        ("?force_reindex=false", False),
        ("?force_reindex=0", False),
    ],
)
def test_documents_ingest_with_force_reindex_parameter(
    client: TestClient,
    query_param: str,
    expected_flag: bool,
) -> None:
    """Verifica que el parámetro query force_reindex se parseee e inyecte correctamente."""
    mock_rag = MagicMock(spec=RAGService)
    mock_rag.aingest_documents = AsyncMock(
        return_value=IngestSummary(
            total_files=2,
            total_chunks=8,
            documents=["manual1.md", "manual2.md"],
        )
    )

    client.app.dependency_overrides[get_rag_service] = lambda: mock_rag
    try:
        response = client.post(f"/api/v1/documents/ingest{query_param}")
        assert response.status_code == 200
        mock_rag.aingest_documents.assert_awaited_once_with(force_reindex=expected_flag)
    finally:
        client.app.dependency_overrides.pop(get_rag_service, None)


def test_documents_ingest_invalid_force_reindex_returns_422(client: TestClient) -> None:
    """Verifica que un valor no booleano en force_reindex retorne 422 Unprocessable Entity."""
    response = client.post("/api/v1/documents/ingest?force_reindex=invalido")
    assert response.status_code == 422
    assert "detail" in response.json()
