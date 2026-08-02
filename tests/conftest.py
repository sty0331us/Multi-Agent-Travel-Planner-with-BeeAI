"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from travel_planner.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv(
        "TRAVEL_PLANNER_LLM_MODEL",
        "watsonx:meta-llama/llama-4-maverick-17b-128e-instruct-fp8",
    )
    monkeypatch.setenv("WATSONX_API_KEY", "test-key")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")
    monkeypatch.setenv("TRAVEL_PLANNER_MAX_RETRIES", "1")
    get_settings.cache_clear()
    return get_settings()
