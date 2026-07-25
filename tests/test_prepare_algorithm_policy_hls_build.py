#!/usr/bin/env python3

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREPARE = ROOT / "scripts" / "prepare_algorithm_policy_hls_build.sh"


def parse_manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    platform = tmp / "platform.xpfm"
    platform.touch()
    hls = tmp / "hls"
    (hls / "etc").mkdir(parents=True)
    output = tmp / "output"
    env = os.environ.copy()
    env["GRI_ROOT"] = str(ROOT)

    subprocess.run(
        [
            str(PREPARE),
            "--target",
            "hw",
            "--algorithm",
            "all",
            "--platform-xpfm",
            str(platform),
            "--hls-include",
            str(hls),
            "--hls-include-etc",
            str(hls / "etc"),
            "--build-root",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    commands = (output / "compile_commands.sh").read_text(encoding="utf-8")
    manifest = parse_manifest(output / "manifest.env")
    inputs = (output / "inputs.tsv").read_text(encoding="utf-8")
    subprocess.run(["bash", "-n", str(output / "compile_commands.sh")], check=True)

    assert commands.count("v++ --target hw --compile") == 3
    assert "-DREGRAPH_ALGORITHM_POLICY=1" in commands
    assert "-DREGRAPH_ALGORITHM_POLICY=2" in commands
    assert "-DREGRAPH_ALGORITHM_POLICY=3" in commands
    assert "--kernel_frequency 200" in commands
    assert manifest["CLAIM_CLASS"] == (
        "synthesizable_policy_core_not_full_system_native"
    )
    assert manifest["EVIDENCE_SCOPE"] == "incremental_map_reduce_apply_datapath"
    assert manifest["POLICY_LANES"] == "8"
    assert manifest["WEIGHTED_SSSP_STATE_BYTES_PER_VERTEX"] == "4"
    assert manifest["FULL_PAGERANK_STATE_BYTES_PER_VERTEX"] == "4"
    assert manifest["THRESHOLDED_RESIDUAL_PAGERANK_STATE_BYTES_PER_VERTEX"] == "8"
    assert inputs.count("generated_xo\tpending") == 3

    invalid = subprocess.run(
        [str(PREPARE), "--algorithm", "not-an-algorithm"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode == 2
    assert "Invalid --algorithm" in invalid.stderr

print("test_prepare_algorithm_policy_hls_build PASS")
