"""Configuración de logging estructurado del Enterprise Legacy Assistant.

El módulo integra **structlog** con el módulo estándar :mod:`logging` mediante
:class:`structlog.stdlib.ProcessorFormatter`, de modo que tanto los logs
emitidos por la aplicación como los de ``uvicorn``, ``fastapi`` o cualquier
librería que use ``logging`` se renderizan con el mismo formato:

* **JSON Lines** cuando ``LOG_JSON=true`` (entorno productivo).
* **Consola legible** cuando ``LOG_JSON=false`` (desarrollo local).

Seguridad
---------
La cadena de procesadores aplica **dos capas complementarias** de redacción:

1. **Por clave:** cualquier valor cuya clave sea sensible (``api_key``,
   ``authorization``, ``cookie``, ``connection_string``, ``token``...) o que
   sea una instancia de :class:`pydantic.SecretStr` se sustituye por
   ``***REDACTED***``, con independencia de su tipo.
2. **Por contenido:** después de :func:`structlog.processors.format_exc_info`,
   un procesador recorre de forma recursiva ``dict``, ``list``, ``tuple`` y
   ``str`` y sustituye en **todos** los textos los patrones de credencial
   conocidos (claves ``sk-...``, cabeceras ``Bearer ...`` y asignaciones
   ``api_key=...``, ``Cookie: ...``, etc.). Esto cubre el campo ``event``,
   ``exception`` (traceback ya formateado), argumentos ya formateados y los
   ``extra`` de los registros de ``logging``.

Las métricas numéricas legítimas (``token_count``, ``token_usage``,
``llm_max_output_tokens``) no se redactan mientras su valor sea ``int`` o
``float``; la palabra ``token`` solo dispara la redacción cuando el valor es
texto o :class:`pydantic.SecretStr`.

Correlación
-----------
La variable de contexto :data:`correlation_id_var` permite asociar todas las
entradas de una petición. Si tiene valor en el momento de emitir el log, el
procesador :func:`add_common_fields` lo publica en el campo
``correlation_id``.
"""

from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Final

import structlog
from pydantic import SecretStr
from structlog.typing import EventDict, Processor, WrappedLogger

from app.core.config import Settings

#: Valor que reemplaza a cualquier secreto detectado.
REDACTED_VALUE: Final[str] = "***REDACTED***"

#: Identificador de correlación disponible para el logger durante una petición.
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

#: Atributo que marca los handlers instalados por este módulo.
_HANDLER_MARKER: Final[str] = "_ela_structured_handler"

#: Loggers de terceros que deben delegar en el handler raíz.
_MANAGED_LOGGERS: Final[tuple[str, ...]] = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
)

#: Partes de clave que identifican un valor sensible como palabra completa.
#: ``token`` se evalúa aparte para no redactar métricas numéricas.
_SENSITIVE_KEY_PARTS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "authorization",
        "cookie",
        "credential",
        "credentials",
    }
)

#: Claves sensibles compuestas que deben detectarse como unidad. Incluye las
#: formas sin separadores (``apikey``) y las que la normalización convierte en
#: una sola pieza (``connection_string``, ``set_cookie``).
_SENSITIVE_KEY_COMPOUND: Final[frozenset[str]] = frozenset(
    {
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
        "connection_string",
        "set_cookie",
    }
)

#: Partes que, junto con ``key``, forman una credencial (``access_key``,
#: ``private_key``, ``signing_key``, ``x_api_key``).
_KEY_TYPE_PARTS: Final[frozenset[str]] = frozenset({"api", "access", "private", "signing"})

#: Normaliza una clave a minúsculas separadas por guiones bajos.
_KEY_NORMALIZER: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")

#: Separa límites camelCase antes de normalizar (``refreshToken``,
#: ``maxOutputTokens``, ``APIKey``) sin confundir plurales como ``tokens``.
_CAMEL_BOUNDARY: Final[re.Pattern[str]] = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)

#: Credenciales con prefijo propio. El mínimo de 6 caracteres cubre el secreto
#: ficticio ``sk-LEAKME4`` sin casar nombres benignos como ``sk-learn`` (5).
_OPENAI_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"sk-[A-Za-z0-9_-]{6,}")

#: Cabeceras ``Authorization: Bearer <token>``.
_BEARER_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]+")

#: Asignaciones ``clave=valor`` o ``clave: valor`` en texto libre, incluidas
#: las representaciones de diccionarios de Python (``'Cookie': 'valor'``).
_ASSIGNMENT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)"
    r"((?:api[_-]?key|access[_-]?key|private[_-]?key|signing[_-]?key|"
    r"client[_-]?secret|connection[_-]?string|set[_-]?cookie|"
    r"token|secret|password|passwd|authorization|cookie)"
    r"""['"]?\s*[=:]\s*['"]?)"""
    r"""[^\s&"',;}]+"""
)

#: Reglas de redacción por contenido, aplicadas en orden. ``Bearer`` va antes
#: que las asignaciones para que ``authorization: Bearer x`` no deje ``x``.
_TEXT_RULES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (_BEARER_PATTERN, f"Bearer {REDACTED_VALUE}"),
    (_OPENAI_KEY_PATTERN, REDACTED_VALUE),
    (_ASSIGNMENT_PATTERN, rf"\1{REDACTED_VALUE}"),
)


def _normalize_key(key: str) -> str:
    """Convierte una clave a minúsculas separadas por guiones bajos.

    Args:
        key: nombre original del campo.

    Returns:
        Clave normalizada, con los límites camelCase convertidos en ``_``.
    """
    spaced = _CAMEL_BOUNDARY.sub("_", key.strip())
    return _KEY_NORMALIZER.sub("_", spaced.lower()).strip("_")


def _is_numeric(value: Any) -> bool:
    """Indica si un valor es numérico (``bool`` no cuenta como número).

    Args:
        value: valor a inspeccionar.

    Returns:
        ``True`` solo para ``int`` o ``float`` reales.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_sensitive_key(key: str, value: Any = None) -> bool:
    """Indica si una clave del event dict debe redactarse.

    Args:
        key: nombre del campo que se va a registrar.
        value: valor asociado. Se usa para no redactar métricas numéricas
            como ``token_count`` o ``token_usage``.

    Returns:
        ``True`` si la clave representa una credencial o un dato sensible.
    """
    normalized = _normalize_key(key)
    if not normalized:
        return False

    if normalized in _SENSITIVE_KEY_COMPOUND:
        return True

    parts = normalized.split("_")
    if any(part in _SENSITIVE_KEY_PARTS for part in parts):
        return True

    # ``openai_api_key`` / ``accessKey`` / ``private-key`` / ``x-api-key``.
    if "key" in parts and any(part in _KEY_TYPE_PARTS for part in parts):
        return True

    # ``token`` solo es sensible cuando transporta texto; los contadores
    # numéricos (``token_count``, ``token_usage``) son métricas legítimas.
    if "token" in parts:
        return not _is_numeric(value)

    return False


def _redact_value(value: Any) -> Any:
    """Redacta recursivamente secretos dentro de un valor ya anidado.

    Args:
        value: valor arbitrario (dict, lista, tupla, escalar o ``SecretStr``).

    Returns:
        Una copia del valor con los secretos sustituidos por
        :data:`REDACTED_VALUE`.
    """
    if isinstance(value, SecretStr):
        return REDACTED_VALUE
    if isinstance(value, dict):
        return {
            key: REDACTED_VALUE if _is_sensitive_key(str(key), item) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_text(value: str) -> str:
    """Sustituye patrones de credencial dentro de un texto libre.

    Args:
        value: texto a sanear (mensaje, traceback o argumento formateado).

    Returns:
        Texto con las credenciales sustituidas por :data:`REDACTED_VALUE`.
    """
    for pattern, replacement in _TEXT_RULES:
        value = pattern.sub(replacement, value)
    return value


def _redact_text_value(value: Any) -> Any:
    """Recorre recursivamente un valor y redacta todas las cadenas de texto.

    Args:
        value: valor arbitrario del event dict.

    Returns:
        Copia del valor con sus cadenas saneadas.
    """
    if isinstance(value, SecretStr):
        return REDACTED_VALUE
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            key: REDACTED_VALUE if _is_sensitive_key(str(key), item) else _redact_text_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_text_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_text_value(item) for item in value)
    return value


def redact_secrets(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Redacta credenciales por clave antes de renderizar la entrada.

    Redacta valores por clave sensible y también cualquier instancia de
    :class:`pydantic.SecretStr`, aunque aparezca bajo una clave que no parezca
    sospechosa. El contenido de los textos lo sanea
    :func:`redact_text_secrets`, que se ejecuta después de formatear los
    tracebacks.

    Args:
        _logger: logger subyacente, no utilizado.
        _method_name: nombre del método de logging, no utilizado.
        event_dict: campos de la entrada de log.

    Returns:
        El mismo event dict, ya saneado.
    """
    for key, value in list(event_dict.items()):
        if _is_sensitive_key(str(key), value):
            event_dict[key] = REDACTED_VALUE
        else:
            event_dict[key] = _redact_value(value)
    return event_dict


def redact_text_secrets(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Redacta credenciales incrustadas en cualquier texto del event dict.

    Debe ejecutarse **después** de :func:`structlog.processors.format_exc_info`
    para que el traceback ya convertido en cadena también se inspeccione.

    Args:
        _logger: logger subyacente, no utilizado.
        _method_name: nombre del método de logging, no utilizado.
        event_dict: campos de la entrada de log.

    Returns:
        El mismo event dict, con todos sus textos saneados.
    """
    for key, value in list(event_dict.items()):
        if _is_sensitive_key(str(key), value):
            event_dict[key] = REDACTED_VALUE
        else:
            event_dict[key] = _redact_text_value(value)
    return event_dict


def add_common_fields(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Inyecta timestamp, nivel, logger y correlación en cada entrada.

    Se aplica tanto a logs nativos de structlog como a registros ajenos.
    Para estos últimos, ``ProcessorFormatter`` adjunta el ``LogRecord``
    original bajo la clave ``_record``.

    Args:
        logger: logger subyacente (``logging.Logger`` en la práctica).
        method_name: nombre del método de logging (``info``, ``warning``...).
        event_dict: campos de la entrada de log.

    Returns:
        El event dict enriquecido con los campos comunes.
    """
    event_dict["timestamp"] = datetime.now(UTC).isoformat()

    record = event_dict.get("_record")
    level: str
    logger_name: str | None
    if isinstance(record, logging.LogRecord):
        level = record.levelname
        logger_name = record.name
    else:
        level = method_name.upper()
        candidate = getattr(logger, "name", None)
        logger_name = candidate if isinstance(candidate, str) else None

    event_dict["level"] = level
    if logger_name:
        event_dict["logger"] = logger_name

    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict.setdefault("correlation_id", correlation_id)

    return event_dict


def _shared_processors() -> list[Processor]:
    """Construye la cadena común a structlog y a ``logging``.

    El orden es deliberado: primero se resuelven argumentos posicionales y
    ``extra``, después se redacta por clave, luego se formatea el traceback y
    por último se inspecciona todo el texto resultante.

    Returns:
        Procesadores que añaden contexto, redactan secretos y normalizan
        excepciones.
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.ExtraAdder(),
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_common_fields,
        redact_secrets,
        structlog.processors.format_exc_info,
        redact_text_secrets,
    ]


def _remove_managed_handlers(logger: logging.Logger) -> None:
    """Retira y cierra los handlers instalados previamente por este módulo.

    Args:
        logger: logger del que se eliminan los handlers marcados.
    """
    for handler in tuple(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()


def _detach_all_handlers(logger: logging.Logger) -> None:
    """Retira y cierra **todos** los handlers de un logger gestionado.

    ``uvicorn`` instala sus propios handlers (no marcados) al arrancar. Si se
    dejan conectados, cada registro se emite dos veces: una línea de texto
    plano por el handler de ``uvicorn`` y otra JSON al propagar al handler
    raíz. Vaciar el logger es intencional, no redundante con
    :func:`_remove_managed_handlers`.

    Args:
        logger: logger cuyos handlers se desconectan por completo.
    """
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def configure_logging(settings: Settings) -> None:
    """Configura structlog y ``logging`` de forma idempotente.

    Se puede invocar varias veces: cada llamada reemplaza el handler propio y
    reinstala la configuración, sin acumular handlers duplicados. También
    redirige los loggers de ``uvicorn`` y ``fastapi`` al handler raíz para que
    se rendericen como JSON.

    Se invoca al construir la aplicación (:func:`app.main.create_app`) y de
    nuevo en el ``lifespan``. La primera llamada garantiza que las líneas de
    arranque del propio ``uvicorn`` (anteriores al ``lifespan``) ya salgan en
    JSON; la segunda es idempotente y cubre reconfiguraciones en pruebas.

    Args:
        settings: configuración validada de la aplicación; de ella se toman
            ``log_json`` y ``log_level``.
    """
    level = logging.getLevelName(settings.log_level.value)
    if not isinstance(level, int):
        level = logging.INFO

    renderer: Processor
    if settings.log_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors(),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    _remove_managed_handlers(root_logger)
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    structlog.configure(
        processors=[
            *_shared_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    for managed_name in _MANAGED_LOGGERS:
        managed_logger = logging.getLogger(managed_name)
        _detach_all_handlers(managed_logger)
        managed_logger.propagate = True
        managed_logger.setLevel(level)

    _quiet_library_noise(level)


def _quiet_library_noise(level: int) -> None:
    """Ajusta loggers de librerías ruidosas al nivel configurado.

    Args:
        level: nivel mínimo de severidad ya resuelto.
    """
    for noisy_name in ("httpx", "httpcore", "chromadb"):
        logging.getLogger(noisy_name).setLevel(max(level, logging.WARNING))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Devuelve un logger estructurado vinculado al nombre indicado.

    Args:
        name: nombre lógico del logger, habitualmente ``__name__``.

    Returns:
        Logger compatible con ``logging`` que ejecuta la cadena de structlog.
    """
    return structlog.stdlib.get_logger(name)


__all__ = [
    "REDACTED_VALUE",
    "add_common_fields",
    "configure_logging",
    "correlation_id_var",
    "get_logger",
    "redact_secrets",
    "redact_text",
    "redact_text_secrets",
]
