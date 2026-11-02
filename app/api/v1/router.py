"""Router centralizador de la versión 1 (v1) de la API.

Agrupa e incluye los routers de chat, documentos, tickets y auditoría
con sus respectivos prefijos y etiquetas OpenAPI.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import audit, chat, documents, tickets

api_v1_router = APIRouter()

api_v1_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_v1_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_v1_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_v1_router.include_router(audit.router, prefix="/audit", tags=["audit"])

__all__ = ["api_v1_router"]
