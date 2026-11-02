"""Configuración central del Enterprise Legacy Assistant.

Este módulo concentra **todo** el acceso a variables de entorno y es la única
fuente de verdad de la configuración. Ningún otro módulo debe leer
``os.environ``: la configuración se inyecta con :func:`get_settings`, que
devuelve una instancia inmutable y cacheada.

Principios de diseño
--------------------
1. **Fail-fast:** los errores de configuración se detectan al arrancar el
   proceso, no en la primera petición de un usuario.
2. **Secretos tipados:** las credenciales usan :class:`pydantic.SecretStr`, de
   modo que nunca se filtran en logs, trazas o serializaciones accidentales.
3. **Inmutabilidad:** ``frozen=True`` impide mutaciones en tiempo de ejecución.
4. **Portabilidad de rutas:** las rutas relativas se resuelven contra la raíz
   del proyecto, sin importar el directorio de trabajo del proceso.

Proveedor de IA
---------------
``AI_PROVIDER=azure_openai`` (primario) usa la **API v1** de Azure OpenAI, que
no requiere ``api-version``: basta el endpoint del recurso y apuntar el cliente
a ``<endpoint>/openai/v1``. ``AI_PROVIDER=openai`` queda como plan de
contingencia usando exactamente la misma ruta de código.

Precedencia de valores (el primero gana)
----------------------------------------
1. Argumentos del constructor, por ejemplo ``Settings(port=9000)``.
2. Variables de entorno del sistema operativo.
3. Archivo ``.env`` en la raíz del proyecto.
4. Valores por defecto declarados en esta clase.

Ejemplo
-------
>>> from app.core.config import get_settings
>>> settings = get_settings()
>>> settings.top_k_results
3
"""

from __future__ import annotations

import re
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Raíz del repositorio: ``<repo>/app/core/config.py`` -> ``<repo>``.
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: Detecta nombres de colección con forma de dirección IPv4 (Chroma los rechaza).
_IPV4_PATTERN: Final[re.Pattern[str]] = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")

#: Marcadores de la plantilla `.env.example` que jamás deben llegar a ejecución.
_PLACEHOLDER_MARKERS: Final[tuple[str, ...]] = (
    "replace_me",
    "replace-me",
    "changeme",
    "your_api_key",
    "your-api-key",
    "tu_api_key",
)


def _reject_placeholder(name: str, value: str) -> None:
    """Rechaza valores heredados sin sustituir de ``.env.example``.

    Args:
        name: nombre de la variable, usado en el mensaje de error.
        value: valor efectivo ya resuelto.

    Raises:
        ValueError: si el valor contiene un marcador de plantilla.
    """
    lowered = value.strip().lower()
    for marker in _PLACEHOLDER_MARKERS:
        if marker in lowered:
            raise ValueError(
                f"{name} conserva el valor de ejemplo de .env.example ({value!r}). "
                "Sustitúyelo por el valor real en el archivo .env."
            )


class _CaseInsensitiveStrEnum(StrEnum):
    """``StrEnum`` que resuelve sus miembros sin distinguir mayúsculas.

    Evita el fallo clásico de despliegue en el que ``LOG_LEVEL=info`` revienta
    porque el enum solo declara ``INFO``.
    """

    @classmethod
    def _missing_(cls, value: object) -> _CaseInsensitiveStrEnum | None:
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value.lower() == normalized:
                    return member
        return None


class Environment(_CaseInsensitiveStrEnum):
    """Entorno de ejecución del servicio."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(_CaseInsensitiveStrEnum):
    """Niveles de severidad aceptados por el logger estructurado."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AIProvider(_CaseInsensitiveStrEnum):
    """Proveedor de modelos de lenguaje y embeddings."""

    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"


class Settings(BaseSettings):
    """Configuración tipada y validada del servicio.

    Cada campo se puede sobrescribir con la variable de entorno homónima en
    mayúsculas (``TOP_K_RESULTS``, ``AZURE_OPENAI_API_KEY``, ...).
    """

    model_config = SettingsConfigDict(
        # Ruta absoluta: el `.env` se localiza en la raíz del repositorio aunque
        # el proceso se lance desde otro directorio (systemd, `--app-dir`, IDE).
        env_file=(str(PROJECT_ROOT / ".env"),),
        env_file_encoding="utf-8",
        case_sensitive=False,
        # `ignore` deliberado: en despliegue la plataforma inyecta variables
        # extra (WEBSITE_*, APPLICATIONINSIGHTS_*) que no deben romper el arranque.
        extra="ignore",
        frozen=True,
        validate_default=True,
        env_ignore_empty=True,
    )

    # ------------------------------------------------------------------
    # Aplicación y servidor
    # ------------------------------------------------------------------
    app_name: str = Field(
        default="Enterprise Legacy Assistant",
        min_length=1,
        max_length=120,
        description="Nombre expuesto en OpenAPI y en los logs de arranque.",
    )
    app_version: str = Field(
        default="0.1.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Versión semántica de la aplicación.",
    )
    api_v1_prefix: str = Field(
        default="/api/v1",
        pattern=r"^/.*$",
        description="Prefijo común de los endpoints versionados.",
    )
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Entorno lógico de ejecución.",
    )
    debug: bool = Field(
        default=False,
        description="Modo depuración. Prohibido en producción.",
    )
    host: str = Field(
        default="0.0.0.0",  # noqa: S104 - necesario para escuchar dentro del contenedor.
        description="Interfaz de escucha de ASGI.",
    )
    port: int = Field(default=8000, ge=1, le=65535, description="Puerto de escucha de ASGI.")
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Nivel mínimo de severidad registrado.",
    )
    log_json: bool = Field(
        default=True,
        description="True emite JSON Lines; False usa consola legible para desarrollo.",
    )
    cors_origins: str = Field(
        default="http://localhost:8000,http://127.0.0.1:8000",
        description="Orígenes CORS separados por coma.",
    )

    # ------------------------------------------------------------------
    # Proveedor de IA
    # ------------------------------------------------------------------
    ai_provider: AIProvider = Field(
        default=AIProvider.AZURE_OPENAI,
        description="Proveedor activo: 'azure_openai' (primario) u 'openai' (fallback).",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        description="API key de OpenAI. Obligatoria si AI_PROVIDER='openai'.",
    )
    openai_model_name: str = Field(
        default="gpt-5-mini",
        min_length=1,
        description="Modelo de chat cuando el proveedor es OpenAI directo.",
    )
    embedding_model_name: str = Field(
        default="text-embedding-3-small",
        min_length=1,
        description="Modelo de embeddings cuando el proveedor es OpenAI directo.",
    )
    llm_temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description=(
            "Temperatura del modelo. None (recomendado) no envía el parámetro: "
            "la familia gpt-5* puede rechazarlo."
        ),
    )
    llm_max_output_tokens: int = Field(
        default=500,
        ge=64,
        le=8192,
        description="Tope de tokens de salida por respuesta. Control de coste.",
    )
    llm_timeout_seconds: float = Field(
        default=10.0,
        gt=0.0,
        le=120.0,
        description="Timeout por llamada al proveedor de IA.",
    )
    llm_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Reintentos ante errores transitorios (429 / 5xx).",
    )
    agent_recursion_limit: int = Field(
        default=5,
        ge=2,
        le=25,
        description="Máximo de pasos del grafo por petición. Evita bucles infinitos.",
    )

    # ------------------------------------------------------------------
    # Azure OpenAI (API v1 — sin api-version)
    # ------------------------------------------------------------------
    azure_openai_api_key: SecretStr | None = Field(
        default=None,
        description=(
            "API key del recurso de Azure OpenAI. Obligatoria si AI_PROVIDER='azure_openai'."
        ),
    )
    azure_openai_endpoint: HttpUrl | None = Field(
        default=None,
        description="Endpoint del recurso, por ejemplo https://mi-recurso.openai.azure.com.",
    )
    azure_openai_chat_deployment: str | None = Field(
        default=None,
        min_length=1,
        description="Nombre del deployment de chat (no el nombre del modelo).",
    )
    azure_openai_embedding_deployment: str | None = Field(
        default=None,
        min_length=1,
        description="Nombre del deployment de embeddings (no el nombre del modelo).",
    )

    # ------------------------------------------------------------------
    # Pipeline RAG
    # ------------------------------------------------------------------
    chunk_size: int = Field(
        default=600,
        ge=100,
        le=4000,
        description="Tamaño de chunk en caracteres.",
    )
    chunk_overlap: int = Field(
        default=80,
        ge=0,
        le=1000,
        description="Solapamiento entre chunks en caracteres.",
    )
    top_k_results: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Fragmentos recuperados por consulta.",
    )
    similarity_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Relevancia mínima para considerar un fragmento como evidencia.",
    )
    collection_name: str = Field(
        default="legacy_docs",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{1,61}[A-Za-z0-9]$",
        description="Nombre de la colección en el vector store (reglas de Chroma).",
    )
    vector_store_space: Literal["cosine", "l2", "ip"] = Field(
        default="cosine",
        description=(
            "Métrica de distancia de Chroma. 'cosine' es obligatoria para que "
            "SIMILARITY_THRESHOLD sea interpretable."
        ),
    )

    # ------------------------------------------------------------------
    # Rutas y persistencia
    # ------------------------------------------------------------------
    base_dir: Path = Field(
        default=PROJECT_ROOT,
        description="Raíz contra la que se resuelven las rutas relativas.",
    )
    data_dir: Path = Field(default=Path("data"), description="Directorio de datos del proyecto.")
    vector_store_path: Path = Field(
        default=Path("data/vectorstore"),
        description="Directorio persistente del vector store.",
    )
    audit_log_path: Path = Field(
        default=Path("data/audit/audit.jsonl"),
        description="Archivo JSON Lines de auditoría.",
    )

    # ------------------------------------------------------------------
    # Validadores
    # ------------------------------------------------------------------
    @field_validator("*", mode="before")
    @classmethod
    def _strip_strings(cls, value: Any) -> Any:
        """Normaliza espacios accidentales en variables de entorno."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("openai_api_key", "azure_openai_api_key", mode="before")
    @classmethod
    def _blank_secret_is_absent(cls, value: Any) -> Any:
        """Convierte un secreto vacío o solo-espacios en ``None``.

        ``env_ignore_empty`` solo descarta la cadena exactamente vacía, no
        ``" "``. Sin esta normalización, una credencial en blanco pasaría la
        validación y el servicio arrancaría para fallar con 401 en la primera
        petición: justo lo contrario del fail-fast que se busca.
        """
        if isinstance(value, SecretStr) and not value.get_secret_value().strip():
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("azure_openai_endpoint")
    @classmethod
    def _validate_azure_endpoint(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Exige un endpoint TLS del host del recurso, sin ruta ni query.

        La API v1 se construye como ``<endpoint>/openai/v1``. Aceptar una ruta
        o una query produciría URLs inválidas y, peor, podría filtrar
        credenciales a los logs de arranque a través del resumen de
        configuración.
        """
        if value is None:
            return None
        if value.scheme != "https":
            raise ValueError(
                f"AZURE_OPENAI_ENDPOINT debe usar https:// (recibido: {value.scheme}://)."
            )
        if value.query or value.fragment:
            raise ValueError("AZURE_OPENAI_ENDPOINT no debe incluir query string ni fragmento.")
        if (value.path or "").strip("/"):
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT debe ser solo el host del recurso; "
                "el cliente añade /openai/v1 automáticamente."
            )
        return value

    @field_validator("base_dir")
    @classmethod
    def _normalize_base_dir(cls, value: Path) -> Path:
        """Resuelve ``BASE_DIR`` relativo contra la raíz del proyecto."""
        if not value.is_absolute():
            return (PROJECT_ROOT / value).resolve()
        return value

    @field_validator("vector_store_space", mode="before")
    @classmethod
    def _normalize_vector_space(cls, value: Any) -> Any:
        """Acepta ``COSINE`` igual que ``cosine``."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("collection_name")
    @classmethod
    def _validate_collection_name(cls, value: str) -> str:
        """Aplica las restricciones reales de Chroma para nombres de colección."""
        if ".." in value:
            raise ValueError("COLLECTION_NAME no puede contener '..'.")
        if _IPV4_PATTERN.fullmatch(value):
            raise ValueError("COLLECTION_NAME no puede tener formato de dirección IPv4.")
        return value

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, value: str) -> str:
        """Valida y normaliza la lista de orígenes CORS separada por comas."""
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS debe declarar al menos un origen.")
        for origin in origins:
            if origin != "*" and not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"Origen CORS inválido: {origin!r}. "
                    "Usa un esquema http:// o https://, o '*' en desarrollo."
                )
        return ",".join(origins)

    @model_validator(mode="after")
    def _validate_consistency(self) -> Settings:
        """Aplica reglas que involucran a más de un campo."""
        if self.ai_provider is AIProvider.AZURE_OPENAI:
            missing: list[str] = []
            if self.azure_openai_api_key is None:
                missing.append("AZURE_OPENAI_API_KEY")
            if self.azure_openai_endpoint is None:
                missing.append("AZURE_OPENAI_ENDPOINT")
            if not self.azure_openai_chat_deployment:
                missing.append("AZURE_OPENAI_CHAT_DEPLOYMENT")
            if not self.azure_openai_embedding_deployment:
                missing.append("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
            if missing:
                raise ValueError("AI_PROVIDER='azure_openai' requiere: " + ", ".join(missing))

            # Los marcadores de la plantilla son valores sintácticamente válidos:
            # sin este control el servicio arrancaría y fallaría con 401.
            _reject_placeholder(
                "AZURE_OPENAI_API_KEY",
                self.azure_openai_api_key.get_secret_value() if self.azure_openai_api_key else "",
            )
            if self.azure_openai_endpoint is not None:
                _reject_placeholder("AZURE_OPENAI_ENDPOINT", str(self.azure_openai_endpoint))

        if (
            self.ai_provider is AIProvider.OPENAI
            and self.environment is not Environment.TESTING
            and self.openai_api_key is None
        ):
            raise ValueError(
                "OPENAI_API_KEY es obligatoria cuando AI_PROVIDER='openai'. "
                "Defínela en el archivo .env (ver .env.example)."
            )

        if self.ai_provider is AIProvider.OPENAI and self.openai_api_key is not None:
            _reject_placeholder("OPENAI_API_KEY", self.openai_api_key.get_secret_value())

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"CHUNK_OVERLAP ({self.chunk_overlap}) debe ser menor que "
                f"CHUNK_SIZE ({self.chunk_size}); de lo contrario el chunking no avanza."
            )

        if self.environment is Environment.PRODUCTION:
            if self.debug:
                raise ValueError("DEBUG debe ser False cuando ENVIRONMENT='production'.")
            if "*" in self.cors_origins_list:
                raise ValueError("CORS_ORIGINS no puede ser '*' cuando ENVIRONMENT='production'.")

        return self

    # ------------------------------------------------------------------
    # Rutas derivadas
    # ------------------------------------------------------------------
    def resolve_path(self, candidate: Path) -> Path:
        """Resuelve ``candidate`` contra :attr:`base_dir` si es relativa."""
        if candidate.is_absolute():
            return candidate
        return (self.base_dir / candidate).resolve()

    @property
    def documents_dir(self) -> Path:
        """Directorio con los manuales de conocimiento."""
        return self.resolve_path(self.data_dir / "documents")

    @property
    def mock_tickets_path(self) -> Path:
        """Archivo JSON que simula el sistema legado de solicitudes."""
        return self.resolve_path(self.data_dir / "mock_tickets.json")

    @property
    def vector_store_dir(self) -> Path:
        """Directorio persistente del vector store."""
        return self.resolve_path(self.vector_store_path)

    @property
    def audit_file(self) -> Path:
        """Archivo JSON Lines de auditoría."""
        return self.resolve_path(self.audit_log_path)

    # ------------------------------------------------------------------
    # Derivados de configuración
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """``True`` cuando el servicio corre en producción."""
        return self.environment is Environment.PRODUCTION

    @property
    def is_azure(self) -> bool:
        """``True`` cuando el proveedor activo es Azure OpenAI."""
        return self.ai_provider is AIProvider.AZURE_OPENAI

    @property
    def cors_origins_list(self) -> list[str]:
        """Orígenes CORS normalizados como lista."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_base_url(self) -> str:
        """URL base del cliente compatible con OpenAI.

        Para Azure OpenAI se construye el endpoint de la **API v1**
        (``<endpoint>/openai/v1``), que no requiere ``api-version``.
        Para OpenAI directo se devuelve la URL pública por defecto.
        """
        if not self.is_azure:
            return "https://api.openai.com/v1"
        endpoint = str(self.azure_openai_endpoint or "").rstrip("/")
        return f"{endpoint}/openai/v1"

    @property
    def llm_api_key(self) -> SecretStr | None:
        """Credencial del proveedor activo, sin exponer su valor."""
        if self.is_azure:
            return self.azure_openai_api_key
        return self.openai_api_key

    @property
    def chat_model_name(self) -> str:
        """Modelo o deployment de chat efectivo según el proveedor activo.

        Raises:
            RuntimeError: si el proveedor es Azure y no hay deployment definido.
                No debería ocurrir tras la validación, pero se falla de forma
                explícita en lugar de enviar una cadena vacía al proveedor.
        """
        if self.is_azure:
            deployment = self.azure_openai_chat_deployment
            if not deployment:
                raise RuntimeError("AZURE_OPENAI_CHAT_DEPLOYMENT no está definido.")
            return deployment
        return self.openai_model_name

    @property
    def embedding_model_name_effective(self) -> str:
        """Modelo o deployment de embeddings efectivo según el proveedor.

        Raises:
            RuntimeError: si el proveedor es Azure y no hay deployment definido.
        """
        if self.is_azure:
            deployment = self.azure_openai_embedding_deployment
            if not deployment:
                raise RuntimeError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT no está definido.")
            return deployment
        return self.embedding_model_name

    @property
    def sends_temperature(self) -> bool:
        """``True`` si el cliente debe enviar ``temperature`` al proveedor.

        Con la familia ``gpt-5*`` este parámetro puede ser rechazado; dejando
        ``LLM_TEMPERATURE`` vacía, el cliente simplemente no lo envía.
        """
        return self.llm_temperature is not None

    def ensure_directories(self) -> None:
        """Crea los directorios de trabajo necesarios, de forma idempotente.

        Se invoca explícitamente en el ``lifespan`` de FastAPI y nunca al
        importar el módulo, para no introducir efectos secundarios en el import.
        """
        for directory in (self.documents_dir, self.vector_store_dir, self.audit_file.parent):
            directory.mkdir(parents=True, exist_ok=True)

    def redacted_summary(self) -> dict[str, Any]:
        """Resumen seguro de la configuración, apto para logs de arranque.

        Nunca incluye el valor de un secreto: solo indica si está configurado.
        """
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment.value,
            "debug": self.debug,
            "ai_provider": self.ai_provider.value,
            "chat_model": self.chat_model_name,
            "embedding_model": self.embedding_model_name_effective,
            "llm_base_url": self.llm_base_url,
            "llm_temperature": self.llm_temperature,
            "sends_temperature": self.sends_temperature,
            "llm_max_output_tokens": self.llm_max_output_tokens,
            "llm_timeout_seconds": self.llm_timeout_seconds,
            "agent_recursion_limit": self.agent_recursion_limit,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "top_k_results": self.top_k_results,
            "similarity_threshold": self.similarity_threshold,
            "vector_store_space": self.vector_store_space,
            "vector_store_dir": str(self.vector_store_dir),
            "openai_api_key_configured": self.openai_api_key is not None,
            "azure_openai_api_key_configured": self.azure_openai_api_key is not None,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración validada del proceso (singleton perezoso).

    El resultado se cachea para validar una sola vez. En pruebas se limpia con
    :func:`reset_settings_cache`.

    Returns:
        Settings: instancia inmutable y ya validada.

    Raises:
        pydantic.ValidationError: si alguna variable de entorno es inválida o
            falta una credencial requerida por el proveedor activo.
    """
    return Settings()


def reset_settings_cache() -> None:
    """Invalida el singleton de configuración (útil en pruebas)."""
    get_settings.cache_clear()


__all__ = [
    "PROJECT_ROOT",
    "AIProvider",
    "Environment",
    "LogLevel",
    "Settings",
    "get_settings",
    "reset_settings_cache",
]
