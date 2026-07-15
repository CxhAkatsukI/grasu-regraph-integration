#!/usr/bin/env python3

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_pure_pipeline_status import build_audit, status_counts  # noqa: E402


audit = build_audit(REPO_ROOT, "unit")
counts = status_counts(audit["requirements"])

assert audit["status_counts"] == counts
assert audit["completion_summary"]["status_counts"] == counts
assert audit["completion_summary"]["requirement_count"] == len(audit["requirements"])
assert audit["completion_summary"]["all_requirements_proven"] == all(
    req["status"] == "proven" for req in audit["requirements"]
)

missing_xclbins = [
    target
    for target, state in audit["targets"].items()
    if not state["xclbin"]["exists"]
]
assert audit["completion_summary"]["missing_xclbin_targets"] == missing_xclbins

for key in (
    "missing_xclbin_targets",
    "missing_stage0_gate_targets",
    "missing_stage0_full_targets",
    "missing_artifact_manifest_claims",
):
    assert isinstance(audit["completion_summary"][key], list)

assert "claim_report" in audit
assert "source_fingerprint_sha256" in audit["claim_report"]
assert "completion_claim" in audit["claim_report"]

for target, state in audit["targets"].items():
    assert "claim_status" in state
    assert "artifact_manifests" in state
    assert set(state["artifact_manifests"]) == {"build", "gate", "full"}
    claim = state["claim_status"]
    for level in ("build", "gate", "full"):
        if f"artifact_manifest_{level}" in claim.get(f"{level}_missing", []):
            assert (
                f"{target}:{level}"
                in audit["completion_summary"]["missing_artifact_manifest_claims"]
            )

print("test_audit_pure_pipeline_status PASS")
