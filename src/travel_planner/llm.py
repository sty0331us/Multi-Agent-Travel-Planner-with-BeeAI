"""LLM factory for BeeAI ChatModel backends."""

from __future__ import annotations

from beeai_framework.backend import ChatModel, ChatModelParameters

from travel_planner.config import Settings
from travel_planner.errors import ConfigurationError
from travel_planner.logging_setup import get_logger

logger = get_logger(__name__)


def create_chat_model(settings: Settings) -> ChatModel:
    """
    Build a BeeAI ``ChatModel`` from settings.

    Uses ``ChatModel.from_name`` so providers are swapable via env
    (``watsonx:...``, ``ollama:...``, ``openai:...``, etc.).
    """
    missing = settings.missing_credentials()
    if missing:
        raise ConfigurationError(
            "Missing credentials for the configured LLM provider.",
            details={"provider": settings.llm_provider, "missing": ", ".join(missing)},
        )

    logger.info(
        "Initializing ChatModel provider=%s model=%s temperature=%.2f",
        settings.llm_provider,
        settings.llm_model,
        settings.llm_temperature,
    )
    return ChatModel.from_name(
        settings.llm_model,
        ChatModelParameters(temperature=settings.llm_temperature),
    )
