#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check_grasu_degree_update.sh"


with tempfile.TemporaryDirectory() as temp_name:
    output = Path(temp_name) / "degree-update"
    result = subprocess.run(
        [str(CHECK), "--out-dir", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = (output / "manifest.txt").read_text(encoding="utf-8")
    assert "GraSU ordered degree-update protocol test passed" in result.stdout
    assert "CLAIM_CLASS=functional_protocol_test_not_synthesized_hardware" in manifest
    assert "kernel_config.h" in manifest
    assert (output / "grasu_degree_update_tb").is_file()

print("test_grasu_degree_update_hls PASS")
