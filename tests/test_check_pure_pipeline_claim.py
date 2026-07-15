#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_pure_pipeline_claim import claim_for_level, target_state  # noqa: E402


report = {
    "completion_claim": {
        "claimable": False,
        "missing": ["hw_emu_gate", "hw_gate", "hw_full"],
        "interpretation": "not ready",
    },
    "targets": [
        {
            "target": "sw_emu",
            "xclbin": "sw.xclbin",
            "current_launch_packet_command": "",
            "claim_status": {
                "build_claimable": True,
                "build_missing": [],
                "gate_claimable": True,
                "gate_missing": [],
                "full_claimable": False,
                "full_missing": ["stage0_full_summary"],
            },
        },
        {
            "target": "hw",
            "xclbin": "hw.xclbin",
            "current_launch_packet_command": "packet_hw.sh",
            "claim_status": {
                "build_claimable": False,
                "build_missing": ["target_xclbin", "postrun_acceptance"],
                "gate_claimable": False,
                "gate_missing": ["target_xclbin", "postrun_acceptance", "stage0_gate_summary"],
                "full_claimable": False,
                "full_missing": ["target_xclbin", "postrun_acceptance", "stage0_full_summary"],
            },
        },
    ],
}


assert target_state(report, "hw")["xclbin"] == "hw.xclbin"
assert target_state(report, "missing") is None

completion = claim_for_level(report, "completion", None)
assert completion["target"] == "all"
assert completion["claimable"] is False
assert completion["missing"] == ["hw_emu_gate", "hw_gate", "hw_full"]

sw_gate = claim_for_level(report, "gate", "sw_emu")
assert sw_gate["claimable"] is True
assert sw_gate["missing"] == []

hw_build = claim_for_level(report, "build", "hw")
assert hw_build["claimable"] is False
assert hw_build["missing"] == ["target_xclbin", "postrun_acceptance"]
assert hw_build["launch_command"] == "packet_hw.sh"

try:
    claim_for_level(report, "full", None)
except ValueError as exc:
    assert "--target is required" in str(exc)
else:
    raise AssertionError("missing target should fail")

print("test_check_pure_pipeline_claim PASS")
