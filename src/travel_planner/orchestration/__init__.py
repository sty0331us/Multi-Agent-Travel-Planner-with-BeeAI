"""Orchestration package — multi-agent wiring, ReAct profiles, resilient runs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from travel_planner.orchestration.react import (
    COORDINATOR_REACT,
    DESTINATION_REACT,
    LANGUAGE_REACT,
    METEOROLOGIST_REACT,
    ReActConstraint,
    ReActPhase,
    all_react_profiles,
)

if TYPE_CHECKING:
    from travel_planner.orchestration.system import (
        TravelAgentSystem,
        build_travel_system,
        run_travel_plan,
    )

__all__ = [
    "COORDINATOR_REACT",
    "DESTINATION_REACT",
    "LANGUAGE_REACT",
    "METEOROLOGIST_REACT",
    "ReActConstraint",
    "ReActPhase",
    "TravelAgentSystem",
    "all_react_profiles",
    "build_travel_system",
    "run_travel_plan",
]


def __getattr__(name: str) -> Any:
    """Lazily import BeeAI-heavy symbols so ReAct docs/tests stay lightweight."""
    if name in {"TravelAgentSystem", "build_travel_system", "run_travel_plan"}:
        from travel_planner.orchestration import system as _system

        return getattr(_system, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
