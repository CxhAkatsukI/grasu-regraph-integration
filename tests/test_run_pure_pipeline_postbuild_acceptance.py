#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from run_pure_pipeline_postbuild_acceptance import build_commands, claim_level_for  # noqa: E402
from run_pure_pipeline_postbuild_acceptance import labels_from_report, target_state  # noqa: E402


sample_report = {
    "stage0_followup": {
        "pure_label": "after_packet",
        "baseline": {"label": "after_baseline"},
    },
    "targets": [
        {"target": "sw_emu", "current_launch_packet_command": ""},
        {"target": "hw_emu", "current_launch_packet_command": "packet_hwemu.sh"},
    ],
}

assert labels_from_report(sample_report) == ("after_packet", "after_baseline")
assert target_state(sample_report, "hw_emu")["current_launch_packet_command"] == "packet_hwemu.sh"
assert target_state(sample_report, "hw") is None
assert claim_level_for("gate", skip_matrix=False) == "gate"
assert claim_level_for("full", skip_matrix=False) == "full"
assert claim_level_for("gate", skip_matrix=True) == "build"


commands = build_commands(
    target="hw_emu",
    label="after_abc1234",
    baseline_label="after_base",
    mode="gate",
    gate_case="tiny_star_v16_u12",
    gate_timeout=900,
    require_compare=True,
    skip_postrun=False,
    skip_matrix=False,
    skip_claim_check=False,
)

assert commands[0] == [
    "./scripts/run_pure_pipeline_target_flow.sh",
    "--target",
    "hw_emu",
    "--label",
    "postrun_after_abc1234",
    "--skip-build",
    "--gate-case",
    "tiny_star_v16_u12",
    "--gate-timeout",
    "900",
]
assert commands[1] == [
    "./scripts/run_pure_stage0_postbuild_matrix.sh",
    "--target",
    "hw_emu",
    "--mode",
    "gate",
    "--label",
    "after_abc1234",
    "--baseline-label",
    "after_base",
    "--require-compare",
]
assert commands[2] == [
    "./scripts/check_pure_pipeline_claim.py",
    "--target",
    "hw_emu",
    "--level",
    "gate",
]

commands = build_commands(
    target="hw",
    label="manual_label",
    baseline_label="after_base",
    mode="full",
    gate_case="tiny_star_v16_u12",
    gate_timeout=300,
    require_compare=False,
    skip_postrun=True,
    skip_matrix=False,
    skip_claim_check=False,
)
assert len(commands) == 2
assert commands[0][0] == "./scripts/run_pure_stage0_postbuild_matrix.sh"
assert "--require-compare" not in commands[0]
assert "--mode" in commands[0]
assert "full" in commands[0]
assert commands[1] == [
    "./scripts/check_pure_pipeline_claim.py",
    "--target",
    "hw",
    "--level",
    "full",
]

commands = build_commands(
    target="hw",
    label="manual_label",
    baseline_label="after_base",
    mode="gate",
    gate_case="tiny_star_v16_u12",
    gate_timeout=300,
    require_compare=True,
    skip_postrun=False,
    skip_matrix=True,
    skip_claim_check=False,
)
assert len(commands) == 2
assert commands[0][0] == "./scripts/run_pure_pipeline_target_flow.sh"
assert commands[1] == [
    "./scripts/check_pure_pipeline_claim.py",
    "--target",
    "hw",
    "--level",
    "build",
]

commands = build_commands(
    target="hw",
    label="manual_label",
    baseline_label="after_base",
    mode="gate",
    gate_case="tiny_star_v16_u12",
    gate_timeout=300,
    require_compare=True,
    skip_postrun=False,
    skip_matrix=False,
    skip_claim_check=True,
)
assert all(command[0] != "./scripts/check_pure_pipeline_claim.py" for command in commands)

print("test_run_pure_pipeline_postbuild_acceptance PASS")
