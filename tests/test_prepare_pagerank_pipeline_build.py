#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREPARE = ROOT / "scripts" / "prepare_pagerank_pipeline_build.sh"


def parse_manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def prepare(root: Path, algorithm: str, target: str) -> Path:
    output = root / f"{algorithm}-{target}"
    env = os.environ.copy()
    env["GRI_ROOT"] = str(ROOT)
    subprocess.run(
        [
            str(PREPARE),
            "--target",
            target,
            "--algorithm",
            algorithm,
            "--build-root",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return output


with tempfile.TemporaryDirectory() as temp_name:
    temp = Path(temp_name)
    full = prepare(temp, "full_pagerank", "sw_emu")
    residual = prepare(temp, "residual_pagerank", "hw")

    full_commands = (full / "compile_commands.sh").read_text(encoding="utf-8")
    full_cfg = (full / "config/full_pagerank_sw_emu.cfg").read_text(
        encoding="utf-8"
    )
    full_manifest = parse_manifest(full / "manifest.env")
    residual_commands = (residual / "compile_commands.sh").read_text(
        encoding="utf-8"
    )
    residual_cfg = (residual / "config/residual_pagerank_hw.cfg").read_text(
        encoding="utf-8"
    )
    residual_manifest = parse_manifest(residual / "manifest.env")

    assert full_commands.count("v++ --target sw_emu --compile") == 11
    assert residual_commands.count("v++ --target hw --compile") == 11
    assert "-DGRASU_REGRAPH_PAGERANK_MODE=1" in full_commands
    assert "-DGRASU_REGRAPH_PAGERANK_MODE=2" in residual_commands
    assert "-DGRASU_REGRAPH_DESTINATION_ONLY=1" in full_commands
    assert "-I" + str(ROOT / "include/regraph_pagerank") in full_commands
    assert "pma_to_regraph_edge_array" not in full_cfg
    assert "dispatch_degree_1.degree_delta:grasu_degree_update_1.degree_delta:64" in full_cfg
    assert "regraph_pagerank_apply_1.residual_state" not in full_cfg
    assert "pr_source_1.residual_state" not in full_cfg
    assert "sp=regraph_pagerank_apply_1.residual_state:HBM[5]" in residual_cfg
    assert "sp=pr_source_1.residual_state:HBM[5]" in residual_cfg
    assert "nk=regraph_pagerank_source_prepare:1:pr_source_1" in full_cfg
    assert "sp=pr_source_1.rank_state:HBM[4]" in full_cfg
    assert "source_prop_write:kernelHBMWrapper_1.prop_write_burst_stm:16" in full_cfg
    assert full_manifest["CLAIM_CLASS"] == (
        "proposed_conversion_free_hls_not_yet_built"
    )
    assert full_manifest["DEGREE_SIDEBAND"] == (
        "dispatch_ordered_projected_optimization"
    )
    assert full_manifest["RESIDUAL_HBM_CHANNEL"] == "unused"
    assert residual_manifest["RESIDUAL_HBM_CHANNEL"] == "5"
    assert (full / "inputs.tsv").read_text().count("generated_xo\tpending") == 11

    for packet in (full, residual):
        subprocess.run(["bash", "-n", str(packet / "compile_commands.sh")], check=True)
        subprocess.run(["bash", "-n", str(packet / "link_command.sh")], check=True)
        subprocess.run(["bash", "-n", str(packet / "run_build.sh")], check=True)

    invalid = subprocess.run(
        [str(PREPARE), "--algorithm", "not-an-algorithm"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode == 2
    assert "Invalid --algorithm" in invalid.stderr

print("test_prepare_pagerank_pipeline_build PASS")
