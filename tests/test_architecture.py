"""Architecture tests — agent wiring, ReAct profiles, orchestration shape."""

from __future__ import annotations

from unittest.mock import MagicMock

from travel_planner.config import Settings
from travel_planner.orchestration.react import (
    COORDINATOR_REACT,
    DESTINATION_REACT,
    LANGUAGE_REACT,
    METEOROLOGIST_REACT,
    ReActPhase,
    all_react_profiles,
)
from travel_planner.orchestration.system import build_travel_system


def test_react_profiles_cover_all_roles() -> None:
    profiles = all_react_profiles()
    assert set(profiles) == {
        "destination_expert",
        "travel_meteorologist",
        "language_culture_expert",
        "travel_coordinator",
    }


def test_destination_react_forces_think_before_wikipedia() -> None:
    reason = DESTINATION_REACT[0]
    act = DESTINATION_REACT[1]
    assert reason.phase is ReActPhase.REASON
    assert reason.tool == "ThinkTool"
    assert reason.force_at_step == 1
    assert act.phase is ReActPhase.ACT
    assert act.tool == "WikipediaTool"
    assert act.only_after == ("ThinkTool",)


def test_meteorologist_react_open_meteo_after_think() -> None:
    act = METEOROLOGIST_REACT[1]
    assert act.tool == "OpenMeteoTool"
    assert act.only_after == ("ThinkTool",)
    assert act.max_invocations == 1


def test_language_react_requires_think() -> None:
    assert LANGUAGE_REACT[0].tool == "ThinkTool"
    assert LANGUAGE_REACT[0].force_at_step == 1


def test_coordinator_react_includes_handoff_act() -> None:
    tools = {c.tool for c in COORDINATOR_REACT}
    assert "ThinkTool" in tools
    assert "HandoffTool" in tools


def test_react_constraint_summary_is_readable() -> None:
    summary = DESTINATION_REACT[0].summary()
    assert "reason:ThinkTool" in summary
    assert "force_at_step=1" in summary


def test_build_travel_system_wires_handoffs(settings: Settings) -> None:
    system = build_travel_system(MagicMock(), settings)
    tools = {role: [name.lower() for name in names] for role, names in system.tool_names().items()}
    assert "destinationresearch" in tools["travel_coordinator"]
    assert "weatherplanning" in tools["travel_coordinator"]
    assert "languageculturalguidance" in tools["travel_coordinator"]
    assert any("wikipedia" in name for name in tools["destination_expert"])
    assert any("openmeteo" in name or "weather" in name for name in tools["travel_meteorologist"])
    assert len(system.specialists) == 3
