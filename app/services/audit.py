"""Servicio de auditoría estructurada para la trazabilidad de llamadas a herramientas (D12).

Persiste en formato JSON Lines (JSONL) el detalle exhaustivo de cada invocación
operativa (argumentos, resultado, éxito, latencia y sesión) garantizando observabilidad
y cumplimiento sin exponer datos sensibles en el contrato público de respuesta.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """Gestiona el registro persistente y la consulta de bitácoras de auditoría JSONL.

    Attributes:
        audit_file: ruta resuelta al archivo JSON Lines de auditoría.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        file_path: Path | None = None,
    ) -> None:
        """Inicializa el servicio de auditoría con la ruta de persistencia correspondiente.

        Args:
            settings: configuración activa opcional del sistema.
            file_path: ruta explícita opcional al archivo de auditoría (prioritaria si se define).
        """
        if file_path is not None:
            self.audit_file: Path = file_path
        else:
            resolved_settings = settings or get_settings()
            self.audit_file = getattr(
                resolved_settings,
                "audit_file",
                getattr(resolved_settings, "audit_log_file", Path("data/audit/audit.jsonl")),
            )

    def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Registra una línea de auditoría correspondiente a la ejecución de una herramienta.

        Args:
            session_id: identificador de la sesión conversacional.
            tool_name: nombre de la herramienta ejecutada.
            arguments: parámetros de entrada provistos a la herramienta.
            result: respuesta o payload retornado por la herramienta.
            success: True si la ejecución concluyó sin excepciones no controladas.
            latency_ms: tiempo de ejecución transcurrido en milisegundos.
        """
        record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "success": success,
            "latency_ms": round(float(latency_ms), 2),
        }

        try:
            self.audit_file.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, default=str, ensure_ascii=False) + "\n"
            with self.audit_file.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception as exc:
            logger.error(
                "audit_log_write_failed",
                tool_name=tool_name,
                session_id=session_id,
                error=str(exc),
            )

    def get_logs(self, limit: int = 50, reverse: bool = False) -> list[dict[str, Any]]:
        """Recupera los últimos registros de auditoría almacenados en el archivo JSONL.

        Args:
            limit: cantidad máxima de registros a retornar (por defecto 50).
            reverse: si es True, retorna los registros en orden cronológico inverso
                (el más reciente primero); si es False, conserva el orden del archivo.

        Returns:
            Lista de diccionarios parseados correspondientes a las líneas solicitadas.
        """
        if limit <= 0 or not self.audit_file.exists():
            return []

        try:
            with self.audit_file.open("r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as exc:
            logger.error("audit_log_read_failed", path=str(self.audit_file), error=str(exc))
            return []

        selected = lines[-limit:]
        parsed_records: list[dict[str, Any]] = []

        for line in selected:
            try:
                parsed_records.append(json.loads(line))
            except json.JSONDecodeError as decode_err:
                logger.warning("audit_log_corrupted_line_skipped", error=str(decode_err))

        if reverse:
            return list(reversed(parsed_records))
        return parsed_records


__all__ = [
    "AuditService",
]
