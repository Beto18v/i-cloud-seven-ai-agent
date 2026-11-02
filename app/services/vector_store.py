"""Servicio de persistencia y búsqueda vectorial respaldado por ChromaDB.

Proporciona operaciones síncronas y asíncronas no bloqueantes para almacenar,
contar, resetear y consultar fragmentos documentales por similitud semántica.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _safe_cosine_relevance_score_fn(distance: float) -> float:
    """Calcula similitud coseno acotada a [0.0, 1.0] evitando desbordes por precisión flotante."""
    return max(0.0, min(1.0, 1.0 - distance))


class VectorStoreService:
    """Gestiona el almacén vectorial Chroma persistente para la indexación y recuperación RAG.

    Attributes:
        settings: configuración activa del servicio.
        embeddings: función o cliente generador de representaciones vectoriales.
    """

    def __init__(self, settings: Settings, embeddings: Embeddings | None = None) -> None:
        """Inicializa el almacén vectorial Chroma persistente.

        Args:
            settings: parámetros de configuración del sistema y rutas persistentes.
            embeddings: función de embeddings opcional; si no se suministra, se
                instancia OpenAIEmbeddings con las credenciales de settings.

        Raises:
            ValueError: si no se proveen embeddings y la configuración carece de API key.
        """
        self.settings: Settings = settings

        if embeddings is not None:
            self.embeddings: Embeddings = embeddings
        else:
            model_name_override = getattr(settings, "embedding_model", None)
            model_name: str = (
                str(model_name_override)
                if model_name_override is not None
                else settings.embedding_model_name_effective
            )

            api_key_candidate = getattr(settings, "api_key", None) or settings.llm_api_key
            if api_key_candidate is None:
                raise ValueError("No se configuró una API key válida en settings.")

            api_key_str: str = (
                api_key_candidate.get_secret_value()
                if hasattr(api_key_candidate, "get_secret_value")
                else str(api_key_candidate)
            )

            self.embeddings = OpenAIEmbeddings(
                model=model_name,
                openai_api_key=api_key_str,
                openai_api_base=settings.llm_base_url,
                request_timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )

            persist_dir: Path = Path(settings.vector_store_dir)
            persist_dir.mkdir(parents=True, exist_ok=True)

        persist_dir = Path(settings.vector_store_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._vector_store: Chroma = Chroma(
            collection_name=settings.collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(persist_dir),
            collection_metadata={"hnsw:space": settings.vector_store_space},
            relevance_score_fn=_safe_cosine_relevance_score_fn,
        )
        logger.info(
            "vector_store_initialized",
            collection=settings.collection_name,
            persist_directory=str(persist_dir),
            space=settings.vector_store_space,
        )

    @property
    def vector_store(self) -> Chroma:
        """Acceso a la instancia subyacente de Chroma.

        Returns:
            Instancia configurada de Chroma.
        """
        return self._vector_store

    def add_documents(self, documents: list[Document]) -> list[str]:
        """Inserta una lista de documentos en la colección vectorial.

        Args:
            documents: colección de instancias de Document a indexar.

        Returns:
            Lista de identificadores únicos generados para cada documento insertado.
        """
        if not documents:
            return []
        ids: list[str] = self._vector_store.add_documents(documents)
        logger.debug("vector_store_documents_added", count=len(documents))
        return ids

    def similarity_search_with_relevance_scores(
        self, query: str, k: int | None = None
    ) -> list[tuple[Document, float]]:
        """Recupera documentos similares a una consulta textual junto con su puntuación.

        Args:
            query: consulta textual en lenguaje natural.
            k: número máximo de documentos a retornar; si es None, toma top_k_results.

        Returns:
            Lista de tuplas (Document, score) ordenadas por mayor similitud.
        """
        cleaned_query: str = query.strip()
        effective_k: int = k if k is not None else self.settings.top_k_results
        if not cleaned_query or effective_k <= 0 or self.count() == 0:
            return []
        return self._vector_store.similarity_search_with_relevance_scores(
            cleaned_query, k=effective_k
        )

    def count(self) -> int:
        """Devuelve el total de fragmentos vectoriales almacenados en la colección.

        Returns:
            Entero con la cantidad de documentos persistidos en la colección activa.
        """
        return int(self._vector_store._collection.count())

    def reset(self) -> None:
        """Elimina por completo la colección actual y la recrea vacía con su configuración."""
        self._vector_store.reset_collection()
        logger.info("vector_store_collection_reset", collection=self.settings.collection_name)

    async def aadd_documents(self, documents: list[Document]) -> list[str]:
        """Versión asíncrona no bloqueante de add_documents ejecutada en hilo dedicado.

        Args:
            documents: colección de instancias de Document a indexar.

        Returns:
            Lista de identificadores únicos generados.
        """
        return await asyncio.to_thread(self.add_documents, documents)

    async def asimilarity_search_with_relevance_scores(
        self, query: str, k: int | None = None
    ) -> list[tuple[Document, float]]:
        """Versión asíncrona no bloqueante de similarity_search_with_relevance_scores.

        Args:
            query: consulta textual en lenguaje natural.
            k: número máximo de documentos a retornar.

        Returns:
            Lista de tuplas (Document, score) ordenadas por similitud.
        """
        return await asyncio.to_thread(self.similarity_search_with_relevance_scores, query, k)

    async def acount(self) -> int:
        """Versión asíncrona no bloqueante de count ejecutada en hilo dedicado.

        Returns:
            Entero con la cantidad de documentos indexados.
        """
        return await asyncio.to_thread(self.count)

    async def areset(self) -> None:
        """Versión asíncrona no bloqueante de reset ejecutada en hilo dedicado."""
        await asyncio.to_thread(self.reset)
