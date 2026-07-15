#!/usr/bin/env python3

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from collect_pure_pipeline_prebuild_snapshot import (  # noqa: E402
    claim_rows,
    default_baseline_label,
    default_label,
    snapshot_artifact_rows,
)


def touch(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


sample_report = {
    "repo": "/tmp/repo",
    "head": "abc123",
    "dirty": False,
    "source_fingerprint_sha256": "fingerprint",
    "next_commands": ["packet/launch_command.sh"],
    "completion_claim": {
        "claimable": False,
        "missing": ["hw_emu_gate", "hw_gate", "hw_full"],
        "interpretation": "not ready",
    },
    "stage0_followup": {
        "baseline": {"label": "after_base"},
        "pure_label": "after_unit",
    },
    "targets": [
        {
            "target": "hw_emu",
            "build_root": ".tmp_build/pure_pipeline_hw_emu_stage0",
            "xclbin": ".tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin",
            "xclbin_exists": False,
            "current_launch_packet": ".tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_unit",
            "current_launch_packet_command": ".tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_unit/launch_command.sh",
            "current_launch_packet_flow_label": "after_unit",
            "current_launch_packet_helpers": {
                "wait_then_accept_gate": ".tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_unit/wait_then_accept_gate.sh",
            },
            "claim_status": {
                "build_claimable": False,
                "build_missing": ["target_xclbin", "postrun_acceptance"],
                "gate_claimable": False,
                "gate_missing": ["target_xclbin", "stage0_gate_summary"],
                "full_claimable": False,
                "full_missing": ["target_xclbin", "stage0_full_summary"],
            },
        }
    ],
}


assert default_label(sample_report, "hw_emu") == "after_unit"
assert default_baseline_label(sample_report) == "after_base"

rows = claim_rows(sample_report, "hw_emu")
assert [row["level"] for row in rows] == ["completion", "build", "gate", "full"]
assert rows[0]["target"] == "all"
assert rows[1]["missing"] == "target_xclbin,postrun_acceptance"
assert rows[2]["launch_command"].endswith("launch_command.sh")

with TemporaryDirectory() as tmp:
    repo = Path(tmp)
    report = dict(sample_report)
    report["repo"] = str(repo)
    packet = repo / ".tmp_build" / "pure_pipeline_launch_packet_launch_packet_hw_emu_after_unit"
    build_root = repo / ".tmp_build" / "pure_pipeline_hw_emu_stage0"
    touch(packet / "launch_packet.env", "\n".join([
        "target=hw_emu",
        "flow_label=after_unit",
        f"source_contract_out={packet / 'source_contracts.tsv'}",
        f"source_fingerprints_out={packet / 'source_fingerprints.tsv'}",
        f"readiness_out={packet / 'readiness_hw_emu.txt'}",
        f"acceptance_gates={packet / 'acceptance_gates.tsv'}",
        f"acceptance_check_prelaunch={packet / 'acceptance_check_prelaunch.tsv'}",
        "",
    ]))
    for name in (
        "launch_command.sh",
        "source_contracts.tsv",
        "source_fingerprints.tsv",
        "readiness_hw_emu.txt",
        "acceptance_gates.tsv",
        "acceptance_check_prelaunch.tsv",
        "wait_then_accept_gate.sh",
    ):
        touch(packet / name)
    for name in ("manifest.env", "compile_commands.sh", "link_command.sh"):
        touch(build_root / name)
    out_dir = repo / ".tmp_build" / "snapshot"
    next_json = out_dir / "next_steps.json"
    next_txt = out_dir / "next_steps.txt"
    claims = out_dir / "claim_status.tsv"
    manifest = out_dir / "artifact_manifest.tsv"
    readme = out_dir / "README.md"
    for path in (next_json, next_txt, claims, manifest, readme):
        touch(path)
    artifact_rows = snapshot_artifact_rows(
        repo,
        report,
        "hw_emu",
        out_dir,
        next_json,
        next_txt,
        claims,
        manifest,
        readme,
    )
    required_missing = [
        row["name"]
        for row in artifact_rows
        if row["required"] == "yes" and row["exists"] != "yes"
    ]
    assert required_missing == []
    xclbin_rows = [row for row in artifact_rows if row["name"] == "xclbin"]
    assert xclbin_rows[0]["required"] == "no"
    assert xclbin_rows[0]["exists"] == "no"

print("test_collect_pure_pipeline_prebuild_snapshot PASS")
