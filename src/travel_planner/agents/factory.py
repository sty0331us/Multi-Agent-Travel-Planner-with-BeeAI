"""Specialized RequirementAgent factories for the travel planner."""

from __future__ import annotations

from beeai_framework.agents.requirement import RequirementAgent
from beeai_framework.agents.requirement.requirements.ask_permission import AskPermissionRequirement
from beeai_framework.agents.requirement.requirements.conditional import ConditionalRequirement
from beeai_framework.backend import ChatModel
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware
from beeai_framework.tools import Tool
from beeai_framework.tools.handoff import HandoffTool
from beeai_framework.tools.search.wikipedia import WikipediaTool
from beeai_framework.tools.think import ThinkTool
from beeai_framework.tools.weather import OpenMeteoTool

from travel_planner.agents import prompts
from travel_planner.config import Settings
from travel_planner.hitl import (
    HANDOFF_TOOL_NAMES,
    ApprovalAuditLog,
    create_handoff_permission_handler,
)


def _trajectory_middleware() -> GlobalTrajectoryMiddleware:
    return GlobalTrajectoryMiddleware(included=[Tool])


def build_destination_expert(llm: ChatModel) -> RequirementAgent:
    """Destination research specialist — Wikipedia + Think (ReAct)."""
    return RequirementAgent(
        name="DestinationExpert",
        description="Specialist in landmarks, attractions, transport, and destination safety.",
        llm=llm,
        tools=[WikipediaTool(), ThinkTool()],
        memory=UnconstrainedMemory(),
        role="Destination Research Expert",
        instructions=prompts.DESTINATION_EXPERT_INSTRUCTIONS,
        middlewares=[_trajectory_middleware()],
        requirements=[
            # ReAct: force Reason (Think) before Act (Wikipedia)
            ConditionalRequirement(
                ThinkTool,
                force_at_step=1,
                min_invocations=1,
                max_invocations=5,
                consecutive_allowed=False,
            ),
            ConditionalRequirement(
                WikipediaTool,
                only_after=[ThinkTool],
                min_invocations=1,
                max_invocations=4,
                consecutive_allowed=False,
            ),
        ],
    )


def build_travel_meteorologist(llm: ChatModel) -> RequirementAgent:
    """Weather specialist — OpenMeteo + Think (ReAct)."""
    return RequirementAgent(
        name="TravelMeteorologist",
        description="Specialist in climate analysis and travel weather guidance.",
        llm=llm,
        tools=[OpenMeteoTool(), ThinkTool()],
        memory=UnconstrainedMemory(),
        role="Travel Meteorologist",
        instructions=prompts.TRAVEL_METEOROLOGIST_INSTRUCTIONS,
        middlewares=[_trajectory_middleware()],
        requirements=[
            ConditionalRequirement(
                ThinkTool,
                force_at_step=1,
                min_invocations=1,
                max_invocations=2,
            ),
            ConditionalRequirement(
                OpenMeteoTool,
                only_after=[ThinkTool],
                min_invocations=1,
                max_invocations=1,
            ),
        ],
    )


def build_language_culture_expert(llm: ChatModel) -> RequirementAgent:
    """Language & culture specialist — Wikipedia + Think (ReAct)."""
    return RequirementAgent(
        name="LanguageCultureExpert",
        description="Specialist in languages, etiquette, and cultural guidance for travelers.",
        llm=llm,
        tools=[WikipediaTool(), ThinkTool()],
        memory=UnconstrainedMemory(),
        role="Language & Cultural Expert",
        instructions=prompts.LANGUAGE_CULTURE_EXPERT_INSTRUCTIONS,
        middlewares=[_trajectory_middleware()],
        requirements=[
            ConditionalRequirement(
                ThinkTool,
                force_at_step=1,
                min_invocations=1,
                max_invocations=3,
                consecutive_allowed=False,
            ),
        ],
    )


def build_travel_coordinator(
    llm: ChatModel,
    *,
    destination_expert: RequirementAgent,
    travel_meteorologist: RequirementAgent,
    language_culture_expert: RequirementAgent,
    settings: Settings,
    audit_log: ApprovalAuditLog | None = None,
) -> RequirementAgent:
    """
    Main orchestrator agent.

    Uses ``HandoffTool`` instances for multi-agent orchestration and
    ``ThinkTool`` + ``ConditionalRequirement`` to enforce ReAct discipline.
    When HITL is enabled, ``AskPermissionRequirement`` gates each specialist
    handoff so a human can protect real-world plan accuracy.
    """
    handoff_to_destination = HandoffTool(
        destination_expert,
        name="DestinationResearch",
        description=prompts.HANDOFF_DESTINATION_DESCRIPTION,
    )
    handoff_to_weather = HandoffTool(
        travel_meteorologist,
        name="WeatherPlanning",
        description=prompts.HANDOFF_WEATHER_DESCRIPTION,
    )
    handoff_to_language = HandoffTool(
        language_culture_expert,
        name="LanguageCulturalGuidance",
        description=prompts.HANDOFF_LANGUAGE_DESCRIPTION,
    )

    requirements: list[object] = [
        ConditionalRequirement(ThinkTool, consecutive_allowed=False),
    ]
    if settings.handoff_permission_enabled:
        audit = audit_log or ApprovalAuditLog()
        requirements.append(
            AskPermissionRequirement(
                list(HANDOFF_TOOL_NAMES),
                handler=create_handoff_permission_handler(audit),
                remember_choices=settings.hitl_remember_choices,
            )
        )

    return RequirementAgent(
        name="TravelCoordinator",
        description="Main travel planning coordinator that synthesizes specialist guidance.",
        llm=llm,
        tools=[
            handoff_to_destination,
            handoff_to_weather,
            handoff_to_language,
            ThinkTool(),
        ],
        memory=UnconstrainedMemory(),
        role="Travel Coordinator",
        instructions=prompts.TRAVEL_COORDINATOR_INSTRUCTIONS,
        middlewares=[_trajectory_middleware()],
        requirements=requirements,  # type: ignore[arg-type]
        notes=[
            "If the traveler does not provide a destination, ask for clarification "
            "before handing off to specialists.",
            "Prefer consulting all three specialists for multi-week cultural immersion trips.",
            "When HITL is enabled, wait for human approval before each specialist handoff.",
        ],
    )
