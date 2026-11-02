"""Pruebas unitarias para los datos sintéticos y manuales operativos del sistema legado.

Verifica la conformidad estructural del archivo de tickets contra el modelo Pydantic
`app.models.ticket.Ticket`, la exactitud del ticket TCK-104 requerido para el caso
TC-02, la unicidad de identificadores, la cobertura de estados y prioridades,
así como la existencia e integridad del contenido técnico en la documentación RAG.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models.ticket import Priority, Ticket, TicketStatus

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MOCK_TICKETS_PATH = DATA_DIR / "mock_tickets.json"
DOCUMENTS_DIR = DATA_DIR / "documents"


@pytest.fixture(scope="module")
def raw_tickets_data() -> list[dict[str, object]]:
    """Carga y retorna la lista de diccionarios crudos desde mock_tickets.json.

    Returns:
        Lista de diccionarios que representan los registros crudos de tickets.

    Raises:
        FileNotFoundError: si el archivo de tickets sintéticos no existe.
        AssertionError: si el contenido decodificado no es una lista.
    """
    assert MOCK_TICKETS_PATH.exists(), f"El archivo {MOCK_TICKETS_PATH} debe existir."
    content = MOCK_TICKETS_PATH.read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, list), "El archivo JSON debe contener una lista en la raíz."
    return data


@pytest.fixture(scope="module")
def parsed_tickets(raw_tickets_data: list[dict[str, object]]) -> list[Ticket]:
    """Parsea y valida cada registro de ticket contra el modelo Ticket de Pydantic.

    Args:
        raw_tickets_data: lista de diccionarios crudos de tickets.

    Returns:
        Lista de instancias de Ticket validadas.
    """
    return [Ticket.model_validate(raw_item) for raw_item in raw_tickets_data]


# =============================================================================
# 1. Pruebas de validación del archivo data/mock_tickets.json
# =============================================================================


def test_mock_tickets_file_exists() -> None:
    """Verifica que el archivo data/mock_tickets.json exista y contenga información."""
    assert MOCK_TICKETS_PATH.exists()
    assert MOCK_TICKETS_PATH.is_file()
    assert MOCK_TICKETS_PATH.stat().st_size > 0


def test_mock_tickets_parses_successfully(parsed_tickets: list[Ticket]) -> None:
    """Verifica que todos los registros en mock_tickets.json cumplan el contrato Ticket.

    Args:
        parsed_tickets: lista de tickets instanciados con Pydantic.
    """
    assert len(parsed_tickets) >= 7, "Se requieren al menos 7 tickets sintéticos."
    for ticket in parsed_tickets:
        assert isinstance(ticket, Ticket)
        assert ticket.ticket_id.startswith("TCK-")
        assert ticket.created_at.tzinfo == UTC
        assert ticket.updated_at.tzinfo == UTC


def test_mock_tickets_unique_identifiers(parsed_tickets: list[Ticket]) -> None:
    """Verifica que no existan identificadores de ticket duplicados en el conjunto.

    Args:
        parsed_tickets: lista de tickets instanciados.
    """
    ticket_ids = [t.ticket_id for t in parsed_tickets]
    unique_ids = set(ticket_ids)
    assert len(ticket_ids) == len(unique_ids), f"Existen IDs duplicados: {ticket_ids}"


def test_mock_tickets_expected_identifier_presence(parsed_tickets: list[Ticket]) -> None:
    """Verifica la presencia explícita de todos los identificadores solicitados.

    Args:
        parsed_tickets: lista de tickets instanciados.
    """
    expected_ids = {"TCK-101", "TCK-102", "TCK-103", "TCK-104", "TCK-105", "TCK-106", "TCK-1001"}
    actual_ids = {t.ticket_id for t in parsed_tickets}
    assert expected_ids.issubset(actual_ids), f"Faltan IDs: {expected_ids - actual_ids}"


def test_mock_tickets_exact_tck104_contract(parsed_tickets: list[Ticket]) -> None:
    """Valida minuciosamente el ticket TCK-104 requerido para el caso de prueba TC-02.

    Args:
        parsed_tickets: lista de tickets instanciados.
    """
    tck104 = next((t for t in parsed_tickets if t.ticket_id == "TCK-104"), None)
    assert tck104 is not None, "El ticket TCK-104 debe existir obligatoriamente."

    assert tck104.ticket_id == "TCK-104"
    assert tck104.title == "Fallo de sincronización en módulo de facturación legado"
    assert tck104.description == (
        "El lote nocturno de facturación del sistema legado falló con código de error "
        "SYNC-902 tras el corte del fin de mes."
    )
    assert tck104.status == TicketStatus.RESOLVED
    assert tck104.priority == Priority.HIGH
    assert tck104.reported_by == "maria.gonzalez@empresa.com"
    assert tck104.assigned_to == "Carlos Mendoza"
    assert tck104.created_at == datetime(2026, 10, 28, 14, 30, 0, tzinfo=UTC)
    assert tck104.updated_at == datetime(2026, 10, 29, 9, 15, 0, tzinfo=UTC)


def test_mock_tickets_covers_all_statuses_and_priorities(
    parsed_tickets: list[Ticket],
) -> None:
    """Verifica la cobertura integral de todos los estados y niveles de prioridad.

    Args:
        parsed_tickets: lista de tickets instanciados.
    """
    statuses = {t.status for t in parsed_tickets}
    priorities = {t.priority for t in parsed_tickets}

    assert statuses == {
        TicketStatus.OPEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    }
    assert priorities == {
        Priority.LOW,
        Priority.MEDIUM,
        Priority.HIGH,
        Priority.CRITICAL,
    }


# =============================================================================
# 2. Pruebas de validación de manuales operativos (RAG)
# =============================================================================


def test_documents_directory_contains_expected_files() -> None:
    """Verifica que el directorio data/documents contenga los archivos Markdown exigidos."""
    assert DOCUMENTS_DIR.exists()
    assert DOCUMENTS_DIR.is_dir()

    expected_files = [
        "manual_operaciones_v2.md",
        "resolucion_bloqueos_bd.md",
        "politicas_sla_escalamiento.md",
    ]

    for file_name in expected_files:
        file_path = DOCUMENTS_DIR / file_name
        assert file_path.exists(), f"El archivo {file_name} no existe en {DOCUMENTS_DIR}."
        assert file_path.is_file()
        assert file_path.stat().st_size > 0, f"El archivo {file_name} está vacío."


def test_manual_operaciones_v2_content_tc01() -> None:
    """Valida los pasos explícitos del procedimiento de sincronización para TC-01."""
    manual_path = DOCUMENTS_DIR / "manual_operaciones_v2.md"
    content = manual_path.read_text(encoding="utf-8")

    assert "Procedimiento operativo para reiniciar el servicio de sincronización legado" in content
    assert "/opt/legacy/bin/sync_ctl.sh stop" in content
    assert "systemctl stop legacy-sync.service" in content
    assert "ps aux | grep legacy-sync" in content
    assert "/var/run/legacy/sync.lock" in content
    assert "/opt/legacy/bin/sync_ctl.sh start" in content
    assert "/var/log/legacy/sync.log" in content
    assert "Sincronización reanudada exitosamente" in content
    assert "SYNC-902" in content


def test_resolucion_bloqueos_bd_content() -> None:
    """Valida que la guía de base de datos incluya las queries y comandos clave."""
    doc_path = DOCUMENTS_DIR / "resolucion_bloqueos_bd.md"
    content = doc_path.read_text(encoding="utf-8")

    assert "pg_stat_activity" in content
    assert "pg_locks" in content
    assert "pg_cancel_backend" in content
    assert "pg_terminate_backend" in content
    assert "PgBouncer" in content
    assert "systemctl restart pgbouncer" in content
    assert "SHOW POOLS" in content


def test_politicas_sla_escalamiento_content() -> None:
    """Valida la documentación de clasificación de severidad y tiempos de SLA."""
    doc_path = DOCUMENTS_DIR / "politicas_sla_escalamiento.md"
    content = doc_path.read_text(encoding="utf-8")

    assert "CRITICAL" in content
    assert ">=500" in content
    assert "< 2 horas" in content or "< 2h" in content
    assert "HIGH" in content
    assert "4 horas" in content
    assert "MEDIUM" in content
    assert "8 horas" in content
    assert "LOW" in content
    assert "24 horas" in content
    assert "Directorio de Contactos de Guardia" in content
    assert "Líder de Incidentes" in content
