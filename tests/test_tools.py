"""Pruebas unitarias para las herramientas operativas del asistente conversacional.

Verifica el comportamiento determinista de get_ticket_status sobre datos legados,
la matriz cuantitativa de severidad y SLA en calculate_incident_priority (D10),
y la factoría de herramientas RAG create_rag_tool con rastreo de fuentes citadas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.models.chat import SourceReference
from app.models.ticket import Priority
from app.services.rag import RAGService
from app.tools.incident_tools import (
    calculate_incident_priority,
    evaluate_incident_severity,
)
from app.tools.rag_tools import create_rag_tool
from app.tools.ticket_tools import (
    get_ticket_status,
    query_ticket_status,
)

# =============================================================================
# 1. Pruebas de get_ticket_status (TC-02)
# =============================================================================


def test_get_ticket_status_success_tck_104() -> None:
    """Verifica que TCK-104 (TC-02) retorne los valores exactos provistos en el mock JSON."""
    result: dict[str, Any] = get_ticket_status.invoke({"ticket_id": "TCK-104"})

    assert "error" not in result
    assert result["ticket_id"] == "TCK-104"
    assert result["title"] == "Fallo de sincronización en módulo de facturación legado"
    assert result["status"] == "resolved"
    assert result["priority"] == "high"
    assert result["assigned_to"] == "Carlos Mendoza"
    assert result["reported_by"] == "maria.gonzalez@empresa.com"
    assert result["updated_at"] == "2026-10-29T09:15:00Z"


def test_get_ticket_status_case_and_whitespace_insensitive() -> None:
    """Verifica que la búsqueda ignore mayúsculas, minúsculas y espacios en blanco."""
    result: dict[str, Any] = get_ticket_status.invoke({"ticket_id": "   tck-104   "})

    assert "error" not in result
    assert result["ticket_id"] == "TCK-104"
    assert result["assigned_to"] == "Carlos Mendoza"


def test_get_ticket_status_unassigned_ticket_103() -> None:
    """Verifica que un ticket sin responsable asignado retorne assigned_to como None."""
    result: dict[str, Any] = get_ticket_status.invoke({"ticket_id": "TCK-103"})

    assert "error" not in result
    assert result["ticket_id"] == "TCK-103"
    assert result["assigned_to"] is None
    assert result["priority"] == "low"
    assert result["status"] == "open"


def test_get_ticket_status_not_found() -> None:
    """Verifica que un identificador inexistente devuelva un diccionario con la clave 'error'."""
    result: dict[str, Any] = get_ticket_status.invoke({"ticket_id": "TCK-999"})

    assert "error" in result
    assert "No se encontró el ticket 'TCK-999'" in result["error"]


def test_query_ticket_status_missing_file(tmp_path: Path) -> None:
    """Verifica que si el archivo de tickets no existe se retorne error controlado."""
    non_existent = tmp_path / "tickets_inexistente.json"
    result = query_ticket_status("TCK-104", tickets_path=non_existent)

    assert "error" in result
    assert "No se encontró el archivo de datos" in result["error"]


def test_query_ticket_status_corrupted_json(tmp_path: Path) -> None:
    """Verifica el manejo de archivos JSON con sintaxis rota o corrupta."""
    corrupted = tmp_path / "corrupted.json"
    corrupted.write_text("{archivo_roto:", encoding="utf-8")

    result = query_ticket_status("TCK-104", tickets_path=corrupted)
    assert "error" in result
    assert "Error al leer el sistema legado" in result["error"]


# =============================================================================
# 2. Pruebas de calculate_incident_priority (TC-03 y D10)
# =============================================================================


@pytest.mark.parametrize(
    ("affected_users", "is_critical", "expected_severity", "expected_sla", "expected_esc"),
    [
        (500, False, Priority.CRITICAL.value, 1, True),
        (1000, False, Priority.CRITICAL.value, 1, True),
        (5, True, Priority.CRITICAL.value, 1, True),
        (0, True, Priority.CRITICAL.value, 1, True),
        (150, False, Priority.HIGH.value, 4, True),
        (100, False, Priority.HIGH.value, 4, True),
        (499, False, Priority.HIGH.value, 4, True),
        (50, False, Priority.MEDIUM.value, 8, False),
        (10, False, Priority.MEDIUM.value, 8, False),
        (99, False, Priority.MEDIUM.value, 8, False),
        (9, False, Priority.LOW.value, 24, False),
        (1, False, Priority.LOW.value, 24, False),
        (0, False, Priority.LOW.value, 24, False),
    ],
)
def test_evaluate_incident_severity_rules(
    affected_users: int,
    is_critical: bool,
    expected_severity: str,
    expected_sla: int,
    expected_esc: bool,
) -> None:
    """Verifica la coherencia determinista de todas las bandas de cálculo de severidad y SLA."""
    evaluation = evaluate_incident_severity(
        affected_users=affected_users,
        is_critical_service=is_critical,
        service_name="Portal Pagos",
    )

    assert evaluation["severity"] == expected_severity
    assert evaluation["sla_hours"] == expected_sla
    assert evaluation["requires_escalation"] is expected_esc
    assert evaluation["affected_users"] == max(0, affected_users)
    assert evaluation["is_critical_service"] is is_critical
    assert "rationale" in evaluation and len(evaluation["rationale"]) > 0


def test_calculate_incident_priority_tool_invocation() -> None:
    """Verifica la invocación de calculate_incident_priority como herramienta de LangChain."""
    result: dict[str, Any] = calculate_incident_priority.invoke(
        {
            "affected_users": 500,
            "is_critical_service": False,
            "service_name": "LDAP Central",
        }
    )

    assert result["severity"] == "critical"
    assert result["sla_hours"] == 1
    assert result["requires_escalation"] is True
    assert ">= 500 usuarios" in result["rationale"]
    assert result["service_name"] == "LDAP Central"


# =============================================================================
# 3. Pruebas de create_rag_tool
# =============================================================================


def test_create_rag_tool_success_and_tracking() -> None:
    """Verifica que la herramienta RAG invoque el servicio y acumule las fuentes en el tracker."""
    mock_rag_service = MagicMock(spec=RAGService)
    fake_reference = SourceReference(
        document="manual_operaciones.md",
        chunk_id="manual_operaciones:1",
        score=0.88,
        excerpt="Procedimiento de reinicio del worker de sincronización.",
    )
    mock_rag_service.retrieve.return_value = [fake_reference]

    captured_sources: list[SourceReference] = []
    rag_tool = create_rag_tool(mock_rag_service, sources_tracker=captured_sources)

    output = rag_tool.invoke({"query": "reinicio servicio"})

    assert "manual_operaciones.md" in output
    assert "0.88" in output
    assert "Procedimiento de reinicio" in output
    assert len(captured_sources) == 1
    assert captured_sources[0] == fake_reference
    mock_rag_service.retrieve.assert_called_once_with("reinicio servicio")


def test_create_rag_tool_no_results() -> None:
    """Verifica el mensaje textual retornado cuando el servicio RAG no encuentra coincidencias."""
    mock_rag_service = MagicMock(spec=RAGService)
    mock_rag_service.retrieve.return_value = []

    captured_sources: list[SourceReference] = []
    rag_tool = create_rag_tool(mock_rag_service, sources_tracker=captured_sources)

    output = rag_tool.invoke({"query": "tema desconocido"})

    assert "No se encontraron fragmentos de documentación técnica relevantes" in output
    assert len(captured_sources) == 0
