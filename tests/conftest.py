"""Fixtures compartidas de la suite de pruebas.

La suite no depende del archivo ``.env`` del desarrollador ni de credenciales
reales: cada prueba parte de un entorno determinista inyectado con
``monkeypatch`` y de una caché de configuración limpia.

Todas las rutas de trabajo (``BASE_DIR`` y, por tanto, ``data/documents``,
``data/vectorstore`` y ``data/audit``) se redirigen al directorio temporal de
pytest. Así el ``lifespan`` nunca crea directorios dentro del repositorio.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

from app.core.config import Settings, get_settings, reset_settings_cache

#: Variables mínimas que garantizan una configuración válida y aislada.
TEST_ENVIRONMENT: dict[str, str] = {
    "AI_PROVIDER": "openai",
    "OPENAI_API_KEY": "sk-test-not-real",
    "ENVIRONMENT": "testing",
    "LOG_JSON": "false",
    "LOG_LEVEL": "DEBUG",
    "DEBUG": "false",
    "APP_NAME": "Enterprise Legacy Assistant (test)",
    "APP_VERSION": "9.9.9",
    "CORS_ORIGINS": "http://localhost:3000,https://client.example.com",
}


@pytest.fixture
def settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[Settings]:
    """Proporciona una configuración válida y aislada del entorno local.

    Args:
        monkeypatch: utilidad de pytest que restaura las variables al terminar.
        tmp_path: directorio temporal exclusivo de la prueba; se usa como
            ``BASE_DIR`` para que ninguna ruta derivada apunte al repositorio.

    Yields:
        Instancia de configuración ya validada y cacheada.
    """
    # Desactiva la carga de `.env` durante la prueba. `pydantic-settings`
    # construye las fuentes en cada instanciación, por lo que basta con
    # neutralizar `env_file`; `monkeypatch` restaura el valor al terminar.
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    for name, value in TEST_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("BASE_DIR", str(tmp_path))

    reset_settings_cache()
    current_settings = get_settings()
    yield current_settings
    reset_settings_cache()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Proporciona un cliente HTTP con el ciclo de vida de la app ejecutado.

    La importación de ``app.main`` se hace de forma diferida para que el
    módulo se cargue después de inyectar el entorno de prueba.

    Args:
        settings: configuración de prueba de la que depende la aplicación.

    Yields:
        Cliente de pruebas de FastAPI.
    """
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


class NormalizedDeterministicEmbeddings(Embeddings):
    """Generador determinista de representaciones vectoriales unitarias para pruebas sin red."""

    def __init__(self, size: int = 64) -> None:
        """Inicializa el generador con la dimensión solicitada."""
        self.size = size

    def _embed(self, text: str) -> list[float]:
        """Calcula un vector unitario normalizado a partir del hash SHA-256 del texto."""
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        raw = [float((seed >> (i % 64)) & 0xFF) for i in range(self.size)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para una lista de textos."""
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Genera embedding para una consulta de texto."""
        return self._embed(text)


@pytest.fixture
def fake_embeddings() -> NormalizedDeterministicEmbeddings:
    """Proporciona un generador de embeddings determinista y normalizado para pruebas."""
    return NormalizedDeterministicEmbeddings()
