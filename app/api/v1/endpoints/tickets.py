"""Endpoint para la consulta de tickets en el sistema legado."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.core.logging import get_logger
from app.models.ticket import Ticket

logger = get_logger(__name__)

router = APIRouter()


def _resolve_mock_tickets_file(settings: Settings) -> Path:
    """Resuelve la ruta efectiva del archivo de tickets sintéticos legados.

    Args:
        settings: configuración activa del sistema.

    Returns:
        Ruta resuelta hacia el archivo JSON de tickets legados.
    """
    candidate: Path | None = getattr(settings, "mock_tickets_file", None) or getattr(
        settings, "mock_tickets_path", None
    )
    if candidate is not None and candidate.exists():
        return candidate

    fallback = PROJECT_ROOT / "data" / "mock_tickets.json"
    if fallback.exists():
        return fallback

    return candidate if candidate is not None else fallback


@router.get(
    "/{ticket_id}",
    response_model=Ticket,
    status_code=status.HTTP_200_OK,
    summary="Consultar detalle de un ticket legado",
    description=(
        "Recupera la información estructurada de un ticket desde el almacén de datos "
        "legado a partir de su identificador unívoco (ej. TCK-104)."
    ),
)
async def get_ticket(
    ticket_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Ticket:
    """Busca un ticket en el sistema legado y lo retorna validado como Ticket.

    Args:
        ticket_id: identificador único del ticket solicitado.
        settings: configuración activa inyectada por FastAPI.

    Returns:
        Instancia de Ticket con todos sus atributos validados.

    Raises:
        HTTPException: 404 si el ticket no existe en el sistema legado.
    """
    tickets_file = _resolve_mock_tickets_file(settings)

    if not tickets_file.exists():
        logger.warning("mock_tickets_file_not_found", path=str(tickets_file))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' no encontrado en el sistema legado.",
        )

    try:
        content = tickets_file.read_text(encoding="utf-8")
        records: list[dict[str, Any]] = json.loads(content)
    except Exception as exc:
        logger.error(
            "mock_tickets_read_failed",
            path=str(tickets_file),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' no encontrado en el sistema legado.",
        ) from exc

    normalized_id = ticket_id.strip().upper()
    for record in records:
        candidate_id = str(record.get("ticket_id", "")).strip().upper()
        if candidate_id == normalized_id:
            return Ticket.model_validate(record)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Ticket '{ticket_id}' no encontrado en el sistema legado.",
    )


__all__ = ["router"]
