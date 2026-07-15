#!/usr/bin/env python3

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / ".tmp_build" / "test_run_pure_stage0_postbuild_matrix"
OUT_DIR = OUT_ROOT / "run"
IDENTITY_DIR = OUT_ROOT / "identity"
PLAN_DIR = OUT_ROOT / "plan"
COMPARE_DIR = OUT_ROOT / "compare"

shutil.rmtree(OUT_ROOT, ignore_errors=True)

cmd = [
    str(ROOT / "scripts" / "run_pure_stage0_postbuild_matrix.sh"),
    "--target",
    "sw_emu",
    "--mode",
    "full",
    "--label",
    "after_case_timeout_unit",
    "--baseline-label",
    "after_64ba9c3",
    "--out-dir",
    str(OUT_DIR),
    "--identity-dir",
    str(IDENTITY_DIR),
    "--plan-dir",
    str(PLAN_DIR),
    "--compare-out",
    str(COMPARE_DIR),
    "--case",
    "large_chain_v4096,boundary_hotdst_v65536_u4096",
    "--case-timeout",
    "large_chain_v4096=7200",
    "--case-timeout",
    "boundary_hotdst_v65536_u4096=1800",
    "--skip-identity",
    "--skip-compare",
    "--dry-run",
]

result = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)
assert "--case-timeout large_chain_v4096=7200" in result.stdout
assert "--case-timeout boundary_hotdst_v65536_u4096=1800" in result.stdout

env_text = (OUT_DIR / "postbuild_matrix.env").read_text(encoding="ascii")
assert "case_timeout_overrides=large_chain_v4096=7200,boundary_hotdst_v65536_u4096=1800" in env_text

print("test_run_pure_stage0_postbuild_matrix PASS")
