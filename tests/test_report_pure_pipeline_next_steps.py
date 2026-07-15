#!/usr/bin/env python3

import sys
from tempfile import TemporaryDirectory
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from report_pure_pipeline_next_steps import (  # noqa: E402
    artifact_manifest_state,
    completion_claim,
    launch_packets,
    postbuild_acceptance_commands,
    postbuild_wait_commands,
    postrun_evidence_label,
    postrun_followup_commands,
    stage0_matrix_state,
    stage0_followup_commands,
    target_claim_status,
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
assert "gate claim check" in postbuild[0]["when"]
assert "gate claim check" in postbuild[1]["when"]
assert "full claim check" in postbuild[2]["when"]
assert "artifact manifest" in postbuild[0]["when"]
assert "artifact manifest" in postbuild[1]["when"]
assert "artifact manifest" in postbuild[2]["when"]

postbuild_wait = postbuild_wait_commands("after_pure", "after_baseline")
assert [item["name"] for item in postbuild_wait] == [
    "hw_emu_wait_then_accept",
    "hw_wait_then_accept_gate",
    "hw_wait_then_accept_full",
]
assert "wait_for_pure_pipeline_xclbin_then_accept.py" in postbuild_wait[0]["command"]
assert "--target hw_emu" in postbuild_wait[0]["command"]
assert "--label after_pure" in postbuild_wait[0]["command"]
assert "--baseline-label after_baseline" in postbuild_wait[0]["command"]
assert "--mode gate" in postbuild_wait[0]["command"]
assert "--target hw" in postbuild_wait[2]["command"]
assert "--mode full" in postbuild_wait[2]["command"]
assert "claim check" in postbuild_wait[0]["when"]
assert "claim check" in postbuild_wait[1]["when"]
assert "claim check" in postbuild_wait[2]["when"]
assert "artifact manifest" in postbuild_wait[0]["when"]
assert "artifact manifest" in postbuild_wait[1]["when"]
assert "artifact manifest" in postbuild_wait[2]["when"]

with TemporaryDirectory() as tmp:
    repo = Path(tmp)
    launch_dir = repo / ".tmp_build" / "pure_pipeline_launch_packet_launch_packet_hw_emu_after_unit"
    launch_dir.mkdir(parents=True)
    helper_names = (
        "postbuild_acceptance_gate",
        "wait_then_accept_gate",
        "postbuild_acceptance_full",
        "wait_then_accept_full",
    )
    for helper in helper_names:
        (launch_dir / f"{helper}.sh").write_text("#!/usr/bin/env bash\n", encoding="ascii")
    (launch_dir / "launch_command.sh").write_text("#!/usr/bin/env bash\n", encoding="ascii")
    (launch_dir / "source_fingerprints.tsv").write_text("", encoding="ascii")
    (launch_dir / "launch_packet.env").write_text(
        "\n".join([
            "target=hw_emu",
            "flow_label=after_unit",
            f"source_fingerprints_out={launch_dir / 'source_fingerprints.tsv'}",
            f"launch_command={launch_dir / 'launch_command.sh'}",
            *(f"{helper}={launch_dir / (helper + '.sh')}" for helper in helper_names),
            "",
        ]),
        encoding="ascii",
    )
    packets = launch_packets(repo, "hw_emu", {})
    assert len(packets) == 1
    assert packets[0]["flow_label"] == "after_unit"
    assert set(packets[0]["helpers"]) == set(helper_names)
    assert all(packets[0]["helper_exists"].values())

with TemporaryDirectory() as tmp:
    repo = Path(tmp)
    manifest = (
        repo
        / ".tmp_build"
        / "pure_pipeline_artifact_manifests"
        / "artifact_manifest_hw_emu_gate_after_unit.tsv"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "\n".join([
            "category\tname\tpath\texists\tsha256\tsize_bytes\trequired\tstatus\tdetail",
            "target\txclbin\tx.xclbin\tyes\tabc\t1\tyes\tPASS\tunit",
            "build_logs\tlink_log\tlink.log\tno\t\t\tno\tPASS\toptional",
            "",
        ]),
        encoding="ascii",
    )
    manifest_state = artifact_manifest_state(repo, "hw_emu", "gate", "after_unit")
    assert manifest_state["status"] == "pass"
    assert manifest_state["row_count"] == 2
    assert manifest_state["required_count"] == 1
    assert manifest_state["missing_required"] == []

    manifest.write_text(
        "\n".join([
            "category\tname\tpath\texists\tsha256\tsize_bytes\trequired\tstatus\tdetail",
            "target\txclbin\tx.xclbin\tno\t\t\tyes\tMISSING\tunit",
            "",
        ]),
        encoding="ascii",
    )
    manifest_state = artifact_manifest_state(repo, "hw_emu", "gate", "after_unit")
    assert manifest_state["status"] == "fail"
    assert manifest_state["missing_required"] == ["xclbin"]

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

base_state = {
    "target": "hw",
    "xclbin_exists": True,
    "latest_acceptance_postrun_status": "pass",
    "stage0_gate": {"summary_status": "pass", "identity_status": "pass"},
    "stage0_full": {"summary_status": "missing", "identity_status": "missing"},
    "artifact_manifests": {
        "build": {"status": "missing"},
        "gate": {"status": "pass"},
        "full": {"status": "missing"},
    },
}
claim = target_claim_status(base_state)
assert claim["build_claimable"] is True
assert claim["gate_claimable"] is True
assert claim["full_claimable"] is False
assert claim["full_missing"] == [
    "stage0_full_summary",
    "stage0_full_input_identity",
    "artifact_manifest_full",
]

missing_manifest_state = dict(base_state)
missing_manifest_state["artifact_manifests"] = {
    "build": {"status": "missing"},
    "gate": {"status": "missing"},
    "full": {"status": "missing"},
}
claim = target_claim_status(missing_manifest_state)
assert claim["build_claimable"] is False
assert claim["build_missing"] == ["artifact_manifest_build"]
assert claim["gate_missing"] == ["artifact_manifest_build", "artifact_manifest_gate"]

missing_xclbin_state = {
    "target": "hw_emu",
    "xclbin_exists": False,
    "latest_acceptance_postrun_status": "missing",
    "stage0_gate": {"summary_status": "missing", "identity_status": "missing"},
    "stage0_full": {"summary_status": "missing", "identity_status": "missing"},
    "artifact_manifests": {
        "build": {"status": "missing"},
        "gate": {"status": "missing"},
        "full": {"status": "missing"},
    },
}
claim = target_claim_status(missing_xclbin_state)
assert claim["build_claimable"] is False
assert claim["build_missing"] == [
    "target_xclbin",
    "postrun_acceptance",
    "artifact_manifest_build",
]
assert "stage0_gate_summary" in claim["gate_missing"]

states = [
    {"target": "sw_emu", "claim_status": {"gate_claimable": True}},
    {"target": "hw_emu", "claim_status": {"gate_claimable": False}},
    {"target": "hw", "claim_status": {"gate_claimable": False, "full_claimable": False}},
]
completion = completion_claim(states)
assert completion["claimable"] is False
assert completion["missing"] == ["hw_emu_gate", "hw_gate", "hw_full"]

print("test_report_pure_pipeline_next_steps PASS")
