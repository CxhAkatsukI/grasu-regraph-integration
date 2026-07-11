#!/usr/bin/env python3
"""Summarize one or more Spine built-in scenario result directories."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


COLUMNS = [
    "case",
    "status",
    "scenario_tag",
    "wall_seconds",
    "vertices",
    "input_edges",
    "batch_edges",
    "source_count",
    "hot_edges",
    "cold_edges",
    "traversed_edges",
    "maint_ms",
    "conv_ms",
    "kernel_e2e_ms",
    "kernel_mteps",
    "errors",
    "args",
    "result_dir",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="ascii", errors="replace") if path.exists() else ""


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key] = value
    return out


def first_match(text: str, pattern: str, default: str = "") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else default


def parse_result_line(text: str) -> tuple[str, dict[str, str]]:
    for line in text.splitlines():
        if not line.startswith("PARTITIONED_CSR_E2E_"):
            continue
        parts = line.split()
        tag = parts[0]
        fields: dict[str, str] = {"status": parts[1] if len(parts) > 1 else ""}
        for part in parts[2:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            fields[key] = value
        return tag, fields
    return "", {}


def summarize_dir(result_dir: Path) -> dict[str, str]:
    env = read_env(result_dir / "case.env")
    log = read_text(result_dir / "spine.log")
    wall = read_text(result_dir / "wall_time.tsv")
    tag, fields = parse_result_line(log)

    status = fields.get("status", "FAIL")
    if env.get("dry_run", "0") == "1":
        status = "DRY_RUN"

    return {
        "case": env.get("case", result_dir.name),
        "status": status,
        "scenario_tag": tag,
        "wall_seconds": first_match(wall, r"wall_seconds\s+([0-9.]+)"),
        "vertices": fields.get("vertices", ""),
        "input_edges": fields.get("input_edges", ""),
        "batch_edges": fields.get("batch_edges", ""),
        "source_count": fields.get("source_count", ""),
        "hot_edges": fields.get("hot_edges", ""),
        "cold_edges": fields.get("cold_edges", ""),
        "traversed_edges": fields.get("traversed_edges", ""),
        "maint_ms": fields.get("maint_ms", ""),
        "conv_ms": fields.get("conv_ms", ""),
        "kernel_e2e_ms": fields.get("kernel_e2e_ms", ""),
        "kernel_mteps": fields.get("kernel_mteps", ""),
        "errors": fields.get("errors", ""),
        "args": env.get("args", ""),
        "result_dir": str(result_dir),
    }


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
