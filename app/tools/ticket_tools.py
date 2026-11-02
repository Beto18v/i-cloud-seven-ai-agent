"""Herramienta operativa para consultar el estado de tickets en el sistema legado.

Permite al agente conversacional inspeccionar solicitudes internas e incidentes
registrados en el almacén de datos legado, verificando identificadores y extrayendo
campos clave como estado, prioridad, responsable y última actualización.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from app.core.config import PROJECT_ROOT, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _resolve_tickets_file(custom_path: Path | None = None) -> Path:
    """Resuelve la ruta efectiva del archivo de tickets sintéticos.

    Args:
        custom_path: ruta personalizada opcional para pruebas unitarias.

    Returns:
        Ruta resuelta hacia el archivo JSON de tickets legados.
    """
    if custom_path is not None:
        return custom_path

    try:
        settings = get_settings()
        candidate = getattr(settings, "mock_tickets_path", None)
        if candidate is not None and candidate.exists():
            return candidate
    except Exception:
        logger.debug("ticket_tools_settings_lookup_failed")

    fallback = PROJECT_ROOT / "data" / "mock_tickets.json"
    return fallback


def query_ticket_status(ticket_id: str, tickets_path: Path | None = None) -> dict[str, Any]:
    """Busca y extrae la información de un ticket ignorando mayúsculas y espacios.

    Args:
        ticket_id: identificador único del ticket (por ejemplo 'TCK-104').
        tickets_path: ruta opcional hacia el archivo JSON con los datos.

    Returns:
        Diccionario con los campos normalizados del ticket o un mensaje de error si no existe.
    """
    normalized_id = ticket_id.strip().upper()
    target_file = _resolve_tickets_file(tickets_path)

    if not target_file.exists():
        logger.error("mock_tickets_file_not_found", path=str(target_file))
        return {
            "error": f"No se encontró el archivo de datos del sistema legado en '{target_file}'."
        }

    try:
        content = target_file.read_text(encoding="utf-8")
        records: list[dict[str, Any]] = json.loads(content)
    except Exception as exc:
        logger.error("mock_tickets_read_error", path=str(target_file), error=str(exc))
        return {"error": f"Error al leer el sistema legado de tickets: {exc}"}

    for record in records:
        candidate_id = str(record.get("ticket_id", "")).strip().upper()
        if candidate_id == normalized_id:
            assigned = record.get("assigned_to")
            return {
                "ticket_id": str(record.get("ticket_id", "")),
                "title": str(record.get("title", "")),
                "status": str(record.get("status", "")),
                "priority": str(record.get("priority", "")),
                "assigned_to": str(assigned) if assigned is not None else None,
                "reported_by": str(record.get("reported_by", "")),
                "updated_at": str(record.get("updated_at", "")),
            }

    return {"error": f"No se encontró el ticket '{ticket_id}' en el sistema legado de soporte."}


@tool("get_ticket_status")
def get_ticket_status(ticket_id: str) -> dict[str, Any]:
    """Consulta el estado, prioridad, asignación y detalles de un ticket en el sistema legado.

    Invoca esta herramienta cuando el usuario pregunte por el estado, responsable,
    prioridad o información operativa de una solicitud interna o ticket específico
    a partir de su identificador (ejemplo: 'TCK-101', 'TCK-104').

    Args:
        ticket_id: identificador unívoco del ticket en formato 'TCK-NNN'.

    Returns:
        Diccionario con ticket_id, title, status, priority, assigned_to,
        reported_by y updated_at, o un diccionario con 'error' si no existe.
    """
    return query_ticket_status(ticket_id)


__all__ = [
    "get_ticket_status",
    "query_ticket_status",
]
