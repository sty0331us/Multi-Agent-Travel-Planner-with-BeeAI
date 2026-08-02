"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_LLM_MODEL = "watsonx:meta-llama/llama-4-maverick-17b-128e-instruct-fp8"
DEFAULT_EXPECTED_OUTPUT = (
    "Comprehensive travel plan covering destination highlights, weather expectations, "
    "and language/cultural guidance. Formatted as markdown with clear sections."
)


class Settings(BaseSettings):
    """Runtime settings for the multi-agent travel planner."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    llm_model: str = Field(default=DEFAULT_LLM_MODEL, alias="TRAVEL_PLANNER_LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="TRAVEL_PLANNER_LLM_TEMPERATURE")
    log_level: str = Field(default="INFO", alias="TRAVEL_PLANNER_LOG_LEVEL")
    verbose: bool = Field(default=True, alias="TRAVEL_PLANNER_VERBOSE")
    max_query_chars: int = Field(default=2000, alias="TRAVEL_PLANNER_MAX_QUERY_CHARS")
    expected_output: str = Field(
        default=DEFAULT_EXPECTED_OUTPUT,
        alias="TRAVEL_PLANNER_EXPECTED_OUTPUT",
    )
    require_handoff_permission: bool = Field(
        default=False,
        alias="TRAVEL_PLANNER_REQUIRE_HANDOFF_PERMISSION",
    )
    max_retries: int = Field(default=2, ge=0, le=5, alias="TRAVEL_PLANNER_MAX_RETRIES")
    retry_wait_seconds: float = Field(
        default=1.5,
        ge=0.0,
        alias="TRAVEL_PLANNER_RETRY_WAIT_SECONDS",
    )

    # Provider credentials (optional depending on llm_model prefix)
    watsonx_api_key: str | None = Field(default=None, alias="WATSONX_API_KEY")
    watsonx_project_id: str | None = Field(default=None, alias="WATSONX_PROJECT_ID")
    watsonx_url: str | None = Field(default=None, alias="WATSONX_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    @field_validator("llm_temperature")
    @classmethod
    def _clamp_temperature(cls, value: float) -> float:
        return max(0.0, min(2.0, value))

    @property
    def llm_provider(self) -> str:
        """Return the provider prefix from ``provider:model``."""
        if ":" not in self.llm_model:
            return "unknown"
        return self.llm_model.split(":", 1)[0].lower()

    def missing_credentials(self) -> list[str]:
        """Return human-readable names of missing credentials for the active provider."""
        missing: list[str] = []
        provider = self.llm_provider
        if provider == "watsonx":
            if not self.watsonx_api_key:
                missing.append("WATSONX_API_KEY")
            if not self.watsonx_project_id:
                missing.append("WATSONX_PROJECT_ID")
        elif provider == "openai":
            if not self.openai_api_key:
                missing.append("OPENAI_API_KEY")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
