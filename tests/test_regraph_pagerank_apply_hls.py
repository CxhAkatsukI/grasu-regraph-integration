#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check_regraph_pagerank_apply.sh"


with tempfile.TemporaryDirectory() as temp_name:
    output = Path(temp_name) / "pagerank-apply"
    result = subprocess.run(
        [str(CHECK), "--out-dir", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = (output / "manifest.txt").read_text(encoding="utf-8")
    assert "Full/residual PageRank policy-path tests passed" in result.stdout
    assert "CLAIM_CLASS=functional_policy_path_not_synthesized_hardware" in manifest
    assert "regraph_pagerank_apply.cpp" in manifest
    assert (output / "full_pagerank_apply").is_file()
    assert (output / "residual_pagerank_apply").is_file()
    assert (output / "full_pagerank_source_prepare").is_file()
    assert (output / "residual_pagerank_source_prepare").is_file()

print("test_regraph_pagerank_apply_hls PASS")
