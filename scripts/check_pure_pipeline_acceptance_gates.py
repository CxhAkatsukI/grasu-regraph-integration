#!/usr/bin/env python3
"""Check a pure-pipeline launch packet acceptance_gates.tsv file."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable


EXPECTED_CASES = {
    "tiny_chain_v16",
    "tiny_star_v16_u12",
    "tiny_spread_v16_u8",
    "tiny_hotdst_v64_u32",
}
TIMING_KEYS = ("grasu_ms", "barrier_ms", "adapter_ms", "lksg_ms", "apply_ms", "event_e2e_ms")
COMPARISON_TIMING_FIELDS = (
    "pure_grasu_ms",
    "pure_barrier_ms",
    "pure_adapter_ms",
    "pure_lksg_ms",
    "pure_apply_ms",
    "pure_event_e2e_ms",
)
PRELAUNCH_GATES = {"source_fingerprints", "source_contracts", "readiness", "launch_command"}
BUNDLE_FILES = (
    "summary.md",
    "bundle_manifest.json",
    "requirement_matrix.tsv",
    "target_matrix.tsv",
    "case_target_matrix.tsv",
    "case_matrix.tsv",
    "input_identity_matrix.tsv",
    "source_proof_matrix.tsv",
    "artifact_matrix.tsv",
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(repo: Path, text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else repo / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_kv_line(line: str) -> dict[str, str]:
    return {key: value for key, value in re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line or "")}


def file_ready(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing file"
    size = path.stat().st_size
    if size <= 0:
        return False, "empty file"
    return True, f"exists size={size} sha256={sha256(path)}"


def check_source_fingerprints(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    rows = read_tsv(path)
    if not rows:
        return False, "no fingerprint rows"
    bad: list[str] = []
    for row in rows:
        role = row.get("role", "")
        tree_sha = row.get("tree_sha256", "")
        if row.get("status") != "present" or not re.fullmatch(r"[0-9a-f]{64}", tree_sha):
            bad.append(role or "<missing-role>")
            continue
        files_path = path.parent / f"{role}.files"
        hashes_path = path.parent / f"{role}.sha256s"
        files_ok, _ = file_ready(files_path)
        hashes_ok, _ = file_ready(hashes_path)
        if not files_ok or not hashes_ok or sha256(hashes_path) != tree_sha:
            bad.append(role or "<missing-role>")
    if bad:
        return False, "bad fingerprint rows=" + ",".join(bad)
    return True, f"{len(rows)} source fingerprints present with sidecar hashes"


def check_source_contracts(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    rows = read_tsv(path)
    required = [row for row in rows if row.get("required") == "yes"]
    failed = [row.get("proof", "") for row in required if row.get("ok") != "yes"]
    if not required:
        return False, "no required source-contract proofs"
    if failed:
        return False, "failed proofs=" + ",".join(failed)
    return True, f"{len(required)} required source-contract proofs ok"


def check_readiness(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    kv: dict[str, str] = {}
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        if "=" in line and not line.startswith((" ", "\t")):
            key, value = line.split("=", 1)
            kv[key] = value
    if kv.get("ready") != "yes":
        return False, f"ready={kv.get('ready', 'missing')} blocking_count={kv.get('blocking_count', 'missing')}"
    if kv.get("blocking_count") not in ("0", None):
        return False, f"blocking_count={kv.get('blocking_count')}"
    return True, f"ready=yes warning_count={kv.get('warning_count', 'unknown')}"


def check_launch_command(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    text = path.read_text(encoding="ascii", errors="replace")
    if "run_pure_pipeline_target_flow.sh" not in text:
        return False, "missing run_pure_pipeline_target_flow.sh"
    if "--target" not in text or "--label" not in text:
        return False, "missing target or label argument"
    if not path.stat().st_mode & 0o111:
        return False, "launch command is not executable"
    return True, "launch command is executable and invokes target flow"


def check_plain_artifact(path: Path) -> tuple[bool, str]:
    return file_ready(path)


def check_xclbin_contract(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    rows = read_tsv(path)
    failed = [row.get("check", "") for row in rows if row.get("ok") != "yes"]
    if not rows:
        return False, "no xclbin-contract rows"
    if failed:
        return False, "failed checks=" + ",".join(failed)
    return True, f"{len(rows)} xclbin-contract checks ok"


def smoke_ok(row: dict[str, str]) -> tuple[bool, str]:
    if row.get("status") != "PASS":
        return False, "status_not_PASS"
    if "mismatches=0" not in row.get("result_line", ""):
        return False, "mismatches_not_zero"
    timing = parse_kv_line(row.get("timing_line", ""))
    missing_timing = [key for key in TIMING_KEYS if key not in timing]
    if missing_timing:
        return False, "missing_timing=" + ",".join(missing_timing)
    return True, "ok"


def check_gate_smoke(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    rows = read_tsv(path)
    bad = []
    for row in rows:
        row_ok, row_detail = smoke_ok(row)
        if not row_ok:
            bad.append(f"{row.get('case', 'unknown')}:{row_detail}")
    if not rows:
        return False, "no smoke rows"
    if bad:
        return False, "; ".join(bad)
    return True, f"{len(rows)} gate smoke rows PASS"


def check_full_smoke(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    rows = read_tsv(path)
    by_case = {row.get("case", ""): row for row in rows}
    missing = sorted(EXPECTED_CASES - set(by_case))
    bad = []
    for case in sorted(EXPECTED_CASES & set(by_case)):
        row_ok, row_detail = smoke_ok(by_case[case])
        if not row_ok:
            bad.append(f"{case}:{row_detail}")
    if missing:
        bad.append("missing_cases=" + ",".join(missing))
    if bad:
        return False, "; ".join(bad)
    return True, "all four smoke families PASS with timing fields"


def check_same_input_compare(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    rows = read_tsv(path)
    by_case = {row.get("case", ""): row for row in rows}
    missing = sorted(EXPECTED_CASES - set(by_case))
    bad = []
    for case in sorted(EXPECTED_CASES & set(by_case)):
        row = by_case[case]
        for field in ("host_status", "spine_status", "pure_status"):
            if row.get(field) != "PASS":
                bad.append(f"{case}:{field}={row.get(field, '')}")
        for field in ("host_zero_cost_ms", *COMPARISON_TIMING_FIELDS):
            if not row.get(field):
                bad.append(f"{case}:missing_{field}")
    if missing:
        bad.append("missing_cases=" + ",".join(missing))
    if bad:
        return False, "; ".join(bad)
    return True, "same-input comparison covers all four smoke cases"


def check_requirement_audit(path: Path) -> tuple[bool, str]:
    ok, detail = file_ready(path)
    if not ok:
        return ok, detail
    try:
        data = json.loads(path.read_text(encoding="ascii", errors="replace"))
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    requirements = data.get("requirements", [])
    if len(requirements) < 10:
        return False, f"expected >=10 requirements, saw {len(requirements)}"
    counts: dict[str, int] = {}
    for requirement in requirements:
        counts[requirement.get("status", "unknown")] = counts.get(requirement.get("status", "unknown"), 0) + 1
    return True, "requirement statuses=" + json.dumps(counts, sort_keys=True)


def check_evidence_bundle(path: Path) -> tuple[bool, str]:
    if not path.is_dir():
        return False, "missing bundle directory"
    missing = [name for name in BUNDLE_FILES if not (path / name).is_file()]
    empty = [name for name in BUNDLE_FILES if (path / name).is_file() and (path / name).stat().st_size <= 0]
    if missing or empty:
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if empty:
            details.append("empty=" + ",".join(empty))
        return False, "; ".join(details)
    return True, f"{len(BUNDLE_FILES)} bundle files present"


CHECKERS: dict[str, Callable[[Path], tuple[bool, str]]] = {
    "source_fingerprints": check_source_fingerprints,
    "source_contracts": check_source_contracts,
    "readiness": check_readiness,
    "launch_command": check_launch_command,
    "compile_log": check_plain_artifact,
    "link_log": check_plain_artifact,
    "target_xclbin": check_plain_artifact,
    "xclbin_contract": check_xclbin_contract,
    "gate_smoke": check_gate_smoke,
    "full_smoke": check_full_smoke,
    "same_input_compare": check_same_input_compare,
    "requirement_audit": check_requirement_audit,
    "evidence_bundle": check_evidence_bundle,
}


def row_status(repo: Path, row: dict[str, str], mode: str) -> dict[str, str]:
    gate = row.get("gate", "")
    required = row.get("required", "")
    evidence_path = row.get("evidence_path", "")
    should_check = required == "yes" and (mode == "postrun" or gate in PRELAUNCH_GATES)
    if required != "yes":
        status = "SKIP"
        detail = "required=no"
    elif not should_check:
        status = "PENDING"
        detail = "postrun gate not checked in prelaunch mode"
    else:
        checker = CHECKERS.get(gate)
        if checker is None:
            status = "FAIL"
            detail = "unknown gate checker"
        else:
            ok, detail = checker(resolve_path(repo, evidence_path))
            status = "PASS" if ok else "FAIL"
    return {
        "gate": gate,
        "required": required,
        "mode": mode,
        "status": status,
        "evidence_path": evidence_path,
        "detail": detail,
    }


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("gate", "required", "mode", "status", "evidence_path", "detail"),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--acceptance-gates", type=Path, default=None)
    parser.add_argument("--packet-dir", type=Path, default=None)
    parser.add_argument("--mode", choices=("prelaunch", "postrun"), default="prelaunch")
    parser.add_argument("--out-file", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    if args.acceptance_gates is None and args.packet_dir is None:
        print("one of --acceptance-gates or --packet-dir is required", file=sys.stderr)
        return 2
    gates_path = args.acceptance_gates or args.packet_dir / "acceptance_gates.tsv"
    gates_path = resolve_path(repo, str(gates_path)).resolve()
    if not gates_path.is_file():
        print(f"missing acceptance gates file: {gates_path}", file=sys.stderr)
        return 1

    rows = [row_status(repo, row, args.mode) for row in read_tsv(gates_path)]
    if args.out_file is None:
        out_file = gates_path.parent / f"acceptance_check_{args.mode}.tsv"
    else:
        out_file = resolve_path(repo, str(args.out_file))
    write_report(out_file, rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(f"acceptance_gates={gates_path}")
    print(f"mode={args.mode}")
    print(f"out_file={out_file}")
    print("status_counts=" + json.dumps(counts, sort_keys=True))
    failures = [row["gate"] for row in rows if row["status"] == "FAIL"]
    if failures:
        print("FAILED gates=" + ",".join(failures), file=sys.stderr)
        return 3
    print("PASS acceptance gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
