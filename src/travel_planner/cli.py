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

from travel_planner.agents.prompts import DEFAULT_DEMO_QUERY
from travel_planner.config import PROJECT_ROOT, Settings, get_settings
from travel_planner.errors import (
    ConfigurationError,
    OrchestrationError,
    TravelPlannerError,
    ValidationError,
    classify_exception,
)
from travel_planner.logging_setup import get_logger, setup_logging
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


def _print_plan(answer: str, *, latency_ms: float, model: str) -> None:
    console.print()
    console.print(
        Panel(
            Markdown(answer),
            title="Comprehensive Travel Plan",
            subtitle=f"{model} · {latency_ms:.0f} ms",
            border_style="cyan",
        )
    )


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
    except (ValidationError, ConfigurationError, OrchestrationError, TravelPlannerError) as exc:
        _print_error(exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled failure")
        _print_error(exc)
        return 1

    if as_json:
        console.print_json(json.dumps(result.as_dict()))
    else:
        _print_plan(result.answer, latency_ms=result.latency_ms, model=result.model)
    return 0


async def interactive_loop(settings: Settings) -> int:
    """REPL loop for iterative travel planning."""
    console.print(
        Panel(
            "[bold]Multi-Agent Travel Planner[/] (BeeAI)\n"
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
            _print_plan(result.answer, latency_ms=result.latency_ms, model=result.model)
        except (ValidationError, ConfigurationError, OrchestrationError, TravelPlannerError) as exc:
            _print_error(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled failure in REPL")
            _print_error(exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="travel-planner",
        description=(
            "Production multi-agent travel planner using BeeAI RequirementAgents, "
            "HandoffTool orchestration, ReAct (ThinkTool), and resilient error handling."
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
