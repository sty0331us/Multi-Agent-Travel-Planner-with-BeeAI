"""Heuristics that flag incomplete travel plans for HITL / accuracy review."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Lightweight keyword signals for the three specialist domains
_DESTINATION_SIGNALS = (
    "landmark",
    "attraction",
    "temple",
    "museum",
    "transport",
    "neighborhood",
    "district",
    "itinerary",
    "site",
)
_WEATHER_SIGNALS = (
    "weather",
    "temperature",
    "forecast",
    "rain",
    "climate",
    "packing",
    "humidity",
    "season",
)
_CULTURE_SIGNALS = (
    "etiquette",
    "phrase",
    "language",
    "custom",
    "culture",
    "respect",
    "bow",
    "tipping",
    "greeting",
)


@dataclass(slots=True)
class CoverageReport:
    """Whether a synthesized plan appears to cover each specialist domain."""

    destination: bool
    weather: bool
    culture: bool

    @property
    def complete(self) -> bool:
        return self.destination and self.weather and self.culture

    @property
    def missing(self) -> list[str]:
        gaps: list[str] = []
        if not self.destination:
            gaps.append("destination")
        if not self.weather:
            gaps.append("weather")
        if not self.culture:
            gaps.append("culture")
        return gaps

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["complete"] = self.complete
        payload["missing"] = self.missing
        return payload


def _mentions(text: str, signals: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in signals)


def assess_plan_coverage(plan_text: str) -> CoverageReport:
    """
    Estimate whether the final answer covers destination, weather, and culture.

    Used to warn operators and feed HITL final review — not a hard correctness
    proof, but a production accuracy signal before traveler delivery.
    """
    return CoverageReport(
        destination=_mentions(plan_text, _DESTINATION_SIGNALS),
        weather=_mentions(plan_text, _WEATHER_SIGNALS),
        culture=_mentions(plan_text, _CULTURE_SIGNALS),
    )
