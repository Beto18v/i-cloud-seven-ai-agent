"""Pruebas del pipeline de logging estructurado y de la redacción de secretos."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import datetime

import pytest
import structlog
from pydantic import SecretStr

from app.core.config import Settings
from app.core.logging import (
    _HANDLER_MARKER,
    REDACTED_VALUE,
    configure_logging,
    correlation_id_var,
    get_logger,
    redact_secrets,
    redact_text,
)


@pytest.fixture(autouse=True)
def _isolate_logging() -> Iterator[None]:
    """Limpia structlog y los handlers propios antes y después de cada prueba."""
    _remove_managed_root_handlers()
    structlog.reset_defaults()
    yield
    _remove_managed_root_handlers()
    structlog.reset_defaults()


def _remove_managed_root_handlers() -> None:
    """Desconecta los handlers instalados por el módulo bajo prueba."""
    root_logger = logging.getLogger()
    for handler in tuple(root_logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            root_logger.removeHandler(handler)
            handler.close()


def _captured_stderr(capsys: pytest.CaptureFixture[str]) -> str:
    """Vacía el buffer de stderr tras hacer flush en los handlers."""
    for handler in logging.getLogger().handlers:
        handler.flush()
    return capsys.readouterr().err


def test_redact_secrets_covers_keys_and_secretstr() -> None:
    """Se redactan claves sensibles, anidados y cualquier ``SecretStr``."""
    event = redact_secrets(
        None,
        "info",
        {
            "api_key": "plain-key",
            "authorization": "Bearer token-value",
            "access_token": "token-value",
            "client_secret": "secret-value",
            "password": "password-value",
            "refreshToken": "camel-case-value",
            "token_count": 500,
            "token_usage": 1200.5,
            "max_output_tokens": 500,
            "maxOutputTokens": 700,
            "nested": {"openai_api_key": "nested-key"},
            "payload": SecretStr("hidden-secret"),
        },
    )

    assert event["api_key"] == REDACTED_VALUE
    assert event["authorization"] == REDACTED_VALUE
    assert event["access_token"] == REDACTED_VALUE
    assert event["client_secret"] == REDACTED_VALUE
    assert event["password"] == REDACTED_VALUE
    assert event["refreshToken"] == REDACTED_VALUE
    assert event["token_count"] == 500
    assert event["token_usage"] == 1200.5
    assert event["max_output_tokens"] == 500
    assert event["maxOutputTokens"] == 700
    assert event["nested"] == {"openai_api_key": REDACTED_VALUE}
    assert event["payload"] == REDACTED_VALUE


@pytest.mark.parametrize(
    "key",
    [
        "credentials",
        "connection_string",
        "connectionString",
        "cookie",
        "set-cookie",
        "set_cookie",
        "access_key",
        "accessKey",
        "signing_key",
        "signingKey",
        "private_key",
        "privateKey",
        "client_secret",
        "clientSecret",
        "refresh_token",
        "refreshToken",
        "id_token",
        "idToken",
        "session_token",
        "sessionToken",
        "x-api-key",
        "X-Api-Key",
        "APIKey",
    ],
)
def test_sensitive_key_variants_are_redacted(key: str) -> None:
    """La denylist cubre camelCase y variantes con guion o guion bajo."""
    event = redact_secrets(None, "info", {key: "LEAKME9"})

    assert event[key] == REDACTED_VALUE


def test_numeric_token_metrics_are_not_redacted() -> None:
    """``token`` solo se redacta cuando el valor es texto o ``SecretStr``."""
    event = redact_secrets(
        None,
        "info",
        {
            "token_count": 12,
            "token_usage": 34.5,
            "llm_max_output_tokens": 500,
            "token": "LEAKME9",
        },
    )

    assert event["token_count"] == 12
    assert event["token_usage"] == 34.5
    assert event["llm_max_output_tokens"] == 500
    assert event["token"] == REDACTED_VALUE


def test_redact_text_covers_bare_keys_bearer_and_assignments() -> None:
    """El escaneo de texto cubre ``sk-``, ``Bearer`` y ``clave=valor``."""
    text = "GET /api/v1/chat?api_key=LEAKME7&x=1 authorization: Bearer abc.def sk-LEAKME4"

    sanitized = redact_text(text)

    assert "LEAKME7" not in sanitized
    assert "abc.def" not in sanitized
    assert "sk-LEAKME4" not in sanitized
    assert sanitized.count(REDACTED_VALUE) >= 3


def test_configure_logging_is_idempotent(settings: Settings) -> None:
    """Invocar la configuración dos veces no acumula handlers propios."""
    configure_logging(settings)
    configure_logging(settings)

    managed_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, _HANDLER_MARKER, False)
    ]
    assert len(managed_handlers) == 1


def test_json_output_covers_native_and_stdlib_logs(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Structlog y ``uvicorn`` emiten JSON válido con campos comunes."""
    json_settings = Settings(log_json=True)
    configure_logging(json_settings)

    token = correlation_id_var.set("req-123")
    try:
        get_logger("tests.logging").info("native_event", answer=42)
        logging.getLogger("uvicorn.error").info("stdlib_event")
    finally:
        correlation_id_var.reset(token)

    lines = [line for line in _captured_stderr(capsys).splitlines() if line.strip()]
    payloads = [json.loads(line) for line in lines]
    by_event = {payload["event"]: payload for payload in payloads}

    native = by_event["native_event"]
    assert native["answer"] == 42
    assert native["level"] == "INFO"
    assert native["logger"] == "tests.logging"
    assert native["correlation_id"] == "req-123"
    assert datetime.fromisoformat(native["timestamp"]).utcoffset() is not None

    foreign = by_event["stdlib_event"]
    assert foreign["level"] == "INFO"
    assert foreign["logger"] == "uvicorn.error"


def test_redacts_secret_in_native_event_text(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Un secreto dentro del mensaje de structlog no llega a la salida."""
    configure_logging(Settings(log_json=True))

    get_logger("tests.logging.native").info("received GET /api/v1/chat?api_key=LEAKME7&x=1")

    output = _captured_stderr(capsys)
    assert "LEAKME7" not in output
    assert REDACTED_VALUE in output


def test_redacts_secret_in_uvicorn_access_record(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """La línea de acceso de uvicorn con query string se sanea."""
    configure_logging(Settings(log_json=True))

    logging.getLogger("uvicorn.access").info(
        '10.0.0.1:5555 - "GET /api/v1/chat?api_key=LEAKME7&x=1 HTTP/1.1" 200'
    )

    output = _captured_stderr(capsys)
    assert "LEAKME7" not in output
    assert REDACTED_VALUE in output


def test_redacts_secret_in_formatted_exception(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """El traceback ya formateado también pasa por el escaneo de texto."""
    configure_logging(Settings(log_json=True))

    try:
        raise RuntimeError("boom sk-LEAKME4ABCD")
    except RuntimeError:
        get_logger("tests.logging.exception").exception("unhandled_error")

    output = _captured_stderr(capsys)
    assert "sk-LEAKME4ABCD" not in output
    assert REDACTED_VALUE in output


def test_redacts_cookie_header_in_stdlib_record(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Una cabecera ``Cookie`` interpolada en un registro stdlib se sanea."""
    configure_logging(Settings(log_json=True))

    logging.getLogger("uvicorn.error").info("headers=%s", {"Cookie": "session=LEAKME6"})

    output = _captured_stderr(capsys)
    assert "LEAKME6" not in output
    assert REDACTED_VALUE in output


def test_preserves_and_redacts_stdlib_extra(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``extra=`` de stdlib se conserva y se redacta por clave."""
    configure_logging(Settings(log_json=True))

    logging.getLogger("uvicorn.error").info(
        "with_extra",
        extra={"authorization": "Bearer LEAKME9"},
    )

    output = _captured_stderr(capsys)
    assert "LEAKME9" not in output
    assert REDACTED_VALUE in output
