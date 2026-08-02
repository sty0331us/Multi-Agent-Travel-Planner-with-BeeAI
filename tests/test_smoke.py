"""Smoke tests that keep CI green from the first commit."""

from __future__ import annotations

import travel_planner


def test_package_version_exposed() -> None:
    assert travel_planner.__version__

