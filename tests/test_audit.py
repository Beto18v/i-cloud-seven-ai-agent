"""Pruebas unitarias para el servicio de auditoría estructurada (AuditService).

Verifica la persistencia y lectura en formato JSON Lines (JSONL), el respeto al límite
de registros solicitados, el ordenamiento, el manejo de rutas no existentes y la
resiliencia ante líneas corruptas (Decisión D12).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.audit import AuditService


def test_audit_service_empty_when_file_not_exists(tmp_path: Path) -> None:
    """Verifica que get_logs retorne lista vacía si el archivo no ha sido creado."""
    log_file = tmp_path / "audit_inexistente.jsonl"
    service = AuditService(file_path=log_file)

    logs = service.get_logs(limit=10)
    assert logs == []


def test_audit_service_log_and_read_single_entry(tmp_path: Path) -> None:
    """Verifica la escritura correcta de una llamada a herramienta y su posterior lectura."""
    log_file = tmp_path / "audit.jsonl"
    service = AuditService(file_path=log_file)

    service.log_tool_call(
        session_id="sess-100",
        tool_name="get_ticket_status",
        arguments={"ticket_id": "TCK-104"},
        result={"ticket_id": "TCK-104", "status": "resolved"},
        success=True,
        latency_ms=15.42,
    )

    assert log_file.exists()
    logs = service.get_logs(limit=10)
    assert len(logs) == 1

    entry: dict[str, Any] = logs[0]
    assert entry["session_id"] == "sess-100"
    assert entry["tool_name"] == "get_ticket_status"
    assert entry["arguments"] == {"ticket_id": "TCK-104"}
    assert entry["result"] == {"ticket_id": "TCK-104", "status": "resolved"}
    assert entry["success"] is True
    assert entry["latency_ms"] == 15.42
    assert "timestamp" in entry


def test_audit_service_limit_and_reverse_order(tmp_path: Path) -> None:
    """Verifica que get_logs respete el límite N y admita orden cronológico inverso."""
    log_file = tmp_path / "audit_multi.jsonl"
    service = AuditService(file_path=log_file)

    for i in range(1, 6):
        service.log_tool_call(
            session_id=f"sess-{i}",
            tool_name=f"tool_{i}",
            arguments={"step": i},
            result={"status": "ok"},
            success=True,
            latency_ms=float(i * 10),
        )

    # Últimas 3 llamadas en orden de inserción
    logs_last_3 = service.get_logs(limit=3, reverse=False)
    assert len(logs_last_3) == 3
    assert [log["tool_name"] for log in logs_last_3] == ["tool_3", "tool_4", "tool_5"]

    # Últimas 3 llamadas con la más reciente al frente
    logs_reversed = service.get_logs(limit=3, reverse=True)
    assert len(logs_reversed) == 3
    assert [log["tool_name"] for log in logs_reversed] == ["tool_5", "tool_4", "tool_3"]


def test_audit_service_invalid_limits(tmp_path: Path) -> None:
    """Verifica que límites menores o iguales a cero retornen lista vacía."""
    log_file = tmp_path / "audit_limits.jsonl"
    service = AuditService(file_path=log_file)
    service.log_tool_call("sess-1", "tool_1", {}, {}, True, 10.0)

    assert service.get_logs(limit=0) == []
    assert service.get_logs(limit=-5) == []


def test_audit_service_skips_corrupted_lines(tmp_path: Path) -> None:
    """Verifica que líneas con formato JSON roto sean omitidas sin fallar."""
    log_file = tmp_path / "corrupted_audit.jsonl"
    valid_entry = json.dumps({"session_id": "valid-1", "tool_name": "t1"})

    log_file.write_text(f"{valid_entry}\nLINEA_CORRUPTA\n{valid_entry}\n", encoding="utf-8")

    service = AuditService(file_path=log_file)
    logs = service.get_logs(limit=10)

    assert len(logs) == 2
    assert logs[0]["session_id"] == "valid-1"
    assert logs[1]["session_id"] == "valid-1"
