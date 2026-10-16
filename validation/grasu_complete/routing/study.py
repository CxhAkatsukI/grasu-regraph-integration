"""Prepare and optionally supervise a bounded production-source G link."""

import argparse
import json
from pathlib import Path

from spine_cycle_sim.experiments.evaluation_impact.common_g.complete_pipeline.hardware.supervisor import run
from .preparation import LINK_TIMEOUTS, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = ("build", "basis", "rtl", "connected", "fit", "config", "output")
    for name in names:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--link-timeout-seconds", type=int, choices=LINK_TIMEOUTS, default=43200)
    args = parser.parse_args()
    prepare(*(getattr(args, name).resolve() for name in names), link_timeout_seconds=args.link_timeout_seconds)
    if args.execute:
        result = run(args.build.resolve(), args.output.resolve())
        print(json.dumps({key: value for key, value in result.items() if key != "resources"}), flush=True)
        return 0 if result["status"] == "LINK_PASS_AWAITING_TIMING_AND_BOARD" else 1
    print("PREPARED_DIAGNOSTIC_LINK_NOT_BASELINE_ADMISSION", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
