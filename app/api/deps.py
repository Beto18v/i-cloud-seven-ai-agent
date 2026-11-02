"""Inyección de dependencias para los endpoints de la API v1.

Proporciona fábricas para resolver instancias de configuración, base vectorial,
servicios de recuperación RAG, auditoría persistente y el orquestador conversacional
del agente mediante el mecanismo `Depends` de FastAPI.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.agent import AgentService
from app.services.audit import AuditService
from app.services.rag import RAGService
from app.services.vector_store import VectorStoreService


def get_audit_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuditService:
    """Proporciona una instancia configurada del servicio de auditoría JSONL.

    Args:
        settings: configuración activa inyectada del sistema.

    Returns:
        Instancia de AuditService asociada a la ruta de persistencia configurada.
    """
    return AuditService(settings=settings)


def get_vector_store_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VectorStoreService:
    """Proporciona una instancia del almacén vectorial persistente ChromaDB.

    Args:
        settings: configuración activa inyectada del sistema.

    Returns:
        Instancia de VectorStoreService lista para operaciones de búsqueda e indexación.
    """
    return VectorStoreService(settings=settings)


def get_rag_service(
    settings: Annotated[Settings, Depends(get_settings)],
    vector_store: Annotated[VectorStoreService, Depends(get_vector_store_service)],
) -> RAGService:
    """Proporciona una instancia del pipeline de recuperación contextual RAG.

    Args:
        settings: configuración activa inyectada del sistema.
        vector_store: servicio de almacenamiento y búsqueda vectorial.

    Returns:
        Instancia de RAGService para ingesta y consultas sobre manuales técnicos.
    """
    return RAGService(settings=settings, vector_store=vector_store)


def get_agent_service(
    settings: Annotated[Settings, Depends(get_settings)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> AgentService:
    """Proporciona el orquestador conversacional basado en LangGraph y Tool Calling.

    Args:
        settings: configuración activa inyectada del sistema.
        rag_service: servicio de recuperación contextual documental.
        audit_service: servicio de registro persistente de auditoría de herramientas.

    Returns:
        Instancia de AgentService lista para procesar consultas de usuarios.
    """
    return AgentService(
        settings=settings,
        rag_service=rag_service,
        audit_service=audit_service,
    )


__all__ = [
    "get_agent_service",
    "get_audit_service",
    "get_rag_service",
    "get_vector_store_service",
]
