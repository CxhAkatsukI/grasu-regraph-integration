#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from summarize_canonical_comparison import (  # noqa: E402
    metric_stats,
    summarize_group,
    system_name,
)


stats = metric_stats([1.0, 2.0, 3.0, 4.0])
assert stats["minimum"] == 1.0
assert stats["median"] == 2.5
assert stats["p10"] == 1.3
assert stats["p90"] == 3.7
assert system_name({"system": "grasu_custom_pull"}) == "grasu_custom_pull"
try:
    system_name({"algorithm": "bfs", "target": "hw"})
except ValueError as error:
    assert "fail closed" in str(error)
else:
    raise AssertionError("missing provenance must not be inferred as AccuGraph")

expected = {"graph_sha256": "graph", "bfs_source": 0}
record = {
    "graph_sha256": "graph",
    "source": 0,
    "warmup": False,
    "correct": True,
    "performance_claim_eligible": False,
    "resident_batch_end_to_end_ms": 8.0,
    "workload_end_to_end_ms": 10.0,
    "host_sha256": "host",
    "xclbin_sha256": "xclbin",
    "source_states": {
        "runner": {"commit": "abc", "tracked_dirty": False},
    },
}
summary = summarize_group([record], expected, minimum_repeats=10)
assert summary["claim_eligible"] is False
assert "measured_runs=1<10" in summary["blockers"]
assert "performance_claim_not_eligible" in summary["blockers"]

eligible_records = []
for index in range(10):
    candidate = dict(record)
    candidate["performance_claim_eligible"] = True
    candidate["resident_batch_end_to_end_ms"] = float(index + 1)
    candidate["workload_end_to_end_ms"] = float(index + 1)
    eligible_records.append(candidate)
summary = summarize_group(eligible_records, expected, minimum_repeats=10)
assert summary["claim_eligible"] is True
assert summary["statistics"]["resident_batch_end_to_end_ms"]["median"] == 5.5
print("test_summarize_canonical_comparison PASS")
