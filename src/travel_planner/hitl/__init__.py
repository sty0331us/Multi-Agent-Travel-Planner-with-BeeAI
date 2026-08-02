"""Human-in-the-loop (HITL) gates for production-grade travel planning accuracy.

HITL is not optional ceremony — it is how operators keep specialist handoffs and
final recommendations accountable before they reach a traveler.
"""

from __future__ import annotations

from travel_planner.hitl.coverage import CoverageReport, assess_plan_coverage
from travel_planner.hitl.gates import (
    HANDOFF_TOOL_NAMES,
    ApprovalAuditLog,
    ApprovalDecision,
    confirm_final_plan,
    create_handoff_permission_handler,
)

__all__ = [
    "HANDOFF_TOOL_NAMES",
    "ApprovalAuditLog",
    "ApprovalDecision",
    "CoverageReport",
    "assess_plan_coverage",
    "confirm_final_plan",
    "create_handoff_permission_handler",
]
