#!/usr/bin/env python3
"""Collect timing-closure evidence from an isolated hardware relink packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_design_summary(path: Path) -> tuple[float, float]:
    in_summary = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "| Design Timing Summary" in line:
            in_summary = True
            continue
        if not in_summary:
            continue
        fields = line.split()
        if len(fields) >= 10 and NUMBER.fullmatch(fields[0]) and NUMBER.fullmatch(fields[1]):
            return float(fields[0]), float(fields[1])
    raise ValueError(f"could not parse Design Timing Summary: {path}")


def timing_reports(packet_root: Path) -> list[Path]:
    candidates = {
        path.resolve()
        for base in (packet_root / "reports", packet_root / "build")
        if base.exists()
        for path in base.rglob("*timing_summary*rpt")
        if path.is_file()
    }
    return sorted(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def collect(packet_root: Path) -> tuple[dict[str, object], int]:
    manifest_path = packet_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    xclbin = Path(manifest["output_xclbin"])
    reports = timing_reports(packet_root)
    parsed: list[tuple[Path, float, float]] = []
    parse_errors: list[str] = []
    for report in reports:
        try:
            wns, tns = parse_design_summary(report)
            parsed.append((report, wns, tns))
        except ValueError as error:
            parse_errors.append(str(error))
    selected = parsed[-1] if parsed else None
    wns = selected[1] if selected else None
    tns = selected[2] if selected else None
    timing_closed = wns is not None and tns is not None and wns >= 0.0 and tns >= 0.0
    xclbin_present = xclbin.is_file()
    passed = xclbin_present and timing_closed
    result: dict[str, object] = {
        "schema": 1,
        "claim_class": "routed_timing_closed" if passed else "relink_not_accepted",
        "passed": passed,
        "packet_root": str(packet_root),
        "profile": manifest["profile"],
        "kernel_frequency_mhz": manifest["kernel_frequency_mhz"],
        "source_git_head": manifest["source_git_head"],
        "input_xo_count": manifest["input_xo_count"],
        "timing_report_count": len(reports),
        "parsed_timing_report_count": len(parsed),
        "selected_timing_report": str(selected[0]) if selected else None,
        "wns_ns": wns,
        "tns_ns": tns,
        "timing_closed": timing_closed,
        "xclbin": str(xclbin),
        "xclbin_present": xclbin_present,
        "xclbin_sha256": sha256(xclbin) if xclbin_present else None,
        "xclbin_bytes": xclbin.stat().st_size if xclbin_present else None,
        "parse_errors": parse_errors,
    }
    (packet_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows = ["field\tvalue"]
    for key in (
        "claim_class",
        "passed",
        "profile",
        "kernel_frequency_mhz",
        "wns_ns",
        "tns_ns",
        "timing_closed",
        "xclbin_present",
        "xclbin_sha256",
        "selected_timing_report",
    ):
        rows.append(f"{key}\t{result[key]}")
    (packet_root / "result.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return result, 0 if passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-root", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    collected, status = collect(args.packet_root.resolve())
    print(json.dumps(collected, indent=2, sort_keys=True))
    raise SystemExit(status)
