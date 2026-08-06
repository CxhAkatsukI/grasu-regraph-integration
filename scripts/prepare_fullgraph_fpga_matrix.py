#!/usr/bin/env python3
"""Bind admitted full-graph workloads to routed hosts and xclbins."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ALGORITHMS = (
    "weighted_sssp",
    "connected_components",
    "residual_pagerank",
)

HOST_BASENAMES = {
    "weighted_sssp": "weighted_sssp/sharded_k4_sssp_native_host",
    "connected_components": "connected_components/sharded_k4_cc_native_host",
    "residual_pagerank": (
        "residual_pagerank/sharded_k4_residual_pagerank_native_host"
    ),
}


def require_file(path: Path, role: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"missing {role}: {path}")
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload-manifest", type=Path, required=True)
    parser.add_argument("--host-root", type=Path, required=True)
    parser.add_argument("--sssp-xclbin", type=Path)
    parser.add_argument("--cc-xclbin", type=Path)
    parser.add_argument("--respr-xclbin", type=Path)
    parser.add_argument(
        "--algorithm",
        action="append",
        choices=ALGORITHMS,
        dest="algorithms",
        help=(
            "Generate only this algorithm; repeat for multiple algorithms. "
            "The default remains the complete three-algorithm matrix."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = require_file(args.workload_manifest, "workload manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "pass":
        raise ValueError("workload manifest is not admitted")
    selected_algorithms = tuple(args.algorithms or ALGORITHMS)
    if len(set(selected_algorithms)) != len(selected_algorithms):
        raise ValueError("duplicate --algorithm selection")
    xclbin_args = {
        "weighted_sssp": (args.sssp_xclbin, "SSSP xclbin"),
        "connected_components": (args.cc_xclbin, "CC xclbin"),
        "residual_pagerank": (args.respr_xclbin, "ResPR xclbin"),
    }
    xclbins = {}
    for algorithm in selected_algorithms:
        path, role = xclbin_args[algorithm]
        if path is None:
            raise ValueError(f"missing --{role.split()[0].lower()}-xclbin")
        xclbins[algorithm] = require_file(path, role)
    hosts = {
        algorithm: require_file(
            args.host_root / HOST_BASENAMES[algorithm], f"{algorithm} host"
        )
        for algorithm in selected_algorithms
    }

    records = manifest.get("records", [])
    selected_records = [
        record for record in records
        if record.get("algorithm") in selected_algorithms
    ]
    lookup = {
        (record["dataset"], record["algorithm"]): record
        for record in selected_records
    }
    datasets = sorted({record["dataset"] for record in selected_records})
    expected = {
        (dataset, algorithm)
        for dataset in datasets
        for algorithm in selected_algorithms
    }
    if set(lookup) != expected:
        missing = sorted(expected - set(lookup))
        extra = sorted(set(lookup) - expected)
        raise ValueError(f"matrix workload coverage mismatch missing={missing} extra={extra}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            ("case", "algorithm", "graph", "source", "gr_host", "gr_xclbin")
        )
        for dataset in datasets:
            for algorithm in selected_algorithms:
                record = lookup[(dataset, algorithm)]
                graph = require_file(Path(record["graph"]), f"{dataset} graph")
                writer.writerow(
                    (
                        f"{dataset.lower()}_{algorithm}_resident",
                        algorithm,
                        graph,
                        record.get("source", 0),
                        hosts[algorithm],
                        xclbins[algorithm],
                    )
                )
    print(
        "FULLGRAPH_FPGA_MATRIX_PASS "
        f"datasets={len(datasets)} rows={len(expected)} output={args.output}"
    )


if __name__ == "__main__":
    main()
