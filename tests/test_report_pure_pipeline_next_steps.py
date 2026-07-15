#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from report_pure_pipeline_next_steps import (  # noqa: E402
    postrun_evidence_label,
    postrun_followup_commands,
    stage0_followup_commands,
)


assert postrun_evidence_label("abc1234") == "postrun_after_abc1234"
assert postrun_evidence_label("after_abc1234") == "postrun_after_abc1234"
assert postrun_evidence_label("postrun_after_abc1234") == "postrun_after_abc1234"

postrun = postrun_followup_commands("after_abc1234")
assert [item["name"] for item in postrun] == ["hw_emu_postrun", "hw_postrun"]
assert "--skip-build" in postrun[0]["command"]
assert "--target hw_emu" in postrun[0]["command"]
assert "--label postrun_after_abc1234" in postrun[0]["command"]
assert "--gate-timeout 900" in postrun[0]["command"]
assert "--target hw" in postrun[1]["command"]
assert "--gate-timeout 300" in postrun[1]["command"]

stage0 = stage0_followup_commands("after_pure", "after_baseline")
assert [item["name"] for item in stage0] == ["hw_emu_gate", "hw_gate", "hw_full"]
assert "--target hw_emu" in stage0[0]["command"]
assert "--mode gate" in stage0[0]["command"]
assert "--baseline-label after_baseline" in stage0[0]["command"]
assert "--target hw" in stage0[2]["command"]
assert "--mode full" in stage0[2]["command"]

print("test_report_pure_pipeline_next_steps PASS")
