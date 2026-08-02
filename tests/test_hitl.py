"""HITL audit trail and plan coverage unit tests."""

from __future__ import annotations

from travel_planner.config import Settings
from travel_planner.errors import PlanRejectedError, classify_exception
from travel_planner.hitl import ApprovalAuditLog, ApprovalDecision, assess_plan_coverage


def test_audit_log_summary() -> None:
    audit = ApprovalAuditLog()
    audit.record(
        ApprovalDecision(tool_name="DestinationResearch", allowed=True, reason="operator_prompt")
    )
    audit.record(
        ApprovalDecision(tool_name="WeatherPlanning", allowed=False, reason="operator_prompt")
    )
    summary = audit.summary()
    assert summary["total"] == 2
    assert summary["allowed"] == 1
    assert summary["denied"] == 1


def test_coverage_detects_complete_plan() -> None:
    plan = (
        "Visit historic landmarks and the museum district. "
        "Weather forecast shows mild temperatures — pack layers. "
        "Learn basic phrases and follow local etiquette respectfully."
    )
    report = assess_plan_coverage(plan)
    assert report.complete is True
    assert report.missing == []


def test_coverage_detects_gaps() -> None:
    report = assess_plan_coverage("Just go to Tokyo and have fun.")
    assert report.complete is False
    assert "weather" in report.missing
    assert "culture" in report.missing


def test_settings_hitl_helpers() -> None:
    s = Settings(hitl_enabled=True, hitl_final_review=True, require_handoff_permission=False)
    assert s.handoff_permission_enabled is True
    assert s.final_review_enabled is True


def test_classify_plan_rejected() -> None:
    report = classify_exception(PlanRejectedError("rejected by operator"))
    assert report.kind == "hitl_rejected"
    assert report.retryable is False
