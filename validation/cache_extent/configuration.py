"""Freeze host-only controls against an already pinned resident campaign."""

import argparse
import json
from pathlib import Path

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from validation.grasu_complete import preparation


def host_control(reference, host, dataset, output):
    prior = json.loads(reference.read_text())
    preparation.unchanged(prior["pins"])
    rows = [row for row in prior["workloads"] if row["dataset"] == dataset]
    if len(rows) != 1 or rows[0]["algorithm"] != "weighted_sssp":
        raise ValueError("one pinned SSSP workload required for the initial host control")
    workload = rows[0]
    paths = [Path(row["path"]) for row in prior["pins"]]
    gr_binary = [path for path in paths if path.suffix == ".xclbin" and "grasu_regraph" in path.name]
    spine_binary = [path for path in paths if path.suffix == ".xclbin" and "spine_" in path.name]
    if len(gr_binary) != 1 or len(spine_binary) != 1:
        raise ValueError("exactly two previously tested bitstreams required")
    config = {"logical": "weighted_sssp", "dataset": dataset,
        "graph": workload["graph"], "source": workload["source"],
        "gr_host": str(host), "gr_binary": str(gr_binary[0]),
        "spine_host": prior["options"]["host"], "spine_binary": str(spine_binary[0]),
        "memory_gib": 16,
        "board_lock": "/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/board-device-one.lock",
        "kernel_variant": "legacy_full_cache",
        "scope": "new_host_old_kernel_control_not_bounded_cache_performance",
        "expected_pins": prior["pins"] + [preparation.pin(reference), preparation.pin(host),
            preparation.pin(host.parent / "manifest.txt"), preparation.pin(Path(__file__))]}
    atomic_write_json(output, config)
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "host", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    host_control(args.reference.resolve(), args.host.resolve(), args.dataset, args.output.resolve())
    print("HOST_CONTROL_CONFIGURED_NOT_BOARD_TESTED")


if __name__ == "__main__":
    main()
