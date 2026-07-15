#!/usr/bin/env python3

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_pure_pipeline_acceptance_gates import (  # noqa: E402
    COMPARISON_TIMING_FIELDS,
    EXPECTED_CASES,
    check_same_input_compare,
    smoke_ok,
)


row = {
    "status": "PASS",
    "result_line": "PURE_PIPELINE_RESULT status=PASS mismatches=0",
    "timing_line": (
        "PURE_PIPELINE_TIMING grasu_ms=1 barrier_ms=0.1 adapter_ms=2 "
        "lksg_ms=3 apply_ms=4 event_e2e_ms=5"
    ),
}
ok, detail = smoke_ok(row)
assert ok, detail

missing_timing = dict(row)
missing_timing["timing_line"] = "PURE_PIPELINE_TIMING grasu_ms=1"
ok, detail = smoke_ok(missing_timing)
assert not ok
assert "missing_timing" in detail
assert "barrier_ms" in detail


def comparison_text(drop_field: str = "") -> str:
    fields = [
        "case",
        "host_status",
        "spine_status",
        "pure_status",
        "host_zero_cost_ms",
        *COMPARISON_TIMING_FIELDS,
    ]
    lines = ["\t".join(fields)]
    for case in sorted(EXPECTED_CASES):
        values = {
            "case": case,
            "host_status": "PASS",
            "spine_status": "PASS",
            "pure_status": "PASS",
            "host_zero_cost_ms": "1.0",
            "pure_grasu_ms": "1.1",
            "pure_barrier_ms": "0.1",
            "pure_adapter_ms": "2.0",
            "pure_lksg_ms": "3.0",
            "pure_apply_ms": "4.0",
            "pure_event_e2e_ms": "5.0",
        }
        if drop_field:
            values[drop_field] = ""
        lines.append("\t".join(values[field] for field in fields))
    return "\n".join(lines) + "\n"


with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "comparison.tsv"
    path.write_text(comparison_text(), encoding="ascii")
    ok, detail = check_same_input_compare(path)
    assert ok, detail

    path.write_text(comparison_text("pure_apply_ms"), encoding="ascii")
    ok, detail = check_same_input_compare(path)
    assert not ok
    assert "missing_pure_apply_ms" in detail

print("test_check_pure_pipeline_acceptance_gates PASS")
