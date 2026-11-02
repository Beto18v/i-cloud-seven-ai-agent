"""Pipeline de Recuperación Aumentada por Generación (RAG) para manuales operativos.

Gestiona la ingesta de documentos Markdown, su segmentación semántica (chunking),
la persistencia indexada en ChromaDB y la recuperación contextual con verificación
determinista de fundamentación (groundedness).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.chat import SourceReference
from app.services.vector_store import VectorStoreService

logger = get_logger(__name__)


class IngestSummary(BaseModel):
    """Resumen inmutable del proceso de ingesta e indexación documental.

    Attributes:
        total_files: cantidad de archivos Markdown procesados.
        total_chunks: cantidad total de fragmentos generados e insertados en el almacén.
        documents: lista con los nombres de archivo procesados.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_files: int = Field(
        ge=0,
        description="Cantidad total de archivos Markdown procesados.",
    )
    total_chunks: int = Field(
        ge=0,
        description="Cantidad total de fragmentos vectoriales indexados.",
    )
    documents: list[str] = Field(
        default_factory=list,
        description="Nombres de los archivos Markdown incluidos en la ingesta.",
    )


class RAGService:
    """Orquesta la ingestión de manuales, segmentación semántica y recuperación contextual RAG.

    Attributes:
        settings: configuración activa del sistema.
        vector_store: servicio de persistencia y búsqueda vectorial.
    """

    def __init__(self, settings: Settings, vector_store: VectorStoreService) -> None:
        """Inicializa el servicio RAG asociándolo a la configuración y vector store activo.

        Args:
            settings: parámetros de configuración del pipeline RAG.
            vector_store: instancia del servicio vectorial sobre el que se ejecutan operaciones.
        """
        self.settings: Settings = settings
        self.vector_store: VectorStoreService = vector_store

    def ingest_documents(
        self, docs_dir: Path | None = None, force_reindex: bool = False
    ) -> IngestSummary:
        """Lee los archivos Markdown del directorio, los segmenta y los indexa en Chroma.

        Args:
            docs_dir: ruta del directorio con archivos .md; si es None, usa settings.documents_dir.
            force_reindex: si es True, vacía previamente la colección antes de indexar.

        Returns:
            IngestSummary con las estadísticas de archivos procesados y fragmentos creados.
        """
        target_dir: Path = docs_dir if docs_dir is not None else self.settings.documents_dir

        if force_reindex:
            logger.info("rag_force_reindex_triggered", collection=self.settings.collection_name)
            self.vector_store.reset()

        if not target_dir.exists() or not target_dir.is_dir():
            logger.warning("rag_ingest_directory_missing", directory=str(target_dir))
            return IngestSummary(total_files=0, total_chunks=0, documents=[])

        md_files: list[Path] = sorted(path for path in target_dir.glob("*.md") if path.is_file())
        if not md_files:
            logger.info("rag_ingest_no_markdown_files_found", directory=str(target_dir))
            return IngestSummary(total_files=0, total_chunks=0, documents=[])

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
        )

        all_documents: list[Document] = []
        processed_documents: list[str] = []

        for file_path in md_files:
            file_name: str = file_path.name
            processed_documents.append(file_name)
            content: str = file_path.read_text(encoding="utf-8")
            if not content.strip():
                continue

            chunks: list[str] = splitter.split_text(content)
            for idx, chunk_text in enumerate(chunks):
                cleaned_chunk: str = chunk_text.strip()
                if not cleaned_chunk:
                    continue

                metadata: dict[str, Any] = {
                    "source": file_name,
                    "chunk_id": f"{file_path.stem}:{idx}",
                    "document_name": file_name,
                }
                all_documents.append(Document(page_content=cleaned_chunk, metadata=metadata))

        if all_documents:
            self.vector_store.add_documents(all_documents)

        summary = IngestSummary(
            total_files=len(processed_documents),
            total_chunks=len(all_documents),
            documents=processed_documents,
        )
        logger.info(
            "rag_ingest_completed",
            total_files=summary.total_files,
            total_chunks=summary.total_chunks,
        )
        return summary

    def retrieve(self, query: str, top_k: int | None = None) -> list[SourceReference]:
        """Recupera fragmentos documentales contextualmente relevantes para una consulta.

        Args:
            query: texto de consulta del usuario o del agente.
            top_k: cantidad máxima de fragmentos a recuperar; si es None, usa top_k_results.

        Returns:
            Lista de referencias bibliográficas normalizadas (SourceReference).
        """
        cleaned_query: str = query.strip()
        if not cleaned_query:
            return []

        effective_k: int = top_k or self.settings.top_k_results
        results: list[tuple[Document, float]] = (
            self.vector_store.similarity_search_with_relevance_scores(
                query=cleaned_query, k=effective_k
            )
        )

        references: list[SourceReference] = []
        for doc, score in results:
            doc_source: str = str(doc.metadata.get("source") or "desconocido")
            chunk_id: str = str(doc.metadata.get("chunk_id") or "c0")
            clamped_score: float = round(max(0.0, min(1.0, float(score))), 4)
            raw_excerpt: str = doc.page_content[:500].strip()
            excerpt: str = raw_excerpt if raw_excerpt else "(Sin extracto disponible)"

            references.append(
                SourceReference(
                    document=doc_source,
                    chunk_id=chunk_id,
                    score=clamped_score,
                    excerpt=excerpt,
                )
            )

        return references

    def is_grounded(self, sources: list[SourceReference]) -> bool:
        """Determina si las fuentes recuperadas superan el umbral mínimo de fundamentación (D11).

        Args:
            sources: lista de referencias bibliográficas obtenidas del almacén vectorial.

        Returns:
            True si existen fuentes y al menos una alcanza o supera el umbral similarity_threshold;
            False si la lista está vacía o ninguna fuente alcanza el umbral.
        """
        return bool(sources) and max(s.score for s in sources) >= self.settings.similarity_threshold

    async def aingest_documents(
        self, docs_dir: Path | None = None, force_reindex: bool = False
    ) -> IngestSummary:
        """Versión asíncrona no bloqueante de ingest_documents ejecutada en hilo secundario.

        Args:
            docs_dir: ruta opcional con los manuales markdown.
            force_reindex: indica si se debe purgar el vector store antes de indexar.

        Returns:
            Resumen estructurado de la ingesta efectuada.
        """
        return await asyncio.to_thread(self.ingest_documents, docs_dir, force_reindex)

    async def aretrieve(self, query: str, top_k: int | None = None) -> list[SourceReference]:
        """Versión asíncrona no bloqueante de retrieve ejecutada en hilo secundario.

        Args:
            query: texto de consulta semántica.
            top_k: cantidad opcional de resultados máximos a recuperar.

        Returns:
            Lista de referencias documentales relevantes recuperadas.
        """
        return await asyncio.to_thread(self.retrieve, query, top_k)
