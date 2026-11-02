"""Punto de entrada ASGI del Enterprise Legacy Assistant.

Expone la aplicación FastAPI mínima de la Fase 1: arranque seguro, CORS
configurable y sondas de salud. Los routers de negocio (``/api/v1``) se
incorporan en fases posteriores.

Aislamiento de pruebas
----------------------
Este módulo construye ``app = create_app()`` al importarse porque ``uvicorn``
necesita un objeto ASGI resoluble por ruta (``app.main:app``). Esa construcción
lee la configuración del proceso. Por eso las pruebas **no importan este módulo
a nivel de módulo**: la fixture ``client`` inyecta primero el entorno con
``monkeypatch``, limpia la caché de ``get_settings`` y solo entonces importa
``create_app`` de forma diferida. Romper esa regla haría que la aplicación se
construyera con el ``.env`` real del desarrollador.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.models.health import HealthResponse, HealthStatus

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Gestiona el ciclo de vida del proceso ASGI.

    Al arrancar prepara los directorios de trabajo, configura el logging
    estructurado y registra un resumen de configuración sin secretos. Al
    apagarse deja una entrada explícita de cierre.

    Args:
        _application: instancia de FastAPI a la que pertenece el ciclo de vida.

    Yields:
        Control a la aplicación mientras permanece en ejecución.
    """
    settings = get_settings()
    await asyncio.to_thread(settings.ensure_directories)
    configure_logging(settings)
    logger.info("application_startup", **settings.redacted_summary())
    try:
        yield
    finally:
        logger.info("application_shutdown", app_name=settings.app_name)


def create_app() -> FastAPI:
    """Construye y devuelve la aplicación FastAPI configurada.

    El logging se configura aquí, y no solo en el ``lifespan``, para que las
    primeras líneas que emite ``uvicorn`` (antes de arrancar la aplicación) ya
    salgan en JSON. La llamada es idempotente y el ``lifespan`` la repite.

    Returns:
        Aplicación lista para ser servida por un servidor ASGI.
    """
    settings = get_settings()
    configure_logging(settings)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Asistente RAG empresarial sobre sistemas legados. "
            "Fase 1: configuración, logging estructurado y sonda de salud."
        ),
        debug=settings.debug,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Sonda de salud del servicio",
        description=(
            "Comprueba que el proceso está vivo y que la configuración es válida. "
            "No invoca al proveedor de IA ni a servicios externos."
        ),
    )
    async def health(
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> HealthResponse:
        """Devuelve el estado de salud del servicio.

        Args:
            current_settings: configuración inyectada por FastAPI.

        Returns:
            Respuesta con estado, metadatos de la aplicación y timestamp UTC.
        """
        return HealthResponse(
            status=HealthStatus.OK,
            app_name=current_settings.app_name,
            version=current_settings.app_version,
            environment=current_settings.environment,
            ai_provider=current_settings.ai_provider,
            timestamp=datetime.now(UTC),
        )

    @application.get(
        "/",
        tags=["system"],
        summary="Información básica de la aplicación",
        description="Devuelve el nombre, la versión y la ruta de la documentación OpenAPI.",
    )
    async def root(
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, str]:
        """Devuelve los datos identificativos mínimos del servicio.

        Args:
            current_settings: configuración inyectada por FastAPI.

        Returns:
            Diccionario con nombre, versión y ruta de Swagger UI.
        """
        return {
            "name": current_settings.app_name,
            "version": current_settings.app_version,
            "docs": "/docs",
        }

    return application


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
