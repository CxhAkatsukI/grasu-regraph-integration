#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from summarize_pure_pipeline_smoke import joined_rows  # noqa: E402


host_rows = {
    "tiny_chain_v16": {
        "case": "tiny_chain_v16",
        "family": "chain",
        "vertices": "16",
        "final_edges": "15",
        "source": "0",
        "supersteps": "16",
        "status": "PASS",
        "wall_seconds": "1.0",
        "grasu_ms": "1.5",
        "regraph_e2e_ms": "2.5",
        "mismatch_count": "0",
    }
}
pure_rows = {
    "tiny_chain_v16": {
        "case": "tiny_chain_v16",
        "family": "chain",
        "vertices": "16",
        "final_edges": "15",
        "source": "0",
        "supersteps": "16",
        "status": "PASS",
        "timing_line": (
            "PURE_PIPELINE_TIMING grasu_ms=3 barrier_ms=0.25 adapter_ms=4 "
            "lksg_ms=5 apply_ms=6 hbm_ms=7 event_e2e_ms=8 wall_ms=9"
        ),
    }
}
spine_rows = {
    "tiny_chain_v16": {
        "case": "tiny_chain_v16",
        "status": "PASS",
        "maint_ms": "0.1",
        "conv_ms": "0.2",
        "kernel_e2e_ms": "0.3",
        "errors": "0",
    }
}

rows = joined_rows(host_rows, pure_rows, spine_rows, pure_target="hw")
assert len(rows) == 1
row = rows[0]
assert row["host_zero_cost_ms"] == "4.000000"
assert row["pure_grasu_ms"] == "3"
assert row["pure_barrier_ms"] == "0.25"
assert row["pure_adapter_ms"] == "4"
assert row["pure_lksg_ms"] == "5"
assert row["pure_apply_ms"] == "6"
assert row["pure_event_e2e_ms"] == "8"
assert row["notes"] == ""

print("test_summarize_pure_pipeline_smoke PASS")
