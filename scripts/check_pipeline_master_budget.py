#!/usr/bin/env python3
"""Audit the AXI-master cost of a GraSU+ReGraph compute pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.check_xo_master_budget import master_interfaces
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repo root.
    from check_xo_master_budget import master_interfaces


SHARED_CUS = {
    "bin_search": 4,
    "dispatch_degree": 1,
    "process_cache": 2,
    "process_ddr": 2,
    "grasu_degree_update": 1,
    "regraph_pagerank_source_prepare": 1,
}

WORKER_CUS = {
    "pma_to_regraph_adapter": 1,
    "lksg_stream": 1,
    "kernelLittleGSMerger": 1,
    "regraph_pagerank_apply": 1,
    "kernelHBMWrapper": 1,
}

SHARDED_K4_CUS = {
    "bin_search": 4,
    "dispatch_degree": 1,
    "process_cache": 2,
    "process_ddr": 2,
    "grasu_degree_update": 1,
    "regraph_pagerank_source_prepare": 1,
    "pma_to_regraph_adapter": 4,
    "lksg_stream": 4,
    "regraph_frontend_mux": 1,
    "kernelLittleGSMerger": 1,
    "regraph_pagerank_apply": 1,
    "kernelHBMWrapper": 1,
}


def project_master_count(
    build_dir: Path,
    compute_pipelines: int,
    pipeline_mode: str = "weighted-axis",
) -> tuple[int, dict[str, dict[str, int]]]:
    if compute_pipelines <= 0:
        raise ValueError("compute_pipelines must be positive")
    if pipeline_mode not in {"weighted-axis", "sharded-k4"}:
        raise ValueError(f"unsupported pipeline mode: {pipeline_mode}")
    breakdown: dict[str, dict[str, int]] = {}
    total = 0
    if pipeline_mode == "sharded-k4":
        topology = SHARDED_K4_CUS
    else:
        topology = {
            **SHARED_CUS,
            **{
                kernel: base_cus * compute_pipelines
                for kernel, base_cus in WORKER_CUS.items()
            },
        }
    for kernel, cus in topology.items():
        xo = build_dir / f"{kernel}.hw.xo"
        if not xo.is_file():
            matches = sorted(build_dir.glob(f"{kernel}.*.xo"))
            if len(matches) != 1:
                raise FileNotFoundError(
                    f"expected one compiled XO for {kernel} under {build_dir}"
                )
            xo = matches[0]
        masters_per_cu = len(master_interfaces(xo))
        subtotal = masters_per_cu * cus
        breakdown[kernel] = {
            "compute_units": cus,
            "masters_per_compute_unit": masters_per_cu,
            "master_instances": subtotal,
        }
        total += subtotal
    return total, breakdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--compute-pipelines", type=int, required=True)
    parser.add_argument(
        "--pipeline-mode",
        choices=("weighted-axis", "sharded-k4"),
        default="weighted-axis",
    )
    parser.add_argument("--platform-master-budget", type=int, default=33)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    total, breakdown = project_master_count(
        args.build_dir.resolve(), args.compute_pipelines, args.pipeline_mode
    )
    passed = total <= args.platform_master_budget
    result = {
        "schema_version": 1,
        "topology": (
            "four_sharded_pma_source_gather_frontends_one_shared_downstream"
            if args.pipeline_mode == "sharded-k4"
            else "direct_complete_worker_replication"
        ),
        "pipeline_mode": args.pipeline_mode,
        "compute_pipelines": args.compute_pipelines,
        "platform_master_budget": args.platform_master_budget,
        "projected_axi_master_instances": total,
        "passed": passed,
        "breakdown": breakdown,
        "disposition": (
            "link_budget_admitted"
            if passed
            else "rejected_before_link_requires_shared_port_integration"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not passed:
        parser.error(
            f"K={args.compute_pipelines} requires {total} AXI masters, "
            f"exceeding platform budget {args.platform_master_budget}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
