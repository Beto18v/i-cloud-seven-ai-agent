"""Endpoint para la ingesta e indexación de manuales técnicos en la base vectorial."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_rag_service
from app.services.rag import IngestSummary, RAGService

router = APIRouter()


@router.post(
    "/ingest",
    response_model=IngestSummary,
    status_code=status.HTTP_200_OK,
    summary="Ingestar e indexar manuales técnicos en la base vectorial",
    description=(
        "Procesa y segmenta los documentos Markdown presentes en el directorio "
        "de conocimiento e indexa los fragmentos generados en ChromaDB."
    ),
)
async def ingest_documents(
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    force_reindex: Annotated[
        bool,
        Query(
            description="Si es True, purga la colección previa antes de indexar de nuevo.",
        ),
    ] = False,
) -> IngestSummary:
    """Ejecuta la ingesta asíncrona de manuales técnicos en el almacén vectorial.

    Args:
        rag_service: servicio de recuperación RAG inyectado por FastAPI.
        force_reindex: booleano que indica si se debe purgar la colección antes de indexar.

    Returns:
        IngestSummary con la cantidad de archivos y fragmentos procesados.
    """
    return await rag_service.aingest_documents(force_reindex=force_reindex)


__all__ = ["router"]
