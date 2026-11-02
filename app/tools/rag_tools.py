"""Herramienta RAG para la búsqueda de documentación técnica y manuales operativos.

Expone una función factory que genera la herramienta invocable por el agente LangGraph,
conectándola con el servicio RAG e integrando un tracker de fuentes recuperadas
para alimentar las citas bibliográficas requeridas en la respuesta (ChatResponse.sources).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool, tool

if TYPE_CHECKING:
    from app.models.chat import SourceReference
    from app.services.rag import RAGService


def create_rag_tool(
    rag_service: RAGService,
    sources_tracker: list[SourceReference] | None = None,
) -> BaseTool:
    """Construye una herramienta de búsqueda documental vinculada al servicio RAG.

    Args:
        rag_service: instancia activa de RAGService para ejecutar la búsqueda vectorial.
        sources_tracker: lista mutable opcional donde se capturan las referencias
            de fuentes para que el orquestador pueda poblar ChatResponse.sources.

    Returns:
        Instancia de BaseTool lista para ser vinculada al agente y a ToolNode.
    """

    @tool("search_technical_documentation")
    def search_technical_documentation(query: str) -> str:
        """Busca procedimientos, guías y políticas operativas en la documentación técnica interna.

        Invoca esta herramienta cuando el usuario pregunte por procedimientos de reinicio,
        configuración, políticas de arquitectura, guías de despliegue o cualquier instrucción
        técnica documentada sobre los sistemas y servicios internos.

        Args:
            query: consulta textual o palabras clave descriptivas sobre el procedimiento o tema.

        Returns:
            Extractos formateados de los documentos más relevantes encontrados, o un mensaje
            indicando que no se localizó información relevante.
        """
        references = rag_service.retrieve(query)

        if sources_tracker is not None:
            sources_tracker.extend(references)

        if not references:
            return (
                "No se encontraron fragmentos de documentación técnica relevantes "
                "en la base de conocimiento para la consulta."
            )

        formatted_chunks: list[str] = []
        for idx, ref in enumerate(references, start=1):
            formatted_chunks.append(
                f"[Fragmento {idx}]\n"
                f"- Documento: {ref.document}\n"
                f"- Identificador: {ref.chunk_id}\n"
                f"- Relevancia: {ref.score:.2f}\n"
                f"- Extracto:\n{ref.excerpt}"
            )

        return "\n\n---\n\n".join(formatted_chunks)

    return search_technical_documentation


__all__ = [
    "create_rag_tool",
]
