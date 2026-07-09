from __future__ import annotations

import argparse
import json

from rich.console import Console

from .health import health_as_dict
from .pipeline import run_pipeline

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="SHP Engine command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="Check whether the system is safe to test")

    run_parser = subparsers.add_parser("run", help="Create a safe dry-run video job")
    run_parser.add_argument("topic", help="Video topic, for example: mycelium")

    args = parser.parse_args()

    if args.command == "health":
        console.print_json(json.dumps(health_as_dict(), ensure_ascii=False))
        return

    if args.command == "run":
        result = run_pipeline(args.topic)
        console.print_json(json.dumps(result, default=lambda value: value.__dict__, ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
