#!/usr/bin/env python3

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from collect_pure_pipeline_artifact_manifest import (  # noqa: E402
    build_manifest_rows,
    find_launch_packet,
    missing_required,
    postrun_evidence_label,
    write_manifest,
)


def touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="ascii")


with TemporaryDirectory() as tmp:
    repo = Path(tmp)
    target = "hw_emu"
    label = "after_unit"
    baseline_label = "after_base"
    postrun_label = postrun_evidence_label(label)
    build_root = repo / ".tmp_build" / f"pure_pipeline_{target}_stage0"
    run_logs = build_root / "run_logs"
    xclbin = build_root / "build" / f"grasu_regraph_pure_pipeline.{target}.xclbin"

    launch_dir = repo / ".tmp_build" / f"pure_pipeline_launch_packet_launch_packet_{target}_{label}"
    launch_env = launch_dir / "launch_packet.env"
    touch(launch_env, "\n".join([
        f"target={target}",
        f"flow_label={label}",
        f"launch_command={launch_dir / 'launch_command.sh'}",
        f"source_contract_out={launch_dir / 'source_contracts.tsv'}",
        f"source_fingerprints_out={launch_dir / 'source_fingerprints.tsv'}",
        f"readiness_out={launch_dir / 'readiness_hw_emu.txt'}",
        f"acceptance_gates={launch_dir / 'acceptance_gates.tsv'}",
        f"acceptance_check_prelaunch={launch_dir / 'acceptance_check_prelaunch.tsv'}",
        "",
    ]))
    for path in [
        launch_dir / "launch_command.sh",
        launch_dir / "source_contracts.tsv",
        launch_dir / "source_fingerprints.tsv",
        launch_dir / "readiness_hw_emu.txt",
        launch_dir / "acceptance_gates.tsv",
        launch_dir / "acceptance_check_prelaunch.tsv",
        launch_dir / "artifact_hashes.tsv",
        xclbin,
        Path(str(xclbin) + ".info"),
        Path(str(xclbin) + ".link_summary"),
        build_root / "manifest.env",
        build_root / "compile_commands.sh",
        build_root / "link_command.sh",
        run_logs / f"target_flow_{postrun_label}.env",
        run_logs / f"source_contracts_target_flow_{postrun_label}.tsv",
        run_logs / f"source_fingerprints_target_flow_{postrun_label}.tsv",
        run_logs / f"readiness_target_flow_{postrun_label}.txt",
        run_logs / f"xclbin_contract_{target}_{postrun_label}.tsv",
        run_logs / f"finalize_{postrun_label}.env",
        run_logs / f"finalize_{postrun_label}_evidence.tsv",
        run_logs / f"acceptance_check_postrun_target_flow_{postrun_label}.tsv",
        repo / "results" / f"pure_pipeline_{target}_smoke_{postrun_label}" / "summary.tsv",
        repo / "results" / f"pure_pipeline_{target}_compare_{postrun_label}" / "comparison.tsv",
        repo / "results" / f"pure_pipeline_requirement_audit_{postrun_label}" / "audit.json",
        repo / "results" / f"pure_pipeline_evidence_bundle_{postrun_label}" / "bundle_manifest.json",
        repo / "results" / f"pure_stage0_comparison_plan_{baseline_label}" / "comparison_plan.tsv",
        repo / "results" / f"pure_stage0_comparison_plan_{baseline_label}" / "input_identity.tsv",
        repo / "results" / f"grasu_regraph_sssp_pure_stage0_{baseline_label}" / "summary.tsv",
        repo / "results" / f"grasu_regraph_sssp_pure_stage0_identity_{baseline_label}" / "input_identity_check.tsv",
        repo / "results" / f"spine_edge_file_pure_stage0_{baseline_label}" / "summary.tsv",
        repo / "results" / f"pure_pipeline_{target}_pure_stage0_gate_{label}" / "postbuild_matrix.env",
        repo / "results" / f"pure_pipeline_{target}_pure_stage0_gate_{label}" / "summary.tsv",
        repo / "results" / f"pure_pipeline_{target}_pure_stage0_identity_gate_{label}" / "input_identity_check.tsv",
        repo / "results" / f"pure_pipeline_{target}_pure_stage0_compare_{label}" / "comparison.tsv",
    ]:
        touch(path)

    assert postrun_evidence_label("abc") == "postrun_after_abc"
    assert postrun_evidence_label("after_abc") == "postrun_after_abc"
    assert postrun_evidence_label("postrun_after_abc") == "postrun_after_abc"
    assert find_launch_packet(repo, target, label) == launch_dir

    rows = build_manifest_rows(repo, target, label, baseline_label, "gate", "gate")
    assert missing_required(rows) == []
    xclbin_row = next(row for row in rows if row["name"] == "xclbin")
    assert xclbin_row["exists"] == "yes"
    assert xclbin_row["required"] == "yes"
    assert xclbin_row["sha256"]

    out_file = repo / ".tmp_build" / "manifest.tsv"
    write_manifest(out_file, rows)
    assert out_file.read_text(encoding="ascii").startswith("category\tname\tpath")

    (repo / "results" / f"pure_pipeline_{target}_pure_stage0_gate_{label}" / "summary.tsv").unlink()
    rows = build_manifest_rows(repo, target, label, baseline_label, "gate", "gate")
    assert "summary" in missing_required(rows)

    rows = build_manifest_rows(repo, target, label, baseline_label, "gate", "build")
    assert "summary" not in missing_required(rows)

print("test_collect_pure_pipeline_artifact_manifest PASS")
