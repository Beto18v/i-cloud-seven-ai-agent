"""Contratos de datos para el dominio de tickets e incidentes del sistema legado.

Define las entidades, enumeraciones y esquemas de entrada y salida utilizados
para consultar el estado de tickets existentes y clasificar la severidad y SLA
de nuevos incidentes según las políticas operativas (D10).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TicketStatus(StrEnum):
    """Estados válidos del ciclo de vida de un ticket de soporte."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(StrEnum):
    """Nivel de prioridad o severidad técnica compartida (D10).

    Conforme a la decisión D10 de la arquitectura, se comparte este enum entre
    la prioridad operativa del ticket (`Ticket.priority`) y la severidad técnica
    del incidente (`IncidentClassification.severity`), dado que en el alcance de
    la solución el mapeo es 1:1.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Ticket(BaseModel):
    """Entidad inmutable que representa un ticket en el sistema legado de soporte.

    Attributes:
        ticket_id: identificador único con patrón TCK-NNN a TCK-NNNNNN.
        title: resumen o título descriptivo del ticket.
        description: detalle descriptivo del problema reportado.
        status: estado operativo actual del ticket.
        priority: prioridad técnica/operativa asignada.
        reported_by: identificador o nombre del usuario que reportó el ticket.
        assigned_to: identificador del agente o área asignada, o None.
        created_at: instante de creación del ticket en tiempo universal UTC.
        updated_at: instante de última actualización del ticket en tiempo universal UTC.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "ticket_id": "TCK-104",
                    "title": "Falla de conectividad VPN",
                    "description": "Usuarios remotos experimentan desconexiones intermitentes.",
                    "status": "open",
                    "priority": "high",
                    "reported_by": "maria.gonzalez",
                    "assigned_to": "infra.soporte",
                    "created_at": "2026-01-15T08:30:00Z",
                    "updated_at": "2026-01-15T09:00:00Z",
                }
            ]
        },
    )

    ticket_id: str = Field(
        pattern=r"^TCK-\d{3,6}$",
        description="Identificador del ticket con prefijo TCK- seguido de 3 a 6 dígitos numéricos.",
    )
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Título descriptivo del ticket.",
    )
    description: str = Field(
        min_length=1,
        max_length=2000,
        description="Descripción detallada del ticket o problema.",
    )
    status: TicketStatus = Field(
        description="Estado operativo actual del ticket.",
    )
    priority: Priority = Field(
        description="Prioridad del ticket según la clasificación compartida (D10).",
    )
    reported_by: str = Field(
        min_length=1,
        max_length=100,
        description="Identificador o nombre del usuario o área reportante.",
    )
    assigned_to: str | None = Field(
        default=None,
        max_length=100,
        description="Identificador del técnico o equipo asignado, o None si no está asignado.",
    )
    created_at: datetime = Field(
        description="Instante de creación del ticket normalizado a UTC.",
    )
    updated_at: datetime = Field(
        description="Instante de última actualización del ticket normalizado a UTC.",
    )

    @field_validator("created_at", "updated_at")
    @classmethod
    def _ensure_utc_aware(cls, value: datetime) -> datetime:
        """Normaliza el timestamp a UTC y rechaza valores sin zona horaria.

        Args:
            value: instante recibido durante la validación.

        Returns:
            El instante convertido a UTC con tzinfo explícito.

        Raises:
            ValueError: si el instante recibido carece de información de zona horaria.
        """
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("El timestamp debe incluir información de zona horaria (UTC).")
        return value.astimezone(UTC)


class IncidentInput(BaseModel):
    """Datos de entrada requeridos para evaluar y clasificar un incidente operativo.

    Attributes:
        service: nombre del servicio o plataforma afectado.
        affected_users: número estimado de usuarios impactados (mayor o igual a cero).
        is_critical_service: indicador de si el servicio está catalogado como misión crítica.
        description: resumen o detalles contextuales adicionales del incidente.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "service": "Portal Transaccional",
                    "affected_users": 150,
                    "is_critical_service": True,
                    "description": "Lentitud extrema y errores 504 en la pasarela de pagos.",
                }
            ]
        },
    )

    service: str = Field(
        min_length=1,
        max_length=100,
        description="Nombre del servicio o infraestructura impactada.",
    )
    affected_users: int = Field(
        ge=0,
        description="Cantidad estimada de usuarios o clientes afectados.",
    )
    is_critical_service: bool = Field(
        default=False,
        description="Indica si el servicio afectado es considerado crítico para el negocio.",
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="Descripción contextual o detalles operativos del incidente.",
    )


class IncidentClassification(BaseModel):
    """Resultado inmutable de la clasificación automatizada de un incidente.

    Attributes:
        severity: nivel de severidad asignado conforme al enum compartido Priority (D10).
        sla_hours: horas de resolución acordadas (entero estrictamente positivo).
        requires_escalation: indica si el incidente requiere escalamiento inmediato.
        rationale: explicación o justificación técnica y cuantitativa de la clasificación.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "severity": "critical",
                    "sla_hours": 2,
                    "requires_escalation": True,
                    "rationale": "Servicio crítico afectado con más de 100 usuarios impactados.",
                }
            ]
        },
    )

    severity: Priority = Field(
        description="Severidad técnica determinada para el incidente (D10).",
    )
    sla_hours: int = Field(
        gt=0,
        description="Acuerdo de nivel de servicio en horas para la resolución (debe ser > 0).",
    )
    requires_escalation: bool = Field(
        description="Indica si la criticidad exige notificación o escalamiento inmediato.",
    )
    rationale: str = Field(
        min_length=1,
        description="Justificación objetiva de las reglas aplicadas en la clasificación.",
    )


__all__ = [
    "IncidentClassification",
    "IncidentInput",
    "Priority",
    "Ticket",
    "TicketStatus",
]
