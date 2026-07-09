#!/usr/bin/env python3
"""Summarize one or more GraSU -> ReGraph chain result directories."""

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
    "converted_edges",
    "grasu_ms",
    "grasu_mups",
    "regraph_vertices",
    "regraph_edges",
    "regraph_e2e_ms",
    "regraph_mteps",
    "processed_edges",
    "graph_edges",
    "result_dir",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="ascii", errors="replace") if path.exists() else ""


def first_match(text: str, pattern: str, default: str = "") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else default


def summarize_dir(result_dir: Path) -> dict:
    generate = read_text(result_dir / "generate.log")
    grasu = read_text(result_dir / "grasu.log")
    convert = read_text(result_dir / "convert.log")
    regraph = read_text(result_dir / "regraph.log")
    wall = read_text(result_dir / "wall_time.tsv")
    manifest = read_text(result_dir / "manifest.env")

    case = first_match(manifest, r"^case=(.+)$") or first_match(generate, r"case=([^\s]+)")

    row = {
        "case": case,
        "status": "FAIL",
        "wall_seconds": first_match(wall, r"wall_seconds\s+([0-9.]+)"),
        "vertices": first_match(generate, r"vertices=([0-9]+)"),
        "static_edges": first_match(generate, r"static=([0-9]+)"),
        "update_edges": first_match(generate, r"updates=([0-9]+)"),
        "final_edges": first_match(generate, r"final=([0-9]+)"),
        "converted_edges": first_match(convert, r"converted_edges=([0-9]+)"),
        "grasu_ms": first_match(grasu, r"time is ([0-9.eE+-]+) ms"),
        "grasu_mups": first_match(grasu, r"throughput is ([0-9.eE+-]+) M updates per second"),
        "regraph_vertices": first_match(regraph, r"vertex num: ([0-9]+)"),
        "regraph_edges": first_match(regraph, r"edge num: ([0-9]+)"),
        "regraph_e2e_ms": first_match(regraph, r"e2e: ([0-9.eE+-]+) ms"),
        "regraph_mteps": first_match(regraph, r"Throught: ([0-9.eE+-]+) MTEPS"),
        "processed_edges": first_match(regraph, r"Processed edges: ([0-9]+)"),
        "graph_edges": first_match(regraph, r"Graph edges: ([0-9]+)"),
        "result_dir": str(result_dir),
    }

    grasu_ok = "check result passed" in grasu
    convert_ok = bool(row["converted_edges"])
    regraph_ok = "Device[0]: program successful!" in regraph and bool(row["processed_edges"])
    if grasu_ok and convert_ok and regraph_ok:
        row["status"] = "PASS"
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dirs", nargs="+")
    parser.add_argument("--no-header", action="store_true")
    args = parser.parse_args()

    if not args.no_header:
        print("\t".join(COLUMNS))
    for result_dir_s in args.result_dirs:
        row = summarize_dir(Path(result_dir_s))
        print("\t".join(row.get(col, "") for col in COLUMNS))


if __name__ == "__main__":
    main()

