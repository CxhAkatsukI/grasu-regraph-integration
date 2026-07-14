#!/usr/bin/env python3
"""Check a run root against pure_stage0 input_identity.tsv."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


IDENTITY_FIELDS = (
    "family",
    "vertices",
    "static_edges",
    "update_edges",
    "final_edges",
    "source",
    "supersteps",
    "default_weight",
)

HASH_FIELDS = (
    ("graph", "graph_sha256"),
    ("result", "result_sha256"),
    ("regraph_sssp_edges", "generated_regraph_sssp_edges_sha256"),
    ("expected", "expected_sha256"),
    ("metadata", "metadata_sha256"),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open("r", encoding="ascii", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
    return values


def resolve_identity_path(text: str) -> Path:
    path = Path(text)
    if path.is_absolute():
        return path.resolve()
    return (repo_root() / path).resolve()


def same_path(left: str, right: str) -> bool:
    return resolve_identity_path(left) == Path(right).resolve()


def add_report(report: list[dict[str, str]], case: str, check: str, ok: bool, detail: str) -> None:
    report.append({"case": case, "check": check, "ok": "yes" if ok else "no", "detail": detail})


def summary_cases(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return {row.get("case", "") for row in read_tsv(path) if row.get("case")}


def check_case(case: str, identity: dict[str, str], env: dict[str, str], report: list[dict[str, str]]) -> None:
    for field in IDENTITY_FIELDS:
        actual = env.get(field, "")
        expected = identity.get(field, "")
        add_report(report, case, field, actual == expected, f"expected={expected} actual={actual}")

    path_checks = (
        ("graph", "graph"),
        ("result", "result"),
        ("regraph_sssp_edges", "generated_regraph_sssp_edges"),
        ("expected", "expected"),
        ("metadata", "metadata"),
    )
    for identity_field, env_field in path_checks:
        actual = env.get(env_field, "")
        expected = identity.get(identity_field, "")
        ok = bool(actual and expected and same_path(expected, actual))
        add_report(report, case, f"{identity_field}_path", ok, f"expected={expected} actual={actual}")

    for identity_hash, env_hash in HASH_FIELDS:
        expected = identity.get(identity_hash + "_sha256", "")
        actual = env.get(env_hash, "")
        add_report(report, case, env_hash, actual == expected, f"expected={expected} actual={actual}")


def write_report(path: Path, report: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("case", "check", "ok", "detail"),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-identity", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()

    identity_rows = {row["case"]: row for row in read_tsv(args.input_identity)}
    report: list[dict[str, str]] = []
    run_root = args.run_root.resolve()
    seen: set[str] = set()

    for case, identity in sorted(identity_rows.items()):
        case_env = run_root / case / "case.env"
        if not case_env.is_file():
            add_report(report, case, "case_env", False, f"missing {case_env}")
            continue
        seen.add(case)
        add_report(report, case, "case_env", True, str(case_env))
        check_case(case, identity, read_env(case_env), report)

    extra_case_dirs = sorted(path.name for path in run_root.iterdir() if path.is_dir() and path.name not in identity_rows)
    for case in extra_case_dirs:
        add_report(report, case, "extra_case_dir", False, str(run_root / case))

    if args.summary is not None:
        cases = summary_cases(args.summary.resolve())
        for case in sorted(identity_rows):
            add_report(report, case, "summary_case", case in cases, str(args.summary))
        for case in sorted(cases - set(identity_rows)):
            add_report(report, case, "summary_extra_case", False, str(args.summary))

    write_report(args.out_file, report)
    failures = [row for row in report if row["ok"] != "yes"]
    print(f"checks={len(report)} failures={len(failures)} report={args.out_file}")
    if failures:
        for row in failures[:20]:
            print(f"FAIL case={row['case']} check={row['check']} {row['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
