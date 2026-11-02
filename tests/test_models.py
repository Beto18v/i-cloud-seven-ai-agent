"""Pruebas unitarias exhaustivas para los contratos de datos de la Fase 1.

Verifica la integridad de los modelos de dominio, validaciones estructurales,
regex de identificadores, restricciones de inmutabilidad (frozen), rechazo de
campos adicionales (extra='forbid'), normalización de cadenas y serialización.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import app.models as models_module
from app.models import (
    ChatRequest,
    ChatResponse,
    IncidentClassification,
    IncidentInput,
    Priority,
    SourceReference,
    Ticket,
    TicketStatus,
    ToolCallSummary,
)

# =============================================================================
# 1. Exportaciones y catálogo del paquete app.models
# =============================================================================


def test_models_module_exports_expected_symbols() -> None:
    """``app.models`` expone todos los contratos y enums públicos en su ``__all__``."""
    expected_symbols = {
        "ChatRequest",
        "ChatResponse",
        "HealthResponse",
        "HealthStatus",
        "IncidentClassification",
        "IncidentInput",
        "Priority",
        "SourceReference",
        "Ticket",
        "TicketStatus",
        "ToolCallSummary",
    }
    assert set(models_module.__all__) == expected_symbols
    for symbol_name in expected_symbols:
        assert hasattr(models_module, symbol_name)


# =============================================================================
# 2. Enumeraciones de dominio (TicketStatus, Priority)
# =============================================================================


def test_ticket_status_enum_values() -> None:
    """``TicketStatus`` define los estados esperados y es comparable con cadenas."""
    expected_values = {"open", "in_progress", "resolved", "closed"}
    actual_values = {status.value for status in TicketStatus}
    assert actual_values == expected_values
    assert TicketStatus.OPEN == "open"
    assert TicketStatus.IN_PROGRESS == "in_progress"
    assert TicketStatus.RESOLVED == "resolved"
    assert TicketStatus.CLOSED == "closed"
    assert isinstance(TicketStatus.OPEN, str)


def test_priority_enum_shared_d10() -> None:
    """``Priority`` define los niveles esperados y cumple con D10 como enum compartido."""
    expected_values = {"low", "medium", "high", "critical"}
    actual_values = {priority.value for priority in Priority}
    assert actual_values == expected_values
    assert Priority.LOW == "low"
    assert Priority.MEDIUM == "medium"
    assert Priority.HIGH == "high"
    assert Priority.CRITICAL == "critical"
    assert isinstance(Priority.HIGH, str)


# =============================================================================
# 3. Entidad Ticket
# =============================================================================


def _build_valid_ticket_kwargs() -> dict[str, object]:
    """Genera un diccionario base con atributos válidos para instanciar Ticket."""
    return {
        "ticket_id": "TCK-104",
        "title": "Falla de conectividad en sucursal",
        "description": "El enlace principal se encuentra caído tras tormenta eléctrica.",
        "status": TicketStatus.OPEN,
        "priority": Priority.HIGH,
        "reported_by": "operaciones.red",
        "assigned_to": "infra.soporte",
        "created_at": datetime(2026, 1, 15, 8, 30, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
    }


def test_ticket_valid_creation_and_defaults() -> None:
    """``Ticket`` se instancia correctamente con todos sus campos y respeta defaults."""
    kwargs = _build_valid_ticket_kwargs()
    ticket = Ticket.model_validate(kwargs)

    assert ticket.ticket_id == "TCK-104"
    assert ticket.title == "Falla de conectividad en sucursal"
    assert ticket.status is TicketStatus.OPEN
    assert ticket.priority is Priority.HIGH
    assert ticket.assigned_to == "infra.soporte"
    assert ticket.created_at.tzinfo == UTC
    assert ticket.updated_at.tzinfo == UTC

    # Default de assigned_to debe ser None
    kwargs_no_assigned = dict(kwargs)
    kwargs_no_assigned.pop("assigned_to")
    ticket_unassigned = Ticket.model_validate(kwargs_no_assigned)
    assert ticket_unassigned.assigned_to is None


@pytest.mark.parametrize(
    "valid_id",
    [
        "TCK-104",  # Caso TC-02
        "TCK-1001",  # 4 dígitos
        "TCK-100",  # Mínimo 3 dígitos
        "TCK-999999",  # Máximo 6 dígitos
    ],
)
def test_ticket_id_pattern_valid_cases(valid_id: str) -> None:
    """``Ticket.ticket_id`` acepta identificadores con patrón TCK- seguido de 3 a 6 dígitos."""
    kwargs = _build_valid_ticket_kwargs()
    kwargs["ticket_id"] = valid_id
    ticket = Ticket.model_validate(kwargs)
    assert ticket.ticket_id == valid_id


@pytest.mark.parametrize(
    "invalid_id",
    [
        "TCK-10",  # Solo 2 dígitos (mínimo es 3)
        "TCK-1234567",  # 7 dígitos (máximo es 6)
        "TCK-abc",  # Letras en lugar de números
        "tck-104",  # Prefijo en minúsculas
        "TCK_104",  # Guión bajo
        "104",  # Sin prefijo
        "TCK-",  # Sin dígitos
        "",  # Cadena vacía
        " TCK-104",  # Espacio al inicio
    ],
)
def test_ticket_id_pattern_invalid_cases(invalid_id: str) -> None:
    """``Ticket.ticket_id`` rechaza formatos que no cumplan estrictamente r'^TCK-\\d{3,6}$'."""
    kwargs = _build_valid_ticket_kwargs()
    kwargs["ticket_id"] = invalid_id
    with pytest.raises(ValidationError) as exc_info:
        Ticket.model_validate(kwargs)
    assert "ticket_id" in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("title", ""),  # min_length 1
        ("title", "A" * 201),  # max_length 200
        ("description", ""),  # min_length 1
        ("description", "D" * 2001),  # max_length 2000
        ("reported_by", ""),  # min_length 1
        ("reported_by", "U" * 101),  # max_length 100
        ("assigned_to", "T" * 101),  # max_length 100
    ],
)
def test_ticket_string_boundaries(field_name: str, invalid_value: str) -> None:
    """``Ticket`` valida longitudes mínimas y máximas de sus campos de texto."""
    kwargs = _build_valid_ticket_kwargs()
    kwargs[field_name] = invalid_value
    with pytest.raises(ValidationError) as exc_info:
        Ticket.model_validate(kwargs)
    assert field_name in str(exc_info.value)


def test_ticket_datetime_utc_normalization_and_rejection() -> None:
    """``Ticket`` normaliza instantes con timezone a UTC y rechaza instantes naive."""
    kwargs = _build_valid_ticket_kwargs()

    # Datetime con zona horaria UTC explícita
    kwargs["created_at"] = datetime(2026, 1, 15, 8, 30, tzinfo=UTC)
    ticket_utc = Ticket.model_validate(kwargs)
    assert ticket_utc.created_at.tzinfo == UTC
    assert ticket_utc.created_at.utcoffset() == timedelta(0)

    # Datetime con zona horaria no-UTC (+02:00) debe convertirse a UTC (06:30)
    tz_plus_two = timezone(timedelta(hours=2))
    kwargs["created_at"] = datetime(2026, 1, 15, 8, 30, tzinfo=tz_plus_two)
    ticket_offset = Ticket.model_validate(kwargs)
    assert ticket_offset.created_at.tzinfo == UTC
    assert ticket_offset.created_at.hour == 6
    assert ticket_offset.created_at.minute == 30

    # Datetime ingenuo (sin zona horaria) debe ser rechazado
    kwargs["created_at"] = datetime(2026, 1, 15, 8, 30)
    with pytest.raises(ValidationError) as exc_info_naive:
        Ticket.model_validate(kwargs)
    assert "created_at" in str(exc_info_naive.value)
    assert "zona horaria" in str(exc_info_naive.value)

    # updated_at también rechaza datetimes ingenuos
    kwargs["created_at"] = datetime(2026, 1, 15, 8, 30, tzinfo=UTC)
    kwargs["updated_at"] = datetime(2026, 1, 15, 9, 0)
    with pytest.raises(ValidationError) as exc_info_updated:
        Ticket.model_validate(kwargs)
    assert "updated_at" in str(exc_info_updated.value)


def test_ticket_immutability_frozen() -> None:
    """``Ticket`` es inmutable (frozen=True) y rechaza modificaciones en sus atributos."""
    ticket = Ticket.model_validate(_build_valid_ticket_kwargs())
    with pytest.raises(ValidationError):
        ticket.status = TicketStatus.CLOSED  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ticket.title = "Nuevo título"  # type: ignore[misc]


def test_ticket_extra_fields_forbidden() -> None:
    """``Ticket`` rechaza atributos no declarados (extra='forbid')."""
    kwargs = _build_valid_ticket_kwargs()
    kwargs["unknown_column"] = "valor_prohibido"
    with pytest.raises(ValidationError) as exc_info:
        Ticket.model_validate(kwargs)
    assert "extra_forbidden" in str(exc_info.value)


# =============================================================================
# 4. Modelos de Incidentes (IncidentInput, IncidentClassification)
# =============================================================================


def test_incident_input_valid_creation_and_defaults() -> None:
    """``IncidentInput`` asigna correctamente defaults para is_critical_service y description."""
    incident = IncidentInput(service="Auth-Service", affected_users=45)
    assert incident.service == "Auth-Service"
    assert incident.affected_users == 45
    assert incident.is_critical_service is False
    assert incident.description == ""

    # Puede mutar ya que no es frozen
    incident.description = "Detalle adicional"
    assert incident.description == "Detalle adicional"


def test_incident_input_affected_users_validation() -> None:
    """``IncidentInput.affected_users`` admite cero o más y rechaza negativos."""
    valid_zero = IncidentInput(service="Web", affected_users=0)
    assert valid_zero.affected_users == 0

    with pytest.raises(ValidationError) as exc_info:
        IncidentInput(service="Web", affected_users=-1)
    assert "affected_users" in str(exc_info.value)


def test_incident_input_service_and_description_boundaries() -> None:
    """``IncidentInput`` valida longitudes de service (1..100) y description (max 2000)."""
    with pytest.raises(ValidationError) as exc_service_empty:
        IncidentInput(service="", affected_users=1)
    assert "service" in str(exc_service_empty.value)

    with pytest.raises(ValidationError) as exc_service_long:
        IncidentInput(service="S" * 101, affected_users=1)
    assert "service" in str(exc_service_long.value)

    # description admite hasta 2000 caracteres
    valid_desc = IncidentInput(service="Web", affected_users=1, description="D" * 2000)
    assert len(valid_desc.description) == 2000

    with pytest.raises(ValidationError) as exc_desc_long:
        IncidentInput(service="Web", affected_users=1, description="D" * 2001)
    assert "description" in str(exc_desc_long.value)


def test_incident_input_extra_forbidden() -> None:
    """``IncidentInput`` rechaza atributos adicionales desconocidos."""
    with pytest.raises(ValidationError) as exc_info:
        IncidentInput(service="Web", affected_users=1, unauthorized_field="hacker")
    assert "extra_forbidden" in str(exc_info.value)


def test_incident_classification_valid_and_shared_priority_d10() -> None:
    """``IncidentClassification`` usa el enum compartido Priority (D10) y es inmutable."""
    classification = IncidentClassification(
        severity=Priority.CRITICAL,
        sla_hours=2,
        requires_escalation=True,
        rationale="Servicio bancario con caída masiva que compromete SLA regulatorio.",
    )
    assert classification.severity is Priority.CRITICAL
    assert classification.sla_hours == 2
    assert classification.requires_escalation is True
    assert "regulatorio" in classification.rationale

    # Inmutabilidad (frozen)
    with pytest.raises(ValidationError):
        classification.sla_hours = 4  # type: ignore[misc]


def test_incident_classification_sla_hours_gt_zero() -> None:
    """``IncidentClassification.sla_hours`` exige ser estrictamente positivo (> 0)."""
    IncidentClassification(
        severity=Priority.LOW,
        sla_hours=1,
        requires_escalation=False,
        rationale="Incidencia menor",
    )

    with pytest.raises(ValidationError) as exc_zero:
        IncidentClassification(
            severity=Priority.LOW,
            sla_hours=0,
            requires_escalation=False,
            rationale="Cero horas no permitido",
        )
    assert "sla_hours" in str(exc_zero.value)

    with pytest.raises(ValidationError) as exc_negative:
        IncidentClassification(
            severity=Priority.LOW,
            sla_hours=-2,
            requires_escalation=False,
            rationale="Horas negativas",
        )
    assert "sla_hours" in str(exc_negative.value)


def test_incident_classification_rationale_non_empty() -> None:
    """``IncidentClassification.rationale`` debe tener longitud mínima de 1 carácter."""
    with pytest.raises(ValidationError) as exc_info:
        IncidentClassification(
            severity=Priority.MEDIUM,
            sla_hours=8,
            requires_escalation=False,
            rationale="",
        )
    assert "rationale" in str(exc_info.value)


def test_incident_classification_extra_forbidden() -> None:
    """``IncidentClassification`` rechaza atributos no declarados."""
    with pytest.raises(ValidationError) as exc_info:
        IncidentClassification(
            severity=Priority.LOW,
            sla_hours=12,
            requires_escalation=False,
            rationale="OK",
            extra_tag="unexpected",
        )
    assert "extra_forbidden" in str(exc_info.value)


# =============================================================================
# 5. Modelos del Asistente Conversacional (ChatRequest, SourceReference, etc.)
# =============================================================================


def test_chat_request_valid_with_defaults() -> None:
    """``ChatRequest`` se crea exitosamente con query y aplica defaults a campos opcionales."""
    req = ChatRequest(query="¿Cómo escalar un ticket?")
    assert req.query == "¿Cómo escalar un ticket?"
    assert req.session_id is None
    assert req.user_id is None


def test_chat_request_alias_message() -> None:
    """``ChatRequest`` acepta 'message' como alias de 'query' por compatibilidad."""
    req_alias = ChatRequest.model_validate({"message": "Consulta vía alias"})
    assert req_alias.query == "Consulta vía alias"

    # Al volcar el modelo, se serializa como 'query'
    dumped = req_alias.model_dump()
    assert dumped["query"] == "Consulta vía alias"


def test_chat_request_query_strip_and_empty_rejection() -> None:
    """``ChatRequest.query`` recorta espacios y rechaza cadenas vacías o solo con espacios."""
    req_spaces = ChatRequest(query="   ¿Estado del servidor?   ")
    assert req_spaces.query == "¿Estado del servidor?"

    with pytest.raises(ValidationError) as exc_empty:
        ChatRequest(query="")
    assert "query" in str(exc_empty.value)

    with pytest.raises(ValidationError) as exc_whitespace_only:
        ChatRequest(query="   \t  \n  ")
    assert "query" in str(exc_whitespace_only.value)


def test_chat_request_query_length_limits() -> None:
    """``ChatRequest.query`` limita el texto entre 1 y 2000 caracteres."""
    valid_query = ChatRequest(query="A" * 2000)
    assert len(valid_query.query) == 2000

    with pytest.raises(ValidationError) as exc_too_long:
        ChatRequest(query="A" * 2001)
    assert "query" in str(exc_too_long.value)


def test_chat_request_session_id_normalization() -> None:
    """``ChatRequest.session_id`` convierte cadenas vacías o con solo espacios a None."""
    req_empty_str = ChatRequest(query="Consulta", session_id="")
    assert req_empty_str.session_id is None

    req_whitespace = ChatRequest(query="Consulta", session_id="   ")
    assert req_whitespace.session_id is None

    req_trimmed = ChatRequest(query="Consulta", session_id="  sess-alpha-01  ")
    assert req_trimmed.session_id == "sess-alpha-01"

    # Máximo 64 caracteres
    valid_sess = ChatRequest(query="Consulta", session_id="S" * 64)
    assert valid_sess.session_id == "S" * 64

    with pytest.raises(ValidationError) as exc_sess_long:
        ChatRequest(query="Consulta", session_id="S" * 65)
    assert "session_id" in str(exc_sess_long.value)


def test_chat_request_user_id_limits() -> None:
    """``ChatRequest.user_id`` admite hasta 100 caracteres y rechaza valores más largos."""
    valid_user = ChatRequest(query="Consulta", user_id="U" * 100)
    assert valid_user.user_id == "U" * 100

    with pytest.raises(ValidationError) as exc_user_long:
        ChatRequest(query="Consulta", user_id="U" * 101)
    assert "user_id" in str(exc_user_long.value)


def test_chat_request_extra_fields_forbidden() -> None:
    """``ChatRequest`` prohíbe atributos adicionales en la carga."""
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest(query="Consulta", prompt_injection="drop table")
    assert "extra_forbidden" in str(exc_info.value)


def test_source_reference_valid_and_bounds() -> None:
    """``SourceReference`` valida score en el intervalo [0.0, 1.0] y límites de excerpt."""
    ref_min = SourceReference(
        document="guia_vpn.md",
        chunk_id="guia_vpn.md_00",
        score=0.0,
        excerpt="Extracto de prueba",
    )
    assert ref_min.score == 0.0

    ref_max = SourceReference(
        document="guia_vpn.md",
        chunk_id="guia_vpn.md_01",
        score=1.0,
        excerpt="Extracto perfecto",
    )
    assert ref_max.score == 1.0

    # Rechazo por debajo de 0.0
    with pytest.raises(ValidationError) as exc_low:
        SourceReference(
            document="d.md",
            chunk_id="c0",
            score=-0.01,
            excerpt="Negativo",
        )
    assert "score" in str(exc_low.value)

    # Rechazo por encima de 1.0
    with pytest.raises(ValidationError) as exc_high:
        SourceReference(
            document="d.md",
            chunk_id="c0",
            score=1.01,
            excerpt="Mayor a 1",
        )
    assert "score" in str(exc_high.value)

    # Excerpt entre 1 y 500 caracteres
    with pytest.raises(ValidationError) as exc_empty_excerpt:
        SourceReference(
            document="d.md",
            chunk_id="c0",
            score=0.8,
            excerpt="",
        )
    assert "excerpt" in str(exc_empty_excerpt.value)

    with pytest.raises(ValidationError) as exc_long_excerpt:
        SourceReference(
            document="d.md",
            chunk_id="c0",
            score=0.8,
            excerpt="E" * 501,
        )
    assert "excerpt" in str(exc_long_excerpt.value)


def test_source_reference_immutability_and_extra_forbidden() -> None:
    """``SourceReference`` es inmutable y prohíbe atributos adicionales."""
    ref = SourceReference(
        document="doc.md",
        chunk_id="c1",
        score=0.85,
        excerpt="Texto",
    )
    with pytest.raises(ValidationError):
        ref.score = 0.95  # type: ignore[misc]

    with pytest.raises(ValidationError) as exc_extra:
        SourceReference(
            document="doc.md",
            chunk_id="c1",
            score=0.85,
            excerpt="Texto",
            extra_field="invalid",
        )
    assert "extra_forbidden" in str(exc_extra.value)


def test_tool_call_summary_valid_and_bounds() -> None:
    """``ToolCallSummary`` (D12) valida latencia no negativa y nombres no vacíos."""
    tool = ToolCallSummary(
        name="get_ticket_status",
        success=True,
        latency_ms=0.0,
    )
    assert tool.name == "get_ticket_status"
    assert tool.success is True
    assert tool.latency_ms == 0.0

    # Nombre vacío
    with pytest.raises(ValidationError) as exc_name:
        ToolCallSummary(name="", success=False, latency_ms=10.0)
    assert "name" in str(exc_name.value)

    # Latencia negativa
    with pytest.raises(ValidationError) as exc_latency:
        ToolCallSummary(name="tool", success=True, latency_ms=-0.1)
    assert "latency_ms" in str(exc_latency.value)


def test_tool_call_summary_immutability_and_extra_forbidden() -> None:
    """``ToolCallSummary`` es inmutable y rechaza campos extras."""
    tool = ToolCallSummary(name="lookup", success=True, latency_ms=12.5)
    with pytest.raises(ValidationError):
        tool.success = False  # type: ignore[misc]

    with pytest.raises(ValidationError) as exc_extra:
        ToolCallSummary(name="lookup", success=True, latency_ms=12.5, payload={"arg": 1})
    assert "extra_forbidden" in str(exc_extra.value)


def test_chat_response_valid_creation_and_defaults() -> None:
    """``ChatResponse`` asigna listas vacías por default para sources y tool_calls."""
    resp = ChatResponse(
        answer="La respuesta es satisfactoria.",
        grounded=True,
        session_id="sess-xyz-789",
        latency_ms=120.4,
    )
    assert resp.answer == "La respuesta es satisfactoria."
    assert resp.sources == []
    assert resp.tool_calls == []
    assert resp.grounded is True
    assert resp.session_id == "sess-xyz-789"
    assert resp.latency_ms == 120.4


def test_chat_response_with_sources_and_tools() -> None:
    """``ChatResponse`` encapsula correctamente fuentes citadas y herramientas ejecutadas."""
    source = SourceReference(
        document="manual.md",
        chunk_id="chunk_1",
        score=0.92,
        excerpt="Procedimiento de reseteo",
    )
    tool = ToolCallSummary(
        name="calculate_incident_priority",
        success=True,
        latency_ms=5.2,
    )
    resp = ChatResponse(
        answer="Procedimiento verificado con éxito.",
        sources=[source],
        tool_calls=[tool],
        grounded=True,
        session_id="sess-100",
        latency_ms=250.0,
    )
    assert len(resp.sources) == 1
    assert resp.sources[0].score == 0.92
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "calculate_incident_priority"


def test_chat_response_validations_and_immutability() -> None:
    """``ChatResponse`` valida answer no vacía, session_id (1..64), latency_ms >= 0 y es frozen."""
    # Answer vacía
    with pytest.raises(ValidationError) as exc_answer:
        ChatResponse(
            answer="",
            grounded=False,
            session_id="sess-1",
            latency_ms=10.0,
        )
    assert "answer" in str(exc_answer.value)

    # Session_id vacío
    with pytest.raises(ValidationError) as exc_sess_empty:
        ChatResponse(
            answer="Respuesta",
            grounded=False,
            session_id="",
            latency_ms=10.0,
        )
    assert "session_id" in str(exc_sess_empty.value)

    # Latencia negativa
    with pytest.raises(ValidationError) as exc_latency:
        ChatResponse(
            answer="Respuesta",
            grounded=False,
            session_id="sess-1",
            latency_ms=-1.0,
        )
    assert "latency_ms" in str(exc_latency.value)

    # Inmutabilidad (frozen)
    resp = ChatResponse(
        answer="Respuesta",
        grounded=False,
        session_id="sess-1",
        latency_ms=10.0,
    )
    with pytest.raises(ValidationError):
        resp.grounded = True  # type: ignore[misc]

    # Extra prohibido
    with pytest.raises(ValidationError) as exc_extra:
        ChatResponse(
            answer="Respuesta",
            grounded=False,
            session_id="sess-1",
            latency_ms=10.0,
            extra_field="no",
        )
    assert "extra_forbidden" in str(exc_extra.value)


# =============================================================================
# 6. Serialización y deserialización bidireccional (Roundtrip)
# =============================================================================


def test_ticket_serialization_roundtrip() -> None:
    """``Ticket`` serializa a JSON y reconstruye un objeto idéntico con timestamps UTC."""
    ticket = Ticket.model_validate(_build_valid_ticket_kwargs())
    json_data = ticket.model_dump_json()
    reconstructed = Ticket.model_validate_json(json_data)
    assert reconstructed == ticket
    assert reconstructed.created_at.tzinfo == UTC


def test_chat_response_serialization_roundtrip() -> None:
    """``ChatResponse`` serializa a JSON y reconstruye su estructura completa intacta."""
    resp = ChatResponse(
        answer="Información recuperada del manual.",
        sources=[
            SourceReference(
                document="doc1.md",
                chunk_id="c1",
                score=0.88,
                excerpt="Fragmento de manual",
            )
        ],
        tool_calls=[
            ToolCallSummary(
                name="get_ticket_status",
                success=True,
                latency_ms=15.3,
            )
        ],
        grounded=True,
        session_id="sess-abc",
        latency_ms=310.5,
    )
    json_data = resp.model_dump_json()
    reconstructed = ChatResponse.model_validate_json(json_data)
    assert reconstructed == resp
    assert reconstructed.sources[0].chunk_id == "c1"
    assert reconstructed.tool_calls[0].name == "get_ticket_status"
