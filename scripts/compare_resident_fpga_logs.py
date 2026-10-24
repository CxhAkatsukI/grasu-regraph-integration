#!/usr/bin/env python3
"""Compare continuous resident walls, not summed component-event durations.

This validates log semantics only. Routed timing, source/binary/input hashes,
device identity and memory admission remain the experiment runner's gates.
"""

import argparse
import json
import math
from pathlib import Path


PROFILES = {
    "weighted_sssp": (0, "WEIGHTED_PMA_NATIVE_SHARDED"),
    "connected_components": (1, "CC_PMA_NATIVE_SHARDED"),
    "residual_pagerank": (2, "RESIDUAL_PR_PMA_NATIVE_SHARDED"),
}
BOUNDARY = "resident_update_to_final_readback_wall_including_host_relaunch"


def record(text, prefix):
    lines = [line for line in text.splitlines() if line.startswith(prefix + " ")]
    if len(lines) != 1:
        raise ValueError("exactly one record required: " + prefix)
    fields = {}
    for token in lines[0].split()[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key in fields:
            raise ValueError("duplicate field: " + key)
        fields[key] = value
    return fields


def require(fields, **expected):
    for key, value in expected.items():
        if fields.get(key) != str(value):
            raise ValueError("unexpected " + key + ": " + str(fields.get(key)))


def finite(fields, key, *, positive=False):
    value = float(fields[key])
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError("invalid finite value: " + key)
    return value


def compare(algorithm, gr_text, spine_text, source):
    kind, prefix = PROFILES[algorithm]
    gr = record(gr_text, prefix + "_RESULT")
    timing = record(gr_text, prefix + "_TIMING")
    spine = record(spine_text, "SPINE_RESIDENT_BENCHMARK_PASS")
    repeat = record(gr_text, "GRASU_SHARDED_UPDATE_REPEAT_CONFIG")
    require(repeat, repeats=1)
    require(gr, status="PASS", hardware_converged=1, oracle_converged=1,
            resident_state="old_graph_converged", conversion_cost="absent",
            k4_frontends=4, shared_regraph_downstream=1)
    require(spine, algorithm=kind, source=source, boundary=BOUNDARY,
            final_validation="outside_wall", full_state_readback="each_round",
            host_correction_included=int(kind == 2))
    counts = {}
    for key in ("vertices", "logical_updates", "physical_updates"):
        count = int(gr[key])
        if count <= 0 or count != int(spine[key]):
            raise ValueError("workload count mismatch: " + key)
        counts[key] = count
    if int(spine["iterations"]) < 0:
        raise ValueError("negative Spine iteration count")
    if kind == 2:
        require(gr, rank_mismatches=0, degree_mismatches=0, rank_nonfinite=0,
                threshold_semantics="direct_per_vertex")
        if float(gr["epsilon"]) != 1.0e-6:
            raise ValueError("residual threshold must be direct 1e-6")
        error = finite(gr, "rank_error_l1")
        expected = finite(gr, "rank_expected_l1")
        limit = finite(gr, "rank_error_l1_limit")
        expected_limit = 1.0e-4 + 1.0e-3 * expected
        # The host prints six decimals, so allow only its rounding tolerance.
        if abs(limit - expected_limit) > 5.1e-7 or error > limit + 5.1e-7:
            raise ValueError("aggregate rank error not accepted")
        gr_rounds = int(gr["propagation_rounds"])
    else:
        require(gr, mismatches=0, source_external=source)
        gr_rounds = int(gr["executed_supersteps"])
    if gr_rounds < 0:
        raise ValueError("negative G+R iteration count")
    # Legacy field name: source inspection establishes this is the continuous
    # resident wall after initial allocation/migration, not initial graph setup.
    gr_wall = finite(timing, "setup_inclusive_ms", positive=True)
    spine_wall = finite(spine, "wall_ms", positive=True)
    speedup = gr_wall / spine_wall
    if not math.isfinite(speedup) or speedup <= 0:
        raise ValueError("invalid speedup")
    return dict(algorithm=algorithm, boundary=BOUNDARY, **counts,
                gr_rounds=gr_rounds, spine_rounds=int(spine["iterations"]),
                gr_wall_ms=gr_wall, spine_wall_ms=spine_wall,
                speedup_gr_over_spine=speedup,
                scope="log_semantics_only_not_provenance_or_hardware_acceptance")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algorithm", required=True, choices=PROFILES)
    parser.add_argument("--gr-log", required=True, type=Path)
    parser.add_argument("--spine-log", required=True, type=Path)
    parser.add_argument("--source", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.source < 0:
        parser.error("source must be nonnegative")
    result = compare(args.algorithm, args.gr_log.read_text(),
                     args.spine_log.read_text(), args.source)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
