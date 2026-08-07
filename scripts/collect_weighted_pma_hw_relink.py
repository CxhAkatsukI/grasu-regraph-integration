#!/usr/bin/env python3
"""Collect timing-closure evidence from an isolated hardware relink packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")
SCALABLE_CLOCK = re.compile(
    r"^\s*(Name|Type|Frequency):\s*(.*?)\s*$", re.IGNORECASE
)


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


def parse_scalable_clocks(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    clocks: list[dict[str, object]] = []
    current: dict[str, object] = {}
    in_section = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip() == "Scalable Clocks":
            in_section = True
            continue
        if in_section and line.strip() == "System Clocks":
            break
        if not in_section:
            continue
        match = SCALABLE_CLOCK.match(line)
        if match is None:
            continue
        key, value = match.groups()
        key = key.lower()
        if key == "name":
            if current:
                clocks.append(current)
            current = {"name": value}
        elif key == "type":
            current["type"] = value.upper()
        elif key == "frequency":
            frequency = re.search(r"\d+(?:\.\d+)?", value)
            if frequency is not None:
                current["frequency_mhz"] = float(frequency.group())
    if current:
        clocks.append(current)
    return clocks


def collect(
    packet_root: Path, *, accept_platform_autoscale: bool = False
) -> tuple[dict[str, object], int]:
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
    xclbin_info = Path(str(xclbin) + ".info")
    scalable_clocks = parse_scalable_clocks(xclbin_info)
    requested_kernel_mhz = float(manifest["kernel_frequency_mhz"])
    data_clock = next(
        (
            clock
            for clock in scalable_clocks
            if clock.get("type") == "DATA" or clock.get("name") == "DATA_CLK"
        ),
        None,
    )
    system_clock = next(
        (clock for clock in scalable_clocks if clock.get("type") == "SYSTEM"),
        None,
    )
    selected_kernel_mhz = (
        float(data_clock["frequency_mhz"])
        if data_clock is not None and "frequency_mhz" in data_clock
        else None
    )
    selected_system_mhz = (
        float(system_clock["frequency_mhz"])
        if system_clock is not None and "frequency_mhz" in system_clock
        else None
    )
    kernel_target_met = (
        selected_kernel_mhz is not None
        and selected_kernel_mhz + 1.0e-9 >= requested_kernel_mhz
    )
    platform_autoscale_accepted = (
        accept_platform_autoscale
        and not timing_closed
        and xclbin_present
        and kernel_target_met
        and selected_system_mhz is not None
    )
    passed = xclbin_present and (timing_closed or platform_autoscale_accepted)
    if timing_closed and xclbin_present:
        claim_class = "routed_timing_closed"
    elif platform_autoscale_accepted:
        claim_class = "routed_kernel_target_met_platform_autoscaled"
    else:
        claim_class = "relink_not_accepted"
    result: dict[str, object] = {
        "schema": 1,
        "claim_class": claim_class,
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
        "accept_platform_autoscale": accept_platform_autoscale,
        "platform_autoscale_accepted": platform_autoscale_accepted,
        "kernel_target_met": kernel_target_met,
        "selected_kernel_frequency_mhz": selected_kernel_mhz,
        "selected_system_frequency_mhz": selected_system_mhz,
        "scalable_clocks": scalable_clocks,
        "xclbin_info": str(xclbin_info) if xclbin_info.is_file() else None,
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
        "platform_autoscale_accepted",
        "kernel_target_met",
        "selected_kernel_frequency_mhz",
        "selected_system_frequency_mhz",
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
    parser.add_argument(
        "--accept-platform-autoscale",
        action="store_true",
        help=(
            "accept a routed xclbin when DATA_CLK meets the requested kernel "
            "frequency and only a scalable platform clock is reduced"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    collected, status = collect(
        args.packet_root.resolve(),
        accept_platform_autoscale=args.accept_platform_autoscale,
    )
    print(json.dumps(collected, indent=2, sort_keys=True))
    raise SystemExit(status)
