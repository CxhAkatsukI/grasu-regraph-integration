"""Admit only the complete predeclared connected host-functional matrix."""

import re

from spine_cycle_sim.experiments.evaluation_impact.common_g.complete_pipeline.analysis import WARNING_PAIR
from ..analysis import COUNTS


LINE = re.compile(
    r"PRODUCTION_CONNECTED_PASS updates=(\d+) generation=([01]) capacity=131072 "
    r"search=4 cache=2 cold=2 external_channels=12 internal_channels=1356 completions=4 "
    r"blocked=(\d+) same_addresses=1")


def expected_cold_insertions():
    """Independent set oracle for the declared two-generation update fixture."""
    present = set()
    insertions = 0
    for count in COUNTS:
        for generation in (0, 1):
            for operation in range(count):
                mapped = (operation % 8) ^ (4 if generation else 0)
                key = (mapped, (operation // 8) % 2)
                if key in present:
                    present.remove(key)
                else:
                    present.add(key)
                    insertions += mapped >= 4
    return insertions


def diagnostics(stderr):
    expected = expected_cold_insertions()
    remaining = stderr
    for message in WARNING_PAIR:
        if remaining.count(message) != expected:
            raise ValueError("unexpected connected-G cold insertion width-warning count")
        remaining = remaining.replace(message, "")
    if remaining.strip():
        raise ValueError("unknown connected-G runtime diagnostic")
    return {"retained_vendor_width_warning_pairs": expected,
            "origin": "actual cold-DDR 512-bit |= 32-bit insertion",
            "complete_intermediate_state_gate_required": True}


def functional(stdout):
    rows = []
    for line in stdout.splitlines():
        match = LINE.fullmatch(line)
        if not match:
            raise ValueError("unexpected connected-G functional output")
        count, generation, blocked = map(int, match.groups())
        if count >= 63 and not blocked:
            raise ValueError("connected-G backpressure was not exercised")
        rows.append({"updates": count, "generation": generation, "blocked_writes": blocked})
    if [(row["updates"], row["generation"]) for row in rows] != [(count, generation)
            for count in COUNTS for generation in (0, 1)]:
        raise ValueError("missing, duplicate or reordered connected-G execution")
    return rows


def stale_rejection(step, stdout, stderr):
    if (step["exit_code"] != 1 or step["stop_reason"] != "process_exit" or
            step["cleanup_snapshot_error"] or stderr != "integrated PMA state mismatch\n"):
        raise ValueError("stale-metadata control did not reject for the expected reason")
    expected = [(0, 0), (0, 1), (1, 0)]
    observed = []
    for line in stdout.splitlines():
        match = LINE.fullmatch(line)
        if not match:
            raise ValueError("unexpected stale-metadata control output")
        observed.append(tuple(map(int, match.groups()[:2])))
    if observed != expected:
        raise ValueError("stale-metadata control failed at the wrong transaction")
    return {"expected_rejection": True, "rejected_at": {"updates": 1, "generation": 1},
            "reason": "integrated PMA state mismatch"}
