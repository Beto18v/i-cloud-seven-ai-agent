"""Pruebas de comportamiento de la configuración central."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.core.config import AIProvider, Environment, Settings, get_settings, reset_settings_cache

#: Valor inyectado por la fixture para la credencial simulada.
EXPECTED_FAKE_CREDENTIAL = "sk-test-not-real"


def test_openai_provider_uses_public_base_url(settings: Settings) -> None:
    """El proveedor OpenAI directo usa la URL pública y el modelo de chat."""
    assert settings.ai_provider is AIProvider.OPENAI
    assert settings.is_azure is False
    assert settings.llm_base_url == "https://api.openai.com/v1"
    assert settings.chat_model_name == settings.openai_model_name
    assert settings.llm_api_key is settings.openai_api_key


def test_azure_provider_switch_changes_base_url_and_models(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    """Conmutar a Azure cambia la URL base y resuelve los deployments."""
    assert settings.is_azure is False

    monkeypatch.setenv("AI_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "az-test-not-real")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example-resource.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5-mini-deployment")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embeddings-deployment")
    reset_settings_cache()

    azure = get_settings()

    assert azure.ai_provider is AIProvider.AZURE_OPENAI
    assert azure.is_azure is True
    assert azure.llm_base_url == "https://example-resource.openai.azure.com/openai/v1"
    assert azure.chat_model_name == "gpt-5-mini-deployment"
    assert azure.embedding_model_name_effective == "embeddings-deployment"


def test_secret_str_never_leaks_its_value(settings: Settings) -> None:
    """``SecretStr`` enmascara el valor en ``str``, ``repr`` y serialización."""
    secret = settings.openai_api_key
    assert secret is not None
    assert secret.get_secret_value() == EXPECTED_FAKE_CREDENTIAL
    assert EXPECTED_FAKE_CREDENTIAL not in str(secret)
    assert EXPECTED_FAKE_CREDENTIAL not in repr(secret)
    assert EXPECTED_FAKE_CREDENTIAL not in str(settings)


def test_redacted_summary_contains_no_secret(settings: Settings) -> None:
    """El resumen de arranque solo indica si la credencial está configurada."""
    summary = settings.redacted_summary()
    serialized = json.dumps(summary, default=str)

    assert summary["openai_api_key_configured"] is True
    assert EXPECTED_FAKE_CREDENTIAL not in serialized
    assert "sk-" not in serialized


def test_cors_origins_list_is_normalized(settings: Settings) -> None:
    """La lista CORS recorta espacios y descarta entradas vacías."""
    parsed = Settings(cors_origins="https://a.example.com, https://b.example.com ,")

    assert parsed.cors_origins_list == [
        "https://a.example.com",
        "https://b.example.com",
    ]
    assert settings.cors_origins_list == [
        "http://localhost:3000",
        "https://client.example.com",
    ]


def test_invalid_cors_origin_is_rejected(settings: Settings) -> None:
    """Un origen sin esquema http/https no supera la validación."""
    assert settings.cors_origins_list
    with pytest.raises(ValidationError):
        Settings(cors_origins="ftp://invalid.example.com")


def test_openai_provider_requires_api_key_outside_testing(settings: Settings) -> None:
    """OpenAI directo exige credencial cuando no se ejecuta en testing."""
    assert settings.environment is Environment.TESTING
    with pytest.raises(ValidationError):
        Settings(
            ai_provider="openai",
            environment=Environment.PRODUCTION,
            openai_api_key=None,
        )
