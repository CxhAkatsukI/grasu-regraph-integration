#!/usr/bin/env python3
"""Check source-level contracts before launching a long pure-pipeline build."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_pure_pipeline_status as audit_status  # noqa: E402


DEFAULT_REQUIRED_PROOFS = (
    "single_context_program",
    "adapter_receives_actual_pma_buffers",
    "pma_row_offset_begin_end_contract",
    "completion_token_barrier",
    "adapter_to_regraph_stream",
    "stream_burst_8_edge_contract",
    "unit_weight_sssp_packing",
    "timing_fields",
    "prepare_only_boundary_mode",
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def display_path(repo: Path, path: Path | None) -> str:
    if path is None:
        return "MISSING"
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def proof_paths(proof: dict[str, object]) -> str:
    paths = proof.get("paths")
    if paths is None:
        paths = [proof.get("path", "")]
    return "; ".join(str(path) for path in paths if path)


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("proof", "required", "ok", "contract", "paths"),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--label", default=None)
    parser.add_argument("--out-file", type=Path, default=None)
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        help="Require a specific proof name. May be repeated. Default: core pure-pipeline contracts.",
    )
    parser.add_argument("--list", action="store_true", help="List known proof names and exit.")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    label = args.label or audit_status.run_git(repo, ["rev-parse", "--short", "HEAD"])
    audit = audit_status.build_audit(repo, label)
    proofs: dict[str, dict[str, object]] = audit["source_proofs"]

    if args.list:
        for name in sorted(proofs):
            print(name)
        return 0

    required = tuple(args.require) if args.require else DEFAULT_REQUIRED_PROOFS
    unknown = [name for name in required if name not in proofs]
    if unknown:
        for name in unknown:
            print(f"UNKNOWN proof={name}", file=sys.stderr)
        return 2

    rows: list[dict[str, str]] = []
    failed: list[str] = []
    for name in sorted(proofs):
        proof = proofs[name]
        is_required = name in required
        ok = bool(proof.get("ok"))
        if is_required and not ok:
            failed.append(name)
        rows.append({
            "proof": name,
            "required": "yes" if is_required else "no",
            "ok": "yes" if ok else "no",
            "contract": str(proof.get("contract", "")),
            "paths": proof_paths(proof),
        })

    if args.out_file is None:
        out_file = repo / ".tmp_build" / "pure_pipeline_source_contracts" / f"source_contracts_{label}.tsv"
    else:
        out_file = args.out_file if args.out_file.is_absolute() else repo / args.out_file
    write_report(out_file, rows)

    print("pure_pipeline_source_contracts")
    print(f"repo={repo}")
    print(f"label={label}")
    print(f"out_file={display_path(repo, out_file)}")
    print(f"required_count={len(required)}")
    print(f"failed_count={len(failed)}")
    for row in rows:
        if row["required"] == "yes":
            print(f"proof={row['proof']} ok={row['ok']}")

    if failed:
        print("FAILED required_proofs=" + ",".join(failed), file=sys.stderr)
        return 3
    print("PASS source contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
