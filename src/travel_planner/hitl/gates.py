"""Interactive HITL gates and approval audit trail."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from beeai_framework.tools import AnyTool
from rich.console import Console
from rich.panel import Panel

from travel_planner.logging_setup import get_logger

logger = get_logger(__name__)
_console = Console(stderr=True)

HANDOFF_TOOL_NAMES: tuple[str, ...] = (
    "DestinationResearch",
    "WeatherPlanning",
    "LanguageCulturalGuidance",
)


@dataclass(slots=True)
class ApprovalDecision:
    """One human approval or denial for a tool / handoff."""

    tool_name: str
    allowed: bool
    reason: str
    decided_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    input_preview: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ApprovalAuditLog:
    """In-memory audit trail of HITL decisions for a planning session."""

    def __init__(self) -> None:
        self._decisions: list[ApprovalDecision] = []

    def record(self, decision: ApprovalDecision) -> None:
        self._decisions.append(decision)
        logger.info(
            "HITL decision tool=%s allowed=%s reason=%s",
            decision.tool_name,
            decision.allowed,
            decision.reason,
        )

    @property
    def decisions(self) -> list[ApprovalDecision]:
        return list(self._decisions)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [d.as_dict() for d in self._decisions]

    def summary(self) -> dict[str, Any]:
        allowed = sum(1 for d in self._decisions if d.allowed)
        denied = sum(1 for d in self._decisions if not d.allowed)
        return {
            "total": len(self._decisions),
            "allowed": allowed,
            "denied": denied,
            "decisions": self.as_dicts(),
        }

    def clear(self) -> None:
        self._decisions.clear()


def _preview_input(payload: dict[str, Any], *, limit: int = 240) -> str:
    text = str(payload)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def create_handoff_permission_handler(
    audit: ApprovalAuditLog,
    *,
    console: Console | None = None,
):
    """
    Build an ``AskPermissionRequirement`` handler that prompts the operator
    and records every decision in ``audit``.
    """
    out = console or _console

    async def handler(tool: AnyTool, tool_input: dict[str, Any]) -> bool:
        preview = _preview_input(tool_input)
        out.print(
            Panel(
                f"[bold]HITL gate[/] — specialist handoff requires human approval\n\n"
                f"[cyan]Tool:[/] {tool.name}\n"
                f"[cyan]Input:[/] {preview}\n\n"
                "Approve only if this specialist call improves plan accuracy "
                "for the traveler's request.",
                title="Human-in-the-Loop",
                border_style="yellow",
            )
        )
        answer = out.input("[bold yellow]Allow this handoff?[/] [y/N] ").strip().lower()
        allowed = answer in {"y", "yes"}
        audit.record(
            ApprovalDecision(
                tool_name=str(tool.name),
                allowed=allowed,
                reason="operator_prompt",
                input_preview=preview,
            )
        )
        if not allowed:
            out.print("[dim]Handoff denied — coordinator will continue without it.[/]")
        return allowed

    return handler


async def confirm_final_plan(
    plan_text: str,
    audit: ApprovalAuditLog,
    *,
    console: Console | None = None,
) -> bool:
    """
    Second HITL gate: human accepts or rejects the synthesized travel plan.

    Improves production accuracy by catching incomplete or unsafe advice
    after specialists have been consulted.
    """
    out = console or _console
    preview = plan_text if len(plan_text) <= 600 else plan_text[:597] + "..."
    out.print(
        Panel(
            "[bold]HITL final review[/] — accept this plan for the traveler?\n\n"
            f"{preview}",
            title="Plan Accuracy Gate",
            border_style="yellow",
        )
    )
    answer = out.input("[bold yellow]Accept final plan?[/] [y/N] ").strip().lower()
    allowed = answer in {"y", "yes"}
    audit.record(
        ApprovalDecision(
            tool_name="FinalPlanReview",
            allowed=allowed,
            reason="final_plan_review",
            input_preview=preview[:240],
        )
    )
    return allowed
