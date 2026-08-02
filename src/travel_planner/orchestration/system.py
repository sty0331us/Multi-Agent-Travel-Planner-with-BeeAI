"""Multi-agent system assembly and resilient run loop."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from beeai_framework.agents.requirement import RequirementAgent
from beeai_framework.backend import ChatModel
from beeai_framework.errors import FrameworkError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from travel_planner.agents import (
    build_destination_expert,
    build_language_culture_expert,
    build_travel_coordinator,
    build_travel_meteorologist,
)
from travel_planner.config import Settings
from travel_planner.errors import OrchestrationError, classify_exception
from travel_planner.logging_setup import get_logger
from travel_planner.models import PlanResult

logger = get_logger(__name__)


@dataclass(slots=True)
class TravelAgentSystem:
    """Wired multi-agent travel planning system."""

    llm: ChatModel
    destination_expert: RequirementAgent
    travel_meteorologist: RequirementAgent
    language_culture_expert: RequirementAgent
    travel_coordinator: RequirementAgent
    settings: Settings

    @property
    def specialists(self) -> dict[str, RequirementAgent]:
        return {
            "destination_expert": self.destination_expert,
            "travel_meteorologist": self.travel_meteorologist,
            "language_culture_expert": self.language_culture_expert,
        }

    def tool_names(self) -> dict[str, list[str]]:
        """Return tool names per agent for architecture introspection / tests."""

        def _names(agent: RequirementAgent) -> list[str]:
            tools = getattr(agent, "_tools", None)
            if not tools:
                meta = getattr(agent, "meta", None)
                tools = getattr(meta, "tools", None) if meta is not None else None
            tools = tools or []
            result: list[str] = []
            for tool in tools:
                name = getattr(tool, "name", None) or type(tool).__name__
                result.append(str(name))
            return result

        return {
            "destination_expert": _names(self.destination_expert),
            "travel_meteorologist": _names(self.travel_meteorologist),
            "language_culture_expert": _names(self.language_culture_expert),
            "travel_coordinator": _names(self.travel_coordinator),
        }


def build_travel_system(llm: ChatModel, settings: Settings) -> TravelAgentSystem:
    """Assemble specialists and the coordinator with handoff tools."""
    destination = build_destination_expert(llm)
    meteorologist = build_travel_meteorologist(llm)
    language = build_language_culture_expert(llm)
    coordinator = build_travel_coordinator(
        llm,
        destination_expert=destination,
        travel_meteorologist=meteorologist,
        language_culture_expert=language,
        settings=settings,
    )
    logger.info(
        "Travel agent system assembled (handoff_permission=%s)",
        settings.require_handoff_permission,
    )
    return TravelAgentSystem(
        llm=llm,
        destination_expert=destination,
        travel_meteorologist=meteorologist,
        language_culture_expert=language,
        travel_coordinator=coordinator,
        settings=settings,
    )


def _extract_answer(response: Any) -> str:
    """Best-effort extraction of the final answer text across BeeAI response shapes."""
    last_message = getattr(response, "last_message", None)
    if last_message is not None:
        text = getattr(last_message, "text", None)
        if text:
            return str(text)

    answer = getattr(response, "answer", None)
    if answer is not None:
        text = getattr(answer, "text", None)
        if text:
            return str(text)
        if isinstance(answer, str):
            return answer

    return str(response)


async def run_travel_plan(
    system: TravelAgentSystem,
    query: str,
    *,
    expected_output: str | None = None,
) -> PlanResult:
    """
    Execute the coordinator with retries and structured error handling.

    Retries transient ``FrameworkError`` failures using exponential backoff.
    Non-retryable domain errors propagate immediately.
    """
    settings = system.settings
    output_spec = expected_output or settings.expected_output
    attempts = settings.max_retries + 1
    started = time.perf_counter()
    last_error: BaseException | None = None

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(
                multiplier=settings.retry_wait_seconds,
                min=settings.retry_wait_seconds,
                max=10.0,
            ),
            retry=retry_if_exception_type(FrameworkError),
            reraise=True,
        ):
            with attempt:
                attempt_n = attempt.retry_state.attempt_number
                logger.info("Coordinator run attempt=%s", attempt_n)
                response = await system.travel_coordinator.run(
                    query,
                    expected_output=output_spec,
                )
                answer = _extract_answer(response)
                latency_ms = (time.perf_counter() - started) * 1000.0
                logger.info("Travel plan completed in %.0f ms", latency_ms)
                return PlanResult(
                    answer=answer,
                    query=query,
                    latency_ms=latency_ms,
                    model=settings.llm_model,
                    metadata={"attempts": attempt_n},
                )
    except FrameworkError as exc:
        last_error = exc
        report = classify_exception(exc)
        logger.error("Framework failure after retries: %s", report.message)
        raise OrchestrationError(
            "Travel planning failed after retries.",
            details=report.as_dict(),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        last_error = exc
        report = classify_exception(exc)
        logger.exception("Unexpected orchestration failure: %s", report.message)
        raise OrchestrationError(
            "Unexpected failure during travel planning.",
            details=report.as_dict(),
        ) from exc
    finally:
        if last_error is not None:
            logger.debug("Last orchestration error: %s", last_error)

    # Defensive — AsyncRetrying with reraise should never reach here.
    raise OrchestrationError("Travel planning aborted without a result.")
