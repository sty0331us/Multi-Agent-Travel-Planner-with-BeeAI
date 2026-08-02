"""CLI entrypoint for the Multi-Agent Travel Planner."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from travel_planner.agents.prompts import DEFAULT_DEMO_QUERY
from travel_planner.config import PROJECT_ROOT, Settings, get_settings
from travel_planner.errors import (
    ConfigurationError,
    OrchestrationError,
    PlanRejectedError,
    TravelPlannerError,
    ValidationError,
    classify_exception,
)
from travel_planner.logging_setup import get_logger, setup_logging
from travel_planner.models import PlanResult
from travel_planner.services import TravelPlannerService

console = Console()
logger = get_logger(__name__)


def _ensure_credentials(settings: Settings) -> None:
    missing = settings.missing_credentials()
    if not missing:
        return
    console.print(
        Panel(
            "[bold red]Missing credentials for provider "
            f"[cyan]{settings.llm_provider}[/cyan]:[/]\n"
            + "\n".join(f"  • {name}" for name in missing)
            + "\n\nCopy [cyan].env.example[/] → [cyan].env[/] and fill in values.",
            title="Configuration Error",
            border_style="red",
        )
    )
    sys.exit(1)


def _apply_hitl_flags(settings: Settings, args: argparse.Namespace) -> Settings:
    """Overlay CLI HITL flags onto settings (immutable copy)."""
    updates: dict[str, object] = {}
    if getattr(args, "hitl", False):
        updates["hitl_enabled"] = True
        updates["require_handoff_permission"] = True
    if getattr(args, "no_hitl", False):
        updates["hitl_enabled"] = False
        updates["require_handoff_permission"] = False
        updates["hitl_final_review"] = False
    if getattr(args, "hitl_final_review", False):
        updates["hitl_enabled"] = True
        updates["require_handoff_permission"] = True
        updates["hitl_final_review"] = True
    if not updates:
        return settings
    return settings.model_copy(update=updates)


def _print_plan(result: PlanResult) -> None:
    console.print()
    console.print(
        Panel(
            Markdown(result.answer),
            title="Comprehensive Travel Plan",
            subtitle=f"{result.model} · {result.latency_ms:.0f} ms",
            border_style="cyan",
        )
    )
    coverage = result.metadata.get("coverage")
    if isinstance(coverage, dict):
        missing = coverage.get("missing") or []
        if missing:
            console.print(
                Panel(
                    "Coverage gaps (accuracy signal): "
                    + ", ".join(f"[yellow]{m}[/]" for m in missing)
                    + "\nEnable [cyan]--hitl --hitl-final-review[/] for human acceptance "
                    "before delivering incomplete plans.",
                    title="Plan Coverage",
                    border_style="yellow",
                )
            )
    hitl = result.metadata.get("hitl")
    if isinstance(hitl, dict) and hitl.get("total", 0) > 0:
        table = Table(title="HITL Audit Trail", show_lines=False)
        table.add_column("Tool")
        table.add_column("Allowed")
        table.add_column("Reason")
        for decision in hitl.get("decisions", []):
            table.add_row(
                str(decision.get("tool_name", "")),
                "yes" if decision.get("allowed") else "no",
                str(decision.get("reason", "")),
            )
        console.print(table)


def _print_error(exc: BaseException) -> None:
    report = classify_exception(exc)
    console.print(
        Panel(
            f"[bold red]{report.kind}[/]\n{report.message}",
            title="Travel Planner Error",
            border_style="red",
        )
    )


async def run_once(query: str, settings: Settings, *, as_json: bool = False) -> int:
    """Execute a single planning request."""
    service = TravelPlannerService(settings)
    try:
        result = await service.plan(query)
    except (
        ValidationError,
        ConfigurationError,
        OrchestrationError,
        PlanRejectedError,
        TravelPlannerError,
    ) as exc:
        _print_error(exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled failure")
        _print_error(exc)
        return 1

    if as_json:
        console.print_json(json.dumps(result.as_dict()))
    else:
        _print_plan(result)
    return 0


async def interactive_loop(settings: Settings) -> int:
    """REPL loop for iterative travel planning."""
    hitl_note = (
        "[green]HITL on[/] — handoffs require approval"
        if settings.handoff_permission_enabled
        else "[dim]HITL off[/] — pass [cyan]--hitl[/] for production accuracy gates"
    )
    console.print(
        Panel(
            "[bold]Multi-Agent Travel Planner[/] (BeeAI)\n"
            f"{hitl_note}\n"
            "Type a travel request, or [cyan]demo[/] for the Japan sample.\n"
            "Commands: [cyan]quit[/] / [cyan]exit[/]",
            border_style="cyan",
        )
    )
    service = TravelPlannerService(settings)

    while True:
        try:
            raw = console.input("\n[bold cyan]You>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            return 0

        if not raw:
            continue
        if raw.lower() in {"quit", "exit", "q"}:
            console.print("Goodbye.")
            return 0
        if raw.lower() == "demo":
            raw = DEFAULT_DEMO_QUERY
            console.print(Panel(raw, title="Demo query", border_style="dim"))

        try:
            result = await service.plan(raw)
            _print_plan(result)
        except (
            ValidationError,
            ConfigurationError,
            OrchestrationError,
            PlanRejectedError,
            TravelPlannerError,
        ) as exc:
            _print_error(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled failure in REPL")
            _print_error(exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="travel-planner",
        description=(
            "Production multi-agent travel planner using BeeAI RequirementAgents, "
            "HandoffTool orchestration, ReAct (ThinkTool), HITL accuracy gates, "
            "and resilient error handling."
        ),
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Travel planning request. Omit to enter interactive mode.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the built-in Japan cultural immersion demo query.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the plan result as JSON.",
    )
    parser.add_argument(
        "--hitl",
        action="store_true",
        help="Enable human-in-the-loop approval before specialist handoffs.",
    )
    parser.add_argument(
        "--no-hitl",
        action="store_true",
        help="Disable HITL gates even if enabled in .env.",
    )
    parser.add_argument(
        "--hitl-final-review",
        action="store_true",
        help="Require human acceptance of the synthesized plan (implies --hitl).",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override TRAVEL_PLANNER_LOG_LEVEL (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    # Clear settings cache so .env values are picked up after load_dotenv
    get_settings.cache_clear()
    settings = get_settings()

    parser = build_parser()
    args = parser.parse_args(argv)
    settings = _apply_hitl_flags(settings, args)

    setup_logging(args.log_level or settings.log_level)
    _ensure_credentials(settings)

    if args.demo:
        query = DEFAULT_DEMO_QUERY
        raise SystemExit(asyncio.run(run_once(query, settings, as_json=args.json)))

    if args.query:
        raise SystemExit(asyncio.run(run_once(args.query, settings, as_json=args.json)))

    raise SystemExit(asyncio.run(interactive_loop(settings)))


if __name__ == "__main__":
    main()
