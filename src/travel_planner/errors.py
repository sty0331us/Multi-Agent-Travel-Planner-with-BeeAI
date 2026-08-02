"""Domain and framework error helpers for production-grade failure handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TravelPlannerError(Exception):
    """Base error for the travel planner application."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def explain(self) -> str:
        """Return a user-facing explanation."""
        if not self.details:
            return self.message
        detail_str = "; ".join(f"{k}={v}" for k, v in self.details.items())
        return f"{self.message} ({detail_str})"


class ConfigurationError(TravelPlannerError):
    """Raised when required configuration or credentials are missing."""


class ValidationError(TravelPlannerError):
    """Raised when a traveler query fails validation."""


class OrchestrationError(TravelPlannerError):
    """Raised when multi-agent coordination fails after retries."""


@dataclass(slots=True, frozen=True)
class ErrorReport:
    """Structured error payload suitable for CLI and logging."""

    kind: str
    message: str
    retryable: bool = False
    cause: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "retryable": self.retryable,
            "cause": self.cause,
        }


def classify_exception(exc: BaseException) -> ErrorReport:
    """
    Map an exception to a structured, user-safe error report.

    Prefers BeeAI ``FrameworkError.explain()`` when available.
    """
    if isinstance(exc, ValidationError):
        return ErrorReport(kind="validation", message=exc.explain(), retryable=False)
    if isinstance(exc, ConfigurationError):
        return ErrorReport(kind="configuration", message=exc.explain(), retryable=False)
    if isinstance(exc, OrchestrationError):
        return ErrorReport(
            kind="orchestration",
            message=exc.explain(),
            retryable=True,
            cause=str(exc.__cause__) if exc.__cause__ else None,
        )

    # BeeAI FrameworkError duck-typing (avoid hard import dependency in tests)
    explain = getattr(exc, "explain", None)
    if callable(explain):
        try:
            message = str(explain())
        except Exception:  # noqa: BLE001 - defensive fallback
            message = str(exc)
        return ErrorReport(
            kind="framework",
            message=message,
            retryable=True,
            cause=type(exc).__name__,
        )

    return ErrorReport(
        kind="unexpected",
        message=str(exc) or type(exc).__name__,
        retryable=False,
        cause=type(exc).__name__,
    )
