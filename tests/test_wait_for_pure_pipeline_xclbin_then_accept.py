#!/usr/bin/env python3

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from wait_for_pure_pipeline_xclbin_then_accept import (  # noqa: E402
    build_acceptance_command,
    wait_for_xclbin,
)


command = build_acceptance_command(
    target="hw",
    label="after_abc1234",
    baseline_label="after_base",
    mode="full",
    gate_case="tiny_star_v16_u12",
    gate_timeout=300,
    require_compare=True,
    skip_postrun=False,
    skip_matrix=False,
    skip_artifact_manifest=False,
    skip_claim_check=False,
    allow_label_mismatch=False,
)

assert command == [
    "./scripts/run_pure_pipeline_postbuild_acceptance.py",
    "--target",
    "hw",
    "--label",
    "after_abc1234",
    "--baseline-label",
    "after_base",
    "--mode",
    "full",
    "--gate-case",
    "tiny_star_v16_u12",
    "--gate-timeout",
    "300",
]
assert "--skip-claim-check" not in command
assert "--skip-artifact-manifest" not in command
assert "--allow-label-mismatch" not in command

command = build_acceptance_command(
    target="hw_emu",
    label="manual",
    baseline_label="after_base",
    mode="gate",
    gate_case="tiny_star_v16_u12",
    gate_timeout=900,
    require_compare=False,
    skip_postrun=True,
    skip_matrix=False,
    skip_artifact_manifest=True,
    skip_claim_check=True,
    allow_label_mismatch=True,
)

assert "--no-require-compare" in command
assert "--skip-postrun" in command
assert "--skip-matrix" not in command
assert "--skip-artifact-manifest" in command
assert "--skip-claim-check" in command
assert "--allow-label-mismatch" in command

with tempfile.TemporaryDirectory() as tmp:
    missing = Path(tmp) / "missing.xclbin"
    assert wait_for_xclbin(missing, timeout_seconds=0, poll_seconds=1, once=True) is False
    present = Path(tmp) / "present.xclbin"
    present.write_bytes(b"xclbin")
    assert wait_for_xclbin(present, timeout_seconds=0, poll_seconds=1, once=True) is True

print("test_wait_for_pure_pipeline_xclbin_then_accept PASS")
