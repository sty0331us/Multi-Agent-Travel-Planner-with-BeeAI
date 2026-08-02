"""
ReAct (Reason + Act) execution model for BeeAI RequirementAgents.

This module documents how ReAct is enforced in this project via
``ThinkTool`` + ``ConditionalRequirement``, and provides small helpers
used by orchestration and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReActPhase(StrEnum):
    """Canonical phases of a ReAct step."""

    REASON = "reason"  # ThinkTool — plan, decompose, decide next action
    ACT = "act"  # Domain tools / HandoffTool — gather evidence
    OBSERVE = "observe"  # Incorporate tool results into working memory
    ANSWER = "answer"  # Final synthesized response


@dataclass(frozen=True, slots=True)
class ReActConstraint:
    """Declarative description of a ReAct constraint enforced by RequirementAgent."""

    tool: str
    phase: ReActPhase
    force_at_step: int | None = None
    only_after: tuple[str, ...] = ()
    min_invocations: int | None = None
    max_invocations: int | None = None
    consecutive_allowed: bool | None = None

    def summary(self) -> str:
        parts = [f"{self.phase.value}:{self.tool}"]
        if self.force_at_step is not None:
            parts.append(f"force_at_step={self.force_at_step}")
        if self.only_after:
            parts.append(f"only_after={list(self.only_after)}")
        if self.min_invocations is not None:
            parts.append(f"min={self.min_invocations}")
        if self.max_invocations is not None:
            parts.append(f"max={self.max_invocations}")
        if self.consecutive_allowed is not None:
            parts.append(f"consecutive={self.consecutive_allowed}")
        return " | ".join(parts)


# Documented constraints mirroring agents/factory.py — used by architecture tests
# and README diagrams so code and docs stay aligned.
DESTINATION_REACT: tuple[ReActConstraint, ...] = (
    ReActConstraint(
        tool="ThinkTool",
        phase=ReActPhase.REASON,
        force_at_step=1,
        min_invocations=1,
        max_invocations=5,
        consecutive_allowed=False,
    ),
    ReActConstraint(
        tool="WikipediaTool",
        phase=ReActPhase.ACT,
        only_after=("ThinkTool",),
        min_invocations=1,
        max_invocations=4,
        consecutive_allowed=False,
    ),
)

METEOROLOGIST_REACT: tuple[ReActConstraint, ...] = (
    ReActConstraint(
        tool="ThinkTool",
        phase=ReActPhase.REASON,
        force_at_step=1,
        min_invocations=1,
        max_invocations=2,
    ),
    ReActConstraint(
        tool="OpenMeteoTool",
        phase=ReActPhase.ACT,
        only_after=("ThinkTool",),
        min_invocations=1,
        max_invocations=1,
    ),
)

LANGUAGE_REACT: tuple[ReActConstraint, ...] = (
    ReActConstraint(
        tool="ThinkTool",
        phase=ReActPhase.REASON,
        force_at_step=1,
        min_invocations=1,
        max_invocations=3,
        consecutive_allowed=False,
    ),
)

COORDINATOR_REACT: tuple[ReActConstraint, ...] = (
    ReActConstraint(
        tool="ThinkTool",
        phase=ReActPhase.REASON,
        consecutive_allowed=False,
    ),
    ReActConstraint(
        tool="HandoffTool",
        phase=ReActPhase.ACT,
    ),
)


def all_react_profiles() -> dict[str, tuple[ReActConstraint, ...]]:
    """Return named ReAct profiles for each agent role."""
    return {
        "destination_expert": DESTINATION_REACT,
        "travel_meteorologist": METEOROLOGIST_REACT,
        "language_culture_expert": LANGUAGE_REACT,
        "travel_coordinator": COORDINATOR_REACT,
    }
