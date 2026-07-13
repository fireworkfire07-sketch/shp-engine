"""Command-line entrypoint.

    python -m photographer_ai.cli run <input_dir> [--output DIR] [--no-body]
        [--no-background-cleanup] [--no-retouch] [--no-shadow]
"""

from __future__ import annotations

import argparse
import sys

from .pipeline import PipelineConfig, run_batch


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="photographer_ai")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the full pipeline on a directory of photos")
    run_p.add_argument("input_dir")
    run_p.add_argument("--output", default="photographer_ai_output")
    run_p.add_argument("--no-body", action="store_true", help="Skip Stage 3 pose analysis")
    run_p.add_argument("--no-background-cleanup", action="store_true", help="Skip Stage 5")
    run_p.add_argument("--no-retouch", action="store_true", help="Skip Stage 8 retouch")
    run_p.add_argument("--no-shadow", action="store_true", help="Skip Stage 11 cinematic shadow")
    run_p.add_argument("--bw-all", action="store_true", help="Generate B&W for every kept image, not just hero shots")

    args = parser.parse_args(argv)

    if args.command == "run":
        config = PipelineConfig(
            output_dir=args.output,
            enable_body_analysis=not args.no_body,
            enable_background_cleanup=not args.no_background_cleanup,
            enable_retouch=not args.no_retouch,
            enable_cinematic_shadow=not args.no_shadow,
            bw_hero_only=not args.bw_all,
            on_progress=lambda msg: print(msg, flush=True),
        )
        result = run_batch(args.input_dir, config)
        print(f"\nDone in {result.elapsed_seconds:.1f}s. Report: {config.output_dir}/report.json")
        for stars in sorted(result.buckets.keys(), reverse=True):
            print(f"  {'*' * stars:<5} {len(result.buckets[stars])} images")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
