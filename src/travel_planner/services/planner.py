"""Travel planning application service."""

from __future__ import annotations

from travel_planner.config import Settings, get_settings
from travel_planner.errors import ValidationError
from travel_planner.llm import create_chat_model
from travel_planner.logging_setup import get_logger
from travel_planner.models import PlanResult
from travel_planner.orchestration import TravelAgentSystem, build_travel_system, run_travel_plan
from travel_planner.validation import sanitize_query

logger = get_logger(__name__)


class TravelPlannerService:
    """
    Production facade: validate → assemble agents → orchestrate → return plan.

    Keeps CLI / REPL thin and concentrates cross-cutting concerns here.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._system: TravelAgentSystem | None = None

    def _ensure_system(self) -> TravelAgentSystem:
        if self._system is None:
            llm = create_chat_model(self.settings)
            self._system = build_travel_system(llm, self.settings)
        return self._system

    async def plan(self, raw_query: str) -> PlanResult:
        """Validate the query and run the multi-agent travel planner."""
        validation = sanitize_query(raw_query, max_chars=self.settings.max_query_chars)
        if not validation.ok:
            raise ValidationError(validation.error or "Invalid query.")

        logger.info("Planning trip for query (%d chars)", len(validation.query))
        system = self._ensure_system()
        return await run_travel_plan(system, validation.query)
