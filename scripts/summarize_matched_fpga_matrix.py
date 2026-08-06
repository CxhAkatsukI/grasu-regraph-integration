#!/usr/bin/env python3
"""Summarize correctness-gated, matched Spine versus G+R FPGA runs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FIELDS = (
    "case",
    "algorithm",
    "graph",
    "gr_status",
    "spine_status",
    "comparison_status",
    "gr_event_e2e_ms",
    "gr_setup_inclusive_ms",
    "spine_dynamic_kernel_ms",
    "spine_dynamic_device_e2e_ms",
    "spine_dynamic_setup_inclusive_ms",
    "kernel_speedup_gr_over_spine",
    "device_e2e_speedup_gr_over_spine",
    "setup_speedup_gr_over_spine",
)


def parse_key_values(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in line.split()[1:]:
        if "=" not in field:
            continue
        key, value = field.split("=", 1)
        result[key] = value
    return result


def last_matching_line(path: Path, marker: str) -> str:
    matches = [line for line in path.read_text().splitlines() if line.startswith(marker)]
    return matches[-1] if matches else ""


def read_matrix(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def one_log(root: Path, pattern: str) -> Path | None:
    logs = sorted(root.rglob(pattern))
    return logs[-1] if logs else None


def safe_ratio(numerator: str, denominator: str) -> str:
    try:
        den = float(denominator)
        if den <= 0:
            return ""
        return f"{float(numerator) / den:.6f}"
    except (TypeError, ValueError):
        return ""


def summarize(matrix: Path, run_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case in read_matrix(matrix):
        case_root = run_root / case["case"]
        gr_log = one_log(case_root / "grasu_regraph", "run.log")
        spine_log = one_log(case_root / "spine", "dynamic_*.log")

        gr_result = (
            parse_key_values(last_matching_line(gr_log, "PMA_NATIVE_HW_RUN "))
            if gr_log
            else {}
        )
        # PMA_NATIVE_HW_RUN is emitted by the wrapper, not run.log. The
        # architecture host's result line is sufficient for the correctness
        # gate; the wrapper exit status is recorded separately by the driver.
        gr_pass = False
        gr_timing: dict[str, str] = {}
        if gr_log:
            gr_pass = any(
                "_RESULT " in line
                and "status=PASS" in line
                and "conversion_cost=absent" in line
                for line in gr_log.read_text().splitlines()
            )
            timing_lines = [
                line
                for line in gr_log.read_text().splitlines()
                if "_TIMING " in line
            ]
            if timing_lines:
                gr_timing = parse_key_values(timing_lines[-1])

        spine_pass = False
        spine_timing: dict[str, str] = {}
        if spine_log:
            text = spine_log.read_text()
            spine_pass = (
                "SPINE_DYNAMIC_MAINT_PASS" in text
                and "PARTITIONED_ALGORITHM_PASS" in text
                and "PARTITIONED_ALGORITHMS_FAIL" not in text
            )
            timing_line = last_matching_line(spine_log, "SPINE_HW_TIMING ")
            if timing_line:
                spine_timing = parse_key_values(timing_line)

        # Weighted SSSP/CC call the OpenCL event envelope event_e2e_ms;
        # PageRank hosts call the same update-to-final-kernel window
        # device_e2e_ms. Normalize the protocol names without changing the
        # measured value or accepting a setup-inclusive fallback.
        gr_kernel = gr_timing.get("event_e2e_ms", "") or gr_timing.get(
            "device_e2e_ms", ""
        )
        spine_kernel = spine_timing.get("dynamic_kernel_ms", "")
        spine_device = spine_timing.get("dynamic_device_e2e_ms", "")
        gr_setup = gr_timing.get("setup_inclusive_ms", "")
        spine_setup = spine_timing.get("dynamic_setup_inclusive_ms", "")
        admitted = gr_pass and spine_pass and bool(gr_kernel) and bool(spine_kernel)
        rows.append(
            {
                "case": case["case"],
                "algorithm": case["algorithm"],
                "graph": case["graph"],
                "gr_status": "PASS" if gr_pass else "FAIL",
                "spine_status": "PASS" if spine_pass else "FAIL",
                "comparison_status": "ADMITTED" if admitted else "REJECTED",
                "gr_event_e2e_ms": gr_kernel,
                "gr_setup_inclusive_ms": gr_setup,
                "spine_dynamic_kernel_ms": spine_kernel,
                "spine_dynamic_device_e2e_ms": spine_device,
                "spine_dynamic_setup_inclusive_ms": spine_setup,
                "kernel_speedup_gr_over_spine": (
                    safe_ratio(gr_kernel, spine_kernel) if admitted else ""
                ),
                "device_e2e_speedup_gr_over_spine": (
                    safe_ratio(gr_kernel, spine_device)
                    if admitted and spine_device
                    else ""
                ),
                "setup_speedup_gr_over_spine": (
                    safe_ratio(gr_setup, spine_setup)
                    if admitted and gr_setup and spine_setup
                    else ""
                ),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = summarize(args.matrix, args.run_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    admitted = sum(row["comparison_status"] == "ADMITTED" for row in rows)
    print(f"MATCHED_FPGA_SUMMARY rows={len(rows)} admitted={admitted} output={args.output}")


if __name__ == "__main__":
    main()
