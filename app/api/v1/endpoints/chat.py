"""Endpoint para el canal conversacional del Enterprise Legacy Assistant."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_agent_service
from app.models.chat import ChatRequest, ChatResponse
from app.services.agent import AgentService

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Procesar consulta con el asistente conversacional",
    description=(
        "Procesa una consulta del usuario a través del orquestador LangGraph con "
        "selección determinista de herramientas (TC-02, TC-03), recuperación RAG (TC-01) "
        "y guardrails de seguridad (TC-05) y ausencia de información (TC-04)."
    ),
)
async def process_chat(
    request: ChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ChatResponse:
    """Procesa una consulta conversacional delegándola en el orquestador del agente.

    Args:
        request: carga útil validada con la consulta, identificador opcional de sesión y usuario.
        agent_service: servicio de agente autónomo inyectado por FastAPI.

    Returns:
        ChatResponse con la respuesta fundamentada, citas documentales y resumen de herramientas.
    """
    return await agent_service.aprocess_chat(
        query=request.query,
        session_id=request.session_id,
        user_id=request.user_id,
    )


__all__ = ["router"]
