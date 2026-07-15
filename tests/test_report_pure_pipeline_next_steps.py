#!/usr/bin/env python3

import sys
from tempfile import TemporaryDirectory
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from report_pure_pipeline_next_steps import (  # noqa: E402
    postbuild_acceptance_commands,
    postrun_evidence_label,
    postrun_followup_commands,
    stage0_matrix_state,
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

postbuild = postbuild_acceptance_commands("after_pure", "after_baseline")
assert [item["name"] for item in postbuild] == [
    "hw_emu_postbuild_acceptance",
    "hw_postbuild_acceptance_gate",
    "hw_postbuild_acceptance_full",
]
assert "run_pure_pipeline_postbuild_acceptance.py" in postbuild[0]["command"]
assert "--target hw_emu" in postbuild[0]["command"]
assert "--label after_pure" in postbuild[0]["command"]
assert "--baseline-label after_baseline" in postbuild[0]["command"]
assert "--mode gate" in postbuild[0]["command"]
assert "--target hw" in postbuild[2]["command"]
assert "--mode full" in postbuild[2]["command"]

with TemporaryDirectory() as tmp:
    repo = Path(tmp)
    summary_dir = repo / "results" / "pure_pipeline_sw_emu_pure_stage0_gate_after_unit"
    identity_dir = repo / "results" / "pure_pipeline_sw_emu_pure_stage0_identity_gate_after_unit"
    summary_dir.mkdir(parents=True)
    identity_dir.mkdir(parents=True)
    (summary_dir / "summary.tsv").write_text(
        "\n".join([
            "case\tvertices\texit_code\tstatus",
            "tiny_chain_v16\t16\t0\tPASS",
            "tiny_star_v16_u12\t16\t0\tPASS",
            "tiny_spread_v16_u8\t16\t0\tPASS",
            "tiny_hotdst_v64_u32\t64\t0\tPASS",
            "",
        ]),
        encoding="ascii",
    )
    (identity_dir / "input_identity_check.tsv").write_text(
        "\n".join([
            "case\tcheck\tok\tdetail",
            "tiny_chain_v16\tcase_env\tyes\tunit",
            "tiny_star_v16_u12\tcase_env\tyes\tunit",
            "tiny_spread_v16_u8\tcase_env\tyes\tunit",
            "tiny_hotdst_v64_u32\tcase_env\tyes\tunit",
            "",
        ]),
        encoding="ascii",
    )
    gate_state = stage0_matrix_state(repo, "sw_emu", "gate")
    assert gate_state["label"] == "pass"
    assert gate_state["summary_row_count"] == 4
    assert gate_state["identity_check_count"] == 4
    assert gate_state["max_vertices_seen"] == 64
    assert gate_state["summary"].endswith("summary.tsv")

    full_state = stage0_matrix_state(repo, "sw_emu", "full")
    assert full_state["label"] == "missing"

print("test_report_pure_pipeline_next_steps PASS")
