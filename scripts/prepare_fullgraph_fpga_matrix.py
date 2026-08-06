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
    parser.add_argument("--sssp-xclbin", type=Path, required=True)
    parser.add_argument("--cc-xclbin", type=Path, required=True)
    parser.add_argument("--respr-xclbin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = require_file(args.workload_manifest, "workload manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "pass":
        raise ValueError("workload manifest is not admitted")
    xclbins = {
        "weighted_sssp": require_file(args.sssp_xclbin, "SSSP xclbin"),
        "connected_components": require_file(args.cc_xclbin, "CC xclbin"),
        "residual_pagerank": require_file(args.respr_xclbin, "ResPR xclbin"),
    }
    hosts = {
        algorithm: require_file(
            args.host_root / HOST_BASENAMES[algorithm], f"{algorithm} host"
        )
        for algorithm in ALGORITHMS
    }

    records = manifest.get("records", [])
    lookup = {
        (record["dataset"], record["algorithm"]): record for record in records
    }
    datasets = sorted({record["dataset"] for record in records})
    expected = {(dataset, algorithm) for dataset in datasets for algorithm in ALGORITHMS}
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
            for algorithm in ALGORITHMS:
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
