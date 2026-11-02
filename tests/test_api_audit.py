"""Pruebas de integración para el endpoint de auditoría (/api/v1/audit/logs).

Valida la consulta de bitácoras JSONL de llamadas a herramientas (D12),
la parametrización del límite (limit) y la validación de rangos numéricos.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_audit_service
from app.core.config import Settings
from app.services.audit import AuditService


def test_get_audit_logs_empty_by_default(client: TestClient) -> None:
    """Verifica que sin registros previos GET /api/v1/audit/logs responda 200 con lista vacía."""
    response = client.get("/api/v1/audit/logs")
    assert response.status_code == 200
    assert response.json() == []


def test_get_audit_logs_returns_persisted_entries(
    client: TestClient,
    settings: Settings,
) -> None:
    """Verifica que los registros generados se lean y serialicen correctamente en la API."""
    audit_service = AuditService(settings=settings)
    audit_service.log_tool_call(
        session_id="audit-sess-1",
        tool_name="get_ticket_status",
        arguments={"ticket_id": "TCK-104"},
        result={"ticket_id": "TCK-104", "status": "resolved"},
        success=True,
        latency_ms=18.4,
    )
    audit_service.log_tool_call(
        session_id="audit-sess-2",
        tool_name="calculate_incident_priority",
        arguments={"affected_users": 150},
        result={"severity": "critical", "sla_hours": 2},
        success=True,
        latency_ms=2.1,
    )

    response = client.get("/api/v1/audit/logs")
    assert response.status_code == 200

    data: list[dict[str, Any]] = response.json()
    assert len(data) == 2
    assert data[0]["tool_name"] == "get_ticket_status"
    assert data[0]["session_id"] == "audit-sess-1"
    assert data[1]["tool_name"] == "calculate_incident_priority"
    assert data[1]["success"] is True


def test_get_audit_logs_respects_limit_parameter(
    client: TestClient,
    settings: Settings,
) -> None:
    """Verifica que el parámetro query limit limite la cantidad de registros retornados."""
    audit_service = AuditService(settings=settings)
    for i in range(5):
        audit_service.log_tool_call(
            session_id=f"sess-{i}",
            tool_name="test_tool",
            arguments={"idx": i},
            result={"ok": True},
            success=True,
            latency_ms=1.0,
        )

    response = client.get("/api/v1/audit/logs?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.parametrize(
    "invalid_limit",
    [
        "?limit=0",
        "?limit=-5",
        "?limit=501",
        "?limit=1000",
        "?limit=not_an_int",
    ],
)
def test_get_audit_logs_invalid_limit_returns_422(
    client: TestClient,
    invalid_limit: str,
) -> None:
    """Verifica que límites fuera del rango [1, 500] o no numéricos devuelvan 422."""
    response = client.get(f"/api/v1/audit/logs{invalid_limit}")
    assert response.status_code == 422
    assert "detail" in response.json()


def test_get_audit_logs_with_dependency_override(client: TestClient) -> None:
    """Verifica la compatibilidad con FastAPI dependency_overrides sobre get_audit_service."""
    mock_audit = MagicMock(spec=AuditService)
    mock_audit.get_logs.return_value = [
        {
            "timestamp": "2026-11-02T12:00:00Z",
            "session_id": "mock-sess",
            "tool_name": "mock_tool",
            "arguments": {},
            "result": "ok",
            "success": True,
            "latency_ms": 1.5,
        }
    ]

    client.app.dependency_overrides[get_audit_service] = lambda: mock_audit
    try:
        response = client.get("/api/v1/audit/logs?limit=10")
        assert response.status_code == 200
        mock_audit.get_logs.assert_called_once_with(limit=10)
        assert len(response.json()) == 1
    finally:
        client.app.dependency_overrides.pop(get_audit_service, None)
