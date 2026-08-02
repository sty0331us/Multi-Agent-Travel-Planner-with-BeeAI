"""Unit tests for validation, errors, and configuration — no live LLM calls."""

from __future__ import annotations

import pytest

from travel_planner.config import Settings, get_settings
from travel_planner.errors import (
    ConfigurationError,
    OrchestrationError,
    ValidationError,
    classify_exception,
)
from travel_planner.validation import sanitize_query


def test_sanitize_rejects_empty() -> None:
    result = sanitize_query("   ")
    assert result.ok is False
    assert result.error is not None


def test_sanitize_rejects_none() -> None:
    result = sanitize_query(None)
    assert result.ok is False


def test_sanitize_strips_control_chars() -> None:
    result = sanitize_query("Plan a trip\x00 to Rome\nplease")
    assert result.ok is True
    assert "\x00" not in result.query
    assert "Rome" in result.query


def test_sanitize_enforces_max_chars() -> None:
    result = sanitize_query("x" * 50, max_chars=20)
    assert result.ok is False
    assert "20" in (result.error or "")


def test_settings_provider_parsing(settings: Settings) -> None:
    assert settings.llm_provider == "watsonx"
    assert settings.missing_credentials() == []


def test_settings_missing_watsonx_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAVEL_PLANNER_LLM_MODEL", "watsonx:ibm/granite-4-h-small")
    monkeypatch.delenv("WATSONX_API_KEY", raising=False)
    monkeypatch.delenv("WATSONX_PROJECT_ID", raising=False)
    # pydantic-settings may still read empty strings from env; force empty
    monkeypatch.setenv("WATSONX_API_KEY", "")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "")
    get_settings.cache_clear()
    s = Settings(
        llm_model="watsonx:ibm/granite-4-h-small",
        watsonx_api_key=None,
        watsonx_project_id=None,
    )
    missing = s.missing_credentials()
    assert "WATSONX_API_KEY" in missing
    assert "WATSONX_PROJECT_ID" in missing


def test_classify_validation_error() -> None:
    report = classify_exception(ValidationError("bad query"))
    assert report.kind == "validation"
    assert report.retryable is False


def test_classify_orchestration_error() -> None:
    report = classify_exception(OrchestrationError("failed", details={"attempts": 3}))
    assert report.kind == "orchestration"
    assert report.retryable is True


def test_classify_framework_like_error() -> None:
    class FakeFrameworkError(Exception):
        def explain(self) -> str:
            return "rate limited"

    report = classify_exception(FakeFrameworkError())
    assert report.kind == "framework"
    assert report.message == "rate limited"
    assert report.retryable is True


def test_configuration_error_explain() -> None:
    err = ConfigurationError("missing keys", details={"missing": "WATSONX_API_KEY"})
    assert "WATSONX_API_KEY" in err.explain()
