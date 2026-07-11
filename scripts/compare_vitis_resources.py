#!/usr/bin/env python3
"""Compare two evidence bundles produced by collect_vitis_evidence.py."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


RESOURCE_FIELDS = ("lut", "lut_as_mem", "reg", "bram", "uram", "dsp")
HLS_FIELDS = ("ff", "lut", "bram", "uram", "dsp")


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def to_number(value: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def delta(before: str, after: str) -> str:
    b = to_number(before)
    a = to_number(after)
    if b is None or a is None:
        return ""
    diff = a - b
    return str(int(diff)) if diff.is_integer() else f"{diff:.3f}"


def compare_by_key(
    before_rows: list[dict[str, str]],
    after_rows: list[dict[str, str]],
    key_fields: list[str],
    value_fields: tuple[str, ...],
    row_type: str,
) -> list[dict[str, Any]]:
    before = {tuple(row.get(field, "") for field in key_fields): row for row in before_rows}
    after = {tuple(row.get(field, "") for field in key_fields): row for row in after_rows}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        b_row = before.get(key, {})
        a_row = after.get(key, {})
        state = "unchanged"
        if key not in before:
            state = "added"
        elif key not in after:
            state = "removed"
        row: dict[str, Any] = {"row_type": row_type, "state": state}
        row.update({field: value for field, value in zip(key_fields, key)})
        for field in value_fields:
            b_val = b_row.get(field, "")
            a_val = a_row.get(field, "")
            d_val = delta(b_val, a_val)
            if d_val not in {"", "0"} and state == "unchanged":
                state = "changed"
            row[f"before_{field}"] = b_val
            row[f"after_{field}"] = a_val
            row[f"delta_{field}"] = d_val
        row["state"] = state
        rows.append(row)
    return rows


def top_hls_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    out = []
    for row in rows:
        if row.get("is_top_module") != "yes":
            continue
        key = (row.get("kernel", ""), row.get("compute_unit", ""), row.get("module", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path, help="Baseline evidence bundle.")
    parser.add_argument("--after", required=True, type=Path, help="New evidence bundle.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Directory for comparison TSVs.")
    parser.add_argument("--label", default="resource_compare", help="Summary label.")
    args = parser.parse_args()

    before = args.before.resolve()
    after = args.after.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    accel_delta = compare_by_key(
        read_tsv(before / "accelerator_util.tsv"),
        read_tsv(after / "accelerator_util.tsv"),
        ["name"],
        RESOURCE_FIELDS,
        "accelerator_util",
    )
    hls_delta = compare_by_key(
        top_hls_rows(read_tsv(before / "hls_area.tsv")),
        top_hls_rows(read_tsv(after / "hls_area.tsv")),
        ["kernel", "compute_unit", "module"],
        HLS_FIELDS,
        "hls_top_area",
    )
    cu_delta = compare_by_key(
        read_tsv(before / "link_kernels.tsv"),
        read_tsv(after / "link_kernels.tsv"),
        ["kernel"],
        ("cu_count",),
        "kernel_cu_count",
    )

    write_tsv(
        out_dir / "accelerator_util_delta.tsv",
        accel_delta,
        ["row_type", "state", "name", *[f"{prefix}_{field}" for field in RESOURCE_FIELDS for prefix in ("before", "after", "delta")]],
    )
    write_tsv(
        out_dir / "hls_top_area_delta.tsv",
        hls_delta,
        ["row_type", "state", "kernel", "compute_unit", "module", *[f"{prefix}_{field}" for field in HLS_FIELDS for prefix in ("before", "after", "delta")]],
    )
    write_tsv(
        out_dir / "kernel_cu_delta.tsv",
        cu_delta,
        ["row_type", "state", "kernel", "before_cu_count", "after_cu_count", "delta_cu_count"],
    )

    changed_accel = [row for row in accel_delta if row["state"] != "unchanged"]
    changed_hls = [row for row in hls_delta if row["state"] != "unchanged"]
    changed_cu = [row for row in cu_delta if row["state"] != "unchanged"]

    summary = [
        f"# {args.label}",
        "",
        f"- before: `{before}`",
        f"- after: `{after}`",
        f"- accelerator_util changes: {len(changed_accel)}",
        f"- hls_top_area changes: {len(changed_hls)}",
        f"- kernel CU count changes: {len(changed_cu)}",
        "",
        "Use this output as a review checklist: every non-zero delta should be either expected",
        "from the integration change or investigated before using the build in experiments.",
    ]
    if changed_accel[:20]:
        summary.extend(["", "## Accelerator Util Changes", "", "| Name | State | Delta LUT | Delta REG | Delta BRAM | Delta URAM | Delta DSP |", "| ---- | ----- | --------- | --------- | ---------- | ---------- | --------- |"])
        for row in changed_accel[:20]:
            summary.append(
                f"| {row.get('name')} | {row.get('state')} | {row.get('delta_lut')} | {row.get('delta_reg')} | {row.get('delta_bram')} | {row.get('delta_uram')} | {row.get('delta_dsp')} |"
            )
    if changed_cu[:20]:
        summary.extend(["", "## Kernel CU Count Changes", "", "| Kernel | State | Before | After | Delta |", "| ------ | ----- | ------ | ----- | ----- |"])
        for row in changed_cu[:20]:
            summary.append(
                f"| {row.get('kernel')} | {row.get('state')} | {row.get('before_cu_count')} | {row.get('after_cu_count')} | {row.get('delta_cu_count')} |"
            )
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n")

    print(f"Wrote comparison to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
