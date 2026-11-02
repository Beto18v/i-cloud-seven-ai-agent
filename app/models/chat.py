"""Contratos de datos para el pipeline de chat, recuperación y auditoría de herramientas.

Define las solicitudes y respuestas de la API del asistente conversacional,
incluyendo citas bibliográficas de fuentes recuperadas (RAG), trazabilidad
sanitizada de herramientas ejecutadas (D12) y fundamentación determinista (D11).
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """Solicitud de consulta entrante para el asistente conversacional.

    Attributes:
        query: texto de la consulta o mensaje (1 a 2000 caracteres, no solo espacios).
        session_id: identificador opcional de sesión (máx 64 chars; vacíos pasan a None).
        user_id: identificador opcional del usuario que realiza la consulta (máx 100).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "query": "¿Cuál es el estado del ticket TCK-104?",
                    "session_id": "sess-user-001",
                    "user_id": "usr-admin-01",
                }
            ]
        },
    )

    query: str = Field(
        min_length=1,
        max_length=2000,
        validation_alias=AliasChoices("query", "message"),
        description="Consulta textual del usuario; admite el alias alternativo 'message'.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=64,
        description="Identificador de sesión para persistencia de contexto conversacional.",
    )
    user_id: str | None = Field(
        default=None,
        max_length=100,
        description="Identificador opcional del usuario remitente.",
    )

    @field_validator("query", mode="before")
    @classmethod
    def _validate_and_strip_query(cls, value: object) -> object:
        """Elimina espacios superfluos y rechaza cadenas vacías o solo compuestas por espacios.

        Args:
            value: valor recibido antes de la validación estructural.

        Returns:
            Cadena recortada si es texto.

        Raises:
            ValueError: si la cadena tras el recorte queda vacía.
        """
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError(
                    "La consulta (query) no puede estar vacía ni contener solo espacios en blanco."
                )
            return stripped
        return value

    @field_validator("session_id", mode="before")
    @classmethod
    def _normalize_session_id(cls, value: object) -> object:
        """Normaliza el session_id a None si se provee una cadena vacía o con solo espacios.

        Args:
            value: valor recibido antes de la validación estructural.

        Returns:
            Cadena recortada o None si la cadena queda vacía.
        """
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value


class SourceReference(BaseModel):
    """Cita bibliográfica inmutable de un fragmento de conocimiento recuperado.

    Attributes:
        document: ruta relativa o nombre del documento fuente indexado.
        chunk_id: identificador único del fragmento dentro del índice vectorial.
        score: puntuación de similitud semántica normalizada en el rango [0.0, 1.0].
        excerpt: fragmento o extracto representativo del contenido textual (1 a 500 caracteres).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "document": "manual_procedimientos.md",
                    "chunk_id": "manual_procedimientos.md_c001",
                    "score": 0.88,
                    "excerpt": "Para reiniciar ejecute systemctl restart auth-svc.",
                }
            ]
        },
    )

    document: str = Field(
        min_length=1,
        description="Nombre o ruta del archivo documental de origen.",
    )
    chunk_id: str = Field(
        min_length=1,
        description="Identificador unívoco del fragmento vectorial.",
    )
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Puntuación de similitud semántica en escala de 0.0 a 1.0.",
    )
    excerpt: str = Field(
        min_length=1,
        max_length=500,
        description="Extracto textual relevante del fragmento citado.",
    )


class ToolCallSummary(BaseModel):
    """Resumen inmutable y sanitizado de la ejecución de una herramienta (D12).

    Attributes:
        name: nombre identificador de la herramienta ejecutada.
        success: indica si la herramienta concluyó con éxito o generó error.
        latency_ms: duración de la ejecución en milisegundos (mayor o igual a cero).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "get_ticket_status",
                    "success": True,
                    "latency_ms": 14.5,
                }
            ]
        },
    )

    name: str = Field(
        min_length=1,
        description="Nombre de la función o herramienta invocada.",
    )
    success: bool = Field(
        description="Indica si la invocación de la herramienta finalizó exitosamente.",
    )
    latency_ms: float = Field(
        ge=0.0,
        description="Duración de la ejecución de la herramienta en milisegundos.",
    )


class ChatResponse(BaseModel):
    """Respuesta inmutable generada por el asistente conversacional.

    Attributes:
        answer: síntesis textual generada por el modelo de lenguaje.
        sources: lista de fragmentos bibliográficos recuperados del almacén de conocimiento.
        tool_calls: lista de ejecuciones sanitizadas de herramientas invocadas (D12).
        grounded: booleano de fundamentación D11 (max(score) >= SIMILARITY_THRESHOLD).
        session_id: identificador de la sesión asociada a la conversación.
        latency_ms: tiempo total transcurrido en procesar la consulta en milisegundos.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "answer": "El ticket TCK-104 está abierto con prioridad alta.",
                    "sources": [],
                    "tool_calls": [
                        {
                            "name": "get_ticket_status",
                            "success": True,
                            "latency_ms": 12.3,
                        }
                    ],
                    "grounded": False,
                    "session_id": "sess-abc-123",
                    "latency_ms": 420.5,
                }
            ]
        },
    )

    answer: str = Field(
        min_length=1,
        description="Texto de la respuesta sintetizada para el usuario.",
    )
    sources: list[SourceReference] = Field(
        default_factory=list,
        description="Colección de fuentes documentales que sustentan la respuesta.",
    )
    tool_calls: list[ToolCallSummary] = Field(
        default_factory=list,
        description="Resumen sanitizado de herramientas ejecutadas durante el flujo (D12).",
    )
    grounded: bool = Field(
        description=(
            "Indica si la respuesta está fundamentada en fuentes documentales (D11). "
            "Se calcula exclusivamente determinando si max(score) >= SIMILARITY_THRESHOLD, "
            "sin delegar en el LLM ni inferir a partir del texto de la respuesta. "
            "Un valor False indica únicamente ausencia de contexto documental suficiente."
        ),
    )
    session_id: str = Field(
        min_length=1,
        max_length=64,
        description="Identificador de la sesión conversacional.",
    )
    latency_ms: float = Field(
        ge=0.0,
        description="Latencia total de procesamiento de la solicitud en milisegundos.",
    )


__all__ = [
    "ChatRequest",
    "ChatResponse",
    "SourceReference",
    "ToolCallSummary",
]
