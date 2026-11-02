"""Pruebas de las sondas de salud y de la documentación OpenAPI."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import PROJECT_ROOT, Settings
from app.models.health import HealthResponse, HealthStatus


def test_health_returns_ok_with_expected_schema(
    client: TestClient,
    settings: Settings,
) -> None:
    """``GET /health`` responde 200 con el contrato completo y estado ok."""
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == set(HealthResponse.model_fields)

    validated = HealthResponse.model_validate(payload)
    assert validated.status is HealthStatus.OK
    assert validated.app_name == settings.app_name
    assert validated.version == settings.app_version
    assert validated.environment is settings.environment
    assert validated.ai_provider is settings.ai_provider
    assert validated.timestamp.utcoffset() == timedelta(0)


def test_openapi_docs_are_available(client: TestClient) -> None:
    """Swagger UI y el esquema OpenAPI se sirven sin servicios externos."""
    docs_response = client.get("/docs")
    openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    assert "/health" in openapi_response.json()["paths"]


def test_root_returns_identifying_metadata(client: TestClient, settings: Settings) -> None:
    """La raíz expone nombre, versión y ruta de la documentación."""
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


def test_lifespan_creates_directories_under_tmp_path(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
) -> None:
    """El ``lifespan`` crea sus directorios fuera del repositorio."""
    assert client.get("/health").status_code == 200
    assert settings.base_dir.resolve() == tmp_path.resolve()

    expected_directories = (
        settings.documents_dir,
        settings.vector_store_dir,
        settings.audit_file.parent,
    )
    for directory in expected_directories:
        assert directory.is_dir()
        assert directory.is_relative_to(tmp_path)
        assert not directory.is_relative_to(PROJECT_ROOT)
