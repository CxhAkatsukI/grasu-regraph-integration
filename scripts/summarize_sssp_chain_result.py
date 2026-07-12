#!/usr/bin/env python3
"""Summarize GraSU -> ReGraph SSSP chain result directories."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


COLUMNS = [
    "case",
    "status",
    "wall_seconds",
    "vertices",
    "static_edges",
    "update_edges",
    "final_edges",
    "source",
    "supersteps",
    "converted_edges",
    "grasu_ms",
    "grasu_mups",
    "regraph_e2e_ms",
    "regraph_mteps",
    "processed_edges",
    "graph_edges",
    "mismatch_count",
    "result_dir",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="ascii", errors="replace") if path.exists() else ""


def first_match(text: str, pattern: str, default: str = "") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else default


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key] = value
    return out


def summarize_dir(result_dir: Path) -> dict[str, str]:
    env = read_env(result_dir / "case.env")
    wall = read_text(result_dir / "wall_time.tsv")
    grasu = read_text(result_dir / "grasu.log")
    convert = read_text(result_dir / "convert.log")
    regraph = read_text(result_dir / "regraph.log")

    mismatch_count = len(re.findall(r"error: mismatch on destination vertex", regraph))
    mismatch_count += len(re.findall(r"This iteration has [1-9][0-9]* errors", regraph))

    row = {
        "case": env.get("case", result_dir.name),
        "status": "FAIL",
        "wall_seconds": first_match(wall, r"wall_seconds\s+([0-9.]+)"),
        "vertices": env.get("vertices", ""),
        "static_edges": env.get("static_edges", ""),
        "update_edges": env.get("update_edges", ""),
        "final_edges": env.get("final_edges", ""),
        "source": env.get("source", ""),
        "supersteps": env.get("supersteps", ""),
        "converted_edges": first_match(convert, r"converted_edges=([0-9]+)"),
        "grasu_ms": first_match(grasu, r"time is ([0-9.eE+-]+) ms"),
        "grasu_mups": first_match(grasu, r"throughput is ([0-9.eE+-]+) M updates per second"),
        "regraph_e2e_ms": first_match(regraph, r"e2e: ([0-9.eE+-]+) ms"),
        "regraph_mteps": first_match(regraph, r"Throught: ([0-9.eE+-]+) MTEPS"),
        "processed_edges": first_match(regraph, r"Processed edges: ([0-9]+)"),
        "graph_edges": first_match(regraph, r"Graph edges: ([0-9]+)"),
        "mismatch_count": str(mismatch_count),
        "result_dir": str(result_dir),
    }

    grasu_required = env.get("skip_grasu", "0") != "1"
    grasu_ok = (not grasu_required) or ("check result passed" in grasu)
    convert_ok = bool(row["converted_edges"])
    if env.get("dry_run", "0") == "1" and convert_ok:
        row["status"] = "DRY_RUN"
        return row

    regraph_programmed = "Device[0]: program successful!" in regraph
    regraph_skip_verify = env.get("regraph_skip_verify", "0") == "1"
    regraph_ok = regraph_programmed and mismatch_count == 0
    if regraph_skip_verify:
        regraph_ok = regraph_ok and "Skipping hardware result verification" in regraph
        if grasu_ok and convert_ok and regraph_ok:
            row["status"] = "PERF_ONLY"
        return row

    regraph_ok = regraph_ok and bool(row["processed_edges"])
    if grasu_ok and convert_ok and regraph_ok:
        row["status"] = "PASS"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dirs", nargs="+")
    parser.add_argument("--no-header", action="store_true")
    args = parser.parse_args()

    if not args.no_header:
        print("\t".join(COLUMNS))
    for result_dir_s in args.result_dirs:
        row = summarize_dir(Path(result_dir_s))
        print("\t".join(row.get(col, "") for col in COLUMNS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
