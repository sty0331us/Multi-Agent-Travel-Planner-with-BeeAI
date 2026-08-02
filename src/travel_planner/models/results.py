"""Result models for travel planning runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PlanResult:
    """Successful travel plan output from the coordinator."""

    answer: str
    query: str
    latency_ms: float
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "query": self.query,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "metadata": self.metadata,
        }
