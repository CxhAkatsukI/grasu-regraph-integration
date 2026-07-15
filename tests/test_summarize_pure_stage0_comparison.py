#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from summarize_pure_stage0_comparison import joined_rows  # noqa: E402


manifest_rows = [
    {
        "case": "tiny_chain_v16",
        "family": "chain",
        "vertices": "16",
        "update_edges": "0",
        "final_edges": "15",
        "source": "0",
        "supersteps": "16",
    },
    {
        "case": "small_chain_v64",
        "family": "chain",
        "vertices": "64",
        "update_edges": "0",
        "final_edges": "63",
        "source": "0",
        "supersteps": "64",
    },
]

host_rows = {
    "tiny_chain_v16": {
        "case": "tiny_chain_v16",
        "status": "PASS",
        "grasu_ms": "1.0",
        "regraph_e2e_ms": "2.0",
        "mismatch_count": "0",
    },
    "small_chain_v64": {
        "case": "small_chain_v64",
        "status": "PASS",
        "grasu_ms": "1.0",
        "regraph_e2e_ms": "2.0",
        "mismatch_count": "0",
    },
}

spine_rows = {
    "tiny_chain_v16": {
        "case": "tiny_chain_v16",
        "status": "PASS",
        "kernel_e2e_ms": "1.5",
        "errors": "0",
    },
    "small_chain_v64": {
        "case": "small_chain_v64",
        "status": "PASS",
        "kernel_e2e_ms": "2.5",
        "errors": "0",
    },
}

pure_rows = {
    "tiny_chain_v16": {
        "case": "tiny_chain_v16",
        "status": "PASS",
        "timing_line": (
            "PURE_PIPELINE_TIMING grasu_ms=3 barrier_ms=0.2 adapter_ms=4 "
            "lksg_ms=5 apply_ms=6 hbm_ms=7 event_e2e_ms=8"
        ),
        "result_line": "PURE_PIPELINE_RESULT status=PASS mismatches=0",
    },
}

rows = joined_rows(
    manifest_rows,
    {},
    host_rows,
    spine_rows,
    pure_rows,
    "sw_emu",
)
by_case = {row["case"]: row for row in rows}

assert by_case["tiny_chain_v16"]["notes"] == "pure timing is sw_emu, not hw"
assert by_case["tiny_chain_v16"]["pure_mismatches"] == "0"
assert by_case["small_chain_v64"]["notes"] == "missing pure pipeline"
assert "pure mismatches" not in by_case["small_chain_v64"]["notes"]
assert "pure timing is sw_emu" not in by_case["small_chain_v64"]["notes"]

print("test_summarize_pure_stage0_comparison PASS")
