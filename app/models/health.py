"""Contratos de datos del chequeo de salud del servicio.

El endpoint ``GET /health`` es una sonda de *liveness/readiness*: valida que el
proceso está vivo y que la configuración se cargó correctamente, **sin**
invocar al proveedor de IA ni a ningún servicio externo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import AIProvider, Environment


class HealthStatus(StrEnum):
    """Estado de salud reportado por la sonda."""

    OK = "ok"
    DEGRADED = "degraded"


class HealthResponse(BaseModel):
    """Respuesta del endpoint de salud.

    Attributes:
        status: estado global del servicio.
        app_name: nombre de la aplicación tomado de la configuración.
        version: versión semántica de la aplicación.
        environment: entorno lógico en el que corre el proceso.
        ai_provider: proveedor de IA configurado (no implica conectividad).
        timestamp: instante de la respuesta en UTC con zona horaria.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "app_name": "Enterprise Legacy Assistant",
                    "version": "0.1.0",
                    "environment": "production",
                    "ai_provider": "azure_openai",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            ]
        },
    )

    status: HealthStatus = Field(
        description="Estado global del servicio: 'ok' o 'degraded'.",
    )
    app_name: str = Field(
        min_length=1,
        max_length=120,
        description="Nombre de la aplicación configurado en el servicio.",
    )
    version: str = Field(
        pattern=r"^\d+\.\d+\.\d+$",
        description="Versión semántica de la aplicación.",
    )
    environment: Environment = Field(
        description="Entorno lógico de ejecución (development, testing, staging o production).",
    )
    ai_provider: AIProvider = Field(
        description="Proveedor de IA configurado; no se comprueba su conectividad.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Instante UTC en el que se generó la respuesta.",
    )

    @field_validator("timestamp")
    @classmethod
    def _ensure_utc_aware(cls, value: datetime) -> datetime:
        """Normaliza el timestamp a UTC y rechaza valores sin zona horaria.

        Args:
            value: instante recibido durante la validación.

        Returns:
            El instante convertido a UTC.

        Raises:
            ValueError: si el instante no incluye información de zona horaria.
        """
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp debe incluir zona horaria (UTC).")
        return value.astimezone(UTC)


__all__ = ["HealthResponse", "HealthStatus"]
