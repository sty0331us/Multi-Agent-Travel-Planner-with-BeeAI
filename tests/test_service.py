"""Service-layer tests with mocked orchestration (no live LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_planner.config import Settings
from travel_planner.errors import ValidationError
from travel_planner.models import PlanResult
from travel_planner.services import TravelPlannerService


@pytest.mark.asyncio
async def test_service_rejects_invalid_query(settings: Settings) -> None:
    service = TravelPlannerService(settings)
    with pytest.raises(ValidationError):
        await service.plan("   ")


@pytest.mark.asyncio
async def test_service_plans_with_mocked_system(settings: Settings) -> None:
    fake_result = PlanResult(
        answer="## Plan\nVisit Kyoto temples.",
        query="Trip to Kyoto",
        latency_ms=12.0,
        model=settings.llm_model,
        metadata={"attempts": 1},
    )
    fake_system = MagicMock()

    with (
        patch(
            "travel_planner.services.planner.create_chat_model",
            return_value=MagicMock(),
        ),
        patch(
            "travel_planner.services.planner.build_travel_system",
            return_value=fake_system,
        ),
        patch(
            "travel_planner.services.planner.run_travel_plan",
            new_callable=AsyncMock,
            return_value=fake_result,
        ) as run_mock,
    ):
        service = TravelPlannerService(settings)
        result = await service.plan("Trip to Kyoto")

    assert result.answer.startswith("## Plan")
    run_mock.assert_awaited_once()
    assert run_mock.await_args.args[1] == "Trip to Kyoto"
