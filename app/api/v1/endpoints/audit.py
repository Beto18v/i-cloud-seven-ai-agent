"""Endpoint para la consulta de bitácoras de auditoría de herramientas."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_audit_service
from app.services.audit import AuditService

router = APIRouter()


@router.get(
    "/logs",
    response_model=list[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Consultar bitácora de auditoría de herramientas",
    description=(
        "Obtiene las últimas invocaciones a herramientas operativas registradas "
        "en formato JSON Lines para propósitos de observabilidad y trazabilidad (D12)."
    ),
)
async def get_audit_logs(
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=500,
            description="Cantidad máxima de registros de auditoría a retornar (1 a 500).",
        ),
    ] = 50,
) -> list[dict[str, Any]]:
    """Recupera los registros de auditoría almacenados en el archivo JSONL.

    Args:
        audit_service: servicio de auditoría inyectado por FastAPI.
        limit: límite de registros a retornar (1 a 500, por defecto 50).

    Returns:
        Lista de registros de auditoría recuperados.
    """
    return audit_service.get_logs(limit=limit)


__all__ = ["router"]
