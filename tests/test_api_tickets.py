"""Pruebas de integración para el endpoint de tickets legados (/api/v1/tickets/{ticket_id}).

Valida la recuperación de tickets existentes (TC-02), la respuesta HTTP 404
ante identificadores inexistentes y la validación estricta con el esquema Ticket.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.models.ticket import Priority, Ticket, TicketStatus


def test_get_ticket_tck_104_success(client: TestClient) -> None:
    """Verifica que GET /api/v1/tickets/TCK-104 retorne 200 OK y el ticket exacto."""
    response = client.get("/api/v1/tickets/TCK-104")
    assert response.status_code == 200

    data: dict[str, Any] = response.json()
    validated = Ticket.model_validate(data)

    assert validated.ticket_id == "TCK-104"
    assert validated.title == "Fallo de sincronización en módulo de facturación legado"
    assert validated.status is TicketStatus.RESOLVED
    assert validated.priority is Priority.HIGH
    assert validated.assigned_to == "Carlos Mendoza"
    assert validated.reported_by == "maria.gonzalez@empresa.com"
    assert validated.created_at.year == 2026


def test_get_ticket_case_insensitive(client: TestClient) -> None:
    """Verifica que el identificador del ticket no distinga entre mayúsculas y minúsculas."""
    response = client.get("/api/v1/tickets/tck-104")
    assert response.status_code == 200

    data = response.json()
    assert data["ticket_id"] == "TCK-104"
    assert data["assigned_to"] == "Carlos Mendoza"


def test_get_ticket_not_found_returns_404(client: TestClient) -> None:
    """Verifica que GET /api/v1/tickets/TCK-999 retorne 404 Not Found con mensaje descriptivo."""
    response = client.get("/api/v1/tickets/TCK-999")
    assert response.status_code == 404

    data = response.json()
    assert data["detail"] == "Ticket 'TCK-999' no encontrado en el sistema legado."


def test_get_ticket_tck_101_critical(client: TestClient) -> None:
    """Verifica que un ticket de prioridad crítica (TCK-101) conserve su contrato."""
    response = client.get("/api/v1/tickets/TCK-101")
    assert response.status_code == 200

    data = response.json()
    assert data["ticket_id"] == "TCK-101"
    assert data["priority"] == "critical"
    assert data["status"] == "open"


def test_get_ticket_tck_103_unassigned(client: TestClient) -> None:
    """Verifica que un ticket sin responsable asignado conserve assigned_to como null."""
    response = client.get("/api/v1/tickets/TCK-103")
    assert response.status_code == 200

    data = response.json()
    assert data["ticket_id"] == "TCK-103"
    assert data["assigned_to"] is None
