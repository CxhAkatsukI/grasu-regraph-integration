#!/usr/bin/env python3
"""Collect reproducible Vitis/Vivado artifact and resource evidence.

The integration experiment needs more than "xclbin exists": we need stable
records for CU counts, HBM/SLR placement, kernel-level resources, SLR pressure,
and timing so that GraSU, ReGraph, and a future combined build can be compared
without hand-copying report snippets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Iterable


RESOURCE_COLUMNS = ("lut", "lut_as_mem", "reg", "bram", "uram", "dsp")
DEFAULT_EXCLUDE_DIRS = {"evidence", ".tmp_doc", "phase6_results", "__pycache__"}
KEY_SLR_ROWS = {
    "CLB",
    "CLB LUTs",
    "LUT as Logic",
    "LUT as Memory",
    "CLB Registers",
    "Block RAM Tile",
    "URAM",
    "DSPs",
}


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        parts = path.parts
    return any(part in DEFAULT_EXCLUDE_DIRS for part in parts[:-1])


def discover(root: Path, patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(path for path in root.rglob(pattern) if not is_excluded(path, root))
    return sorted({path.resolve() for path in paths if path.is_file()})


def copy_report(path: Path, out_dir: Path, build_root: Path) -> str:
    copied = out_dir / "copied_reports" / relpath(path, build_root)
    copied.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, copied)
    return str(copied)


def extract_json_entries(link_summary: Path) -> list[dict[str, Any]]:
    text = link_summary.read_text(errors="replace")
    entries: list[dict[str, Any]] = []
    for match in re.finditer(r"<ENTRY>\s*(.*?)\s*</ENTRY>", text, re.S):
        blob = match.group(1).strip()
        try:
            entries.append(json.loads(blob))
        except json.JSONDecodeError:
            continue
    return entries


def parse_link_summary(link_summary: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    kernel_rows: list[dict[str, Any]] = []
    connectivity_rows: list[dict[str, Any]] = []
    command_rows: list[dict[str, Any]] = []

    for entry in extract_json_entries(link_summary):
        build_step = entry.get("buildStep")
        if build_step:
            command = build_step.get("commandLine", "")
            if command:
                command_rows.append(
                    {
                        "source": str(link_summary),
                        "entry_type": entry.get("type", ""),
                        "step_name": build_step.get("name", ""),
                        "command": command,
                    }
                )
            for ini in build_step.get("iniFiles", []) or []:
                content = ini.get("content", "")
                for raw_line in content.splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key not in {"nk", "sp", "slr", "stream_connect", "sc"}:
                        continue
                    row: dict[str, Any] = {
                        "source": str(link_summary),
                        "ini_path": ini.get("path", ""),
                        "kind": key,
                        "raw": line,
                        "kernel": "",
                        "cu": "",
                        "port": "",
                        "target": "",
                        "count": "",
                        "connections": "",
                    }
                    if key == "nk":
                        parts = value.split(":")
                        row["kernel"] = parts[0] if parts else ""
                        row["count"] = parts[1] if len(parts) > 1 else ""
                        row["connections"] = parts[2] if len(parts) > 2 else ""
                    elif key == "sp":
                        endpoint, _, target = value.partition(":")
                        cu, _, port = endpoint.partition(".")
                        row["cu"] = cu
                        row["port"] = port
                        row["target"] = target
                    elif key == "slr":
                        cu, _, target = value.partition(":")
                        row["cu"] = cu
                        row["target"] = target
                    else:
                        row["connections"] = value
                    connectivity_rows.append(row)

        build_summary = entry.get("buildSummary")
        if not build_summary:
            continue
        binary = build_summary.get("binaryContainer", {}).get("base", {})
        for kernel in build_summary.get("kernels", []) or []:
            base = kernel.get("base", {})
            cu_names = kernel.get("cuNames", []) or []
            kernel_rows.append(
                {
                    "source": str(link_summary),
                    "target": build_summary.get("target", ""),
                    "binary_name": binary.get("name", ""),
                    "binary_file": binary.get("file", ""),
                    "kernel": base.get("name", ""),
                    "xo_file": base.get("file", ""),
                    "cu_count": len(cu_names),
                    "cu_names": ".".join(cu_names),
                    "kernel_type": kernel.get("type", ""),
                }
            )

    return kernel_rows, connectivity_rows, command_rows


def parse_system_estimate(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    meta: dict[str, Any] = {
        "source": str(path),
        "design_name": "",
        "target_device": "",
        "target_clock_mhz": "",
        "total_kernels": "",
    }
    kernel_rows: list[dict[str, Any]] = []
    area_rows: list[dict[str, Any]] = []
    section = ""

    for raw in path.read_text(errors="replace").splitlines():
        line = raw.rstrip()
        if line.startswith("Design Name:"):
            meta["design_name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Target Device:"):
            meta["target_device"] = line.split(":", 1)[1].strip()
        elif line.startswith("Target Clock:"):
            meta["target_clock_mhz"] = line.split(":", 1)[1].strip().replace("MHz", "")
        elif line.startswith("Total number of kernels:"):
            meta["total_kernels"] = line.split(":", 1)[1].strip()

        if line.strip() == "Kernel Summary":
            section = "kernel"
            continue
        if line.strip() == "Timing Information (MHz)":
            section = "timing"
            continue
        if line.strip() == "Area Information":
            section = "area"
            continue
        if not line.strip() or set(line.strip()) <= {"-"}:
            continue

        if section == "kernel":
            if line.lstrip().startswith("Kernel Name"):
                continue
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) >= 5:
                kernel_rows.append(
                    {
                        "source": str(path),
                        "kernel": parts[0],
                        "type": parts[1],
                        "target": parts[2],
                        "opencl_library": parts[3],
                        "compute_units": parts[4],
                    }
                )
        elif section == "area":
            if line.lstrip().startswith("Compute Unit"):
                continue
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) < 8:
                continue
            try:
                ff, lut, dsp, bram, uram = (int(float(value)) for value in parts[-5:])
            except ValueError:
                continue
            area_rows.append(
                {
                    "source": str(path),
                    "compute_unit": parts[0],
                    "kernel": parts[1],
                    "module": parts[2],
                    "ff": ff,
                    "lut": lut,
                    "dsp": dsp,
                    "bram": bram,
                    "uram": uram,
                    "is_top_module": "yes" if parts[1] == parts[2] else "no",
                }
            )

    return meta, kernel_rows, area_rows


def parse_resource_cell(cell: str) -> tuple[str, str]:
    match = re.search(r"([0-9.]+)\s*\[\s*([0-9.<>]+)%\]", cell)
    if match:
        return match.group(1), match.group(2)
    value_match = re.search(r"([0-9.]+)", cell)
    return (value_match.group(1), "") if value_match else ("", "")


def parse_accelerator_util(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    design_state = ""
    for raw in path.read_text(errors="replace").splitlines():
        if "| Design State :" in raw:
            design_state = raw.split(":", 1)[1].strip().strip("|").strip()
        if not raw.startswith("|") or "[" not in raw:
            continue
        cells_raw = raw.split("|")[1:-1]
        if len(cells_raw) < 7:
            continue
        name_raw = cells_raw[0]
        name = name_raw.strip()
        if not name or name == "Name":
            continue
        row: dict[str, Any] = {
            "source": str(path),
            "stage": infer_stage(path),
            "design_state": design_state,
            "name": name,
            "indent": len(name_raw) - len(name_raw.lstrip()),
            "is_cu": "yes" if name.endswith(tuple(f"_{idx}" for idx in range(1, 65))) else "no",
        }
        for col, cell in zip(RESOURCE_COLUMNS, cells_raw[1:7]):
            value, pct = parse_resource_cell(cell)
            row[col] = value
            row[f"{col}_pct"] = pct
        rows.append(row)
    return rows


def infer_stage(path: Path) -> str:
    name = path.name
    for stage in ("routed", "placed", "synthed"):
        if stage in name:
            return stage
    return ""


def parse_slr_util(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    design_state = ""
    for raw in path.read_text(errors="replace").splitlines():
        if "| Design State :" in raw:
            design_state = raw.split(":", 1)[1].strip().strip("|").strip()
        if not raw.startswith("|"):
            continue
        cells = [cell.strip() for cell in raw.split("|")[1:-1]]
        if len(cells) != 7 or cells[0] not in KEY_SLR_ROWS:
            continue
        rows.append(
            {
                "source": str(path),
                "stage": infer_stage(path),
                "design_state": design_state,
                "site_type": cells[0],
                "slr0": cells[1],
                "slr1": cells[2],
                "slr2": cells[3],
                "slr0_pct": cells[4],
                "slr1_pct": cells[5],
                "slr2_pct": cells[6],
            }
        )
    return rows


def parse_timing(path: Path) -> dict[str, Any]:
    lines = path.read_text(errors="replace").splitlines()
    design_state = ""
    for raw in lines:
        if "| Design State :" in raw:
            design_state = raw.split(":", 1)[1].strip().strip("|").strip()

    for idx, line in enumerate(lines):
        if "WNS(ns)" not in line or "TNS(ns)" not in line or "WHS(ns)" not in line:
            continue
        for candidate in lines[idx + 1 : idx + 6]:
            parts = candidate.split()
            if len(parts) >= 12 and re.match(r"^-?\d+(\.\d+)?$", parts[0]):
                return {
                    "source": str(path),
                    "design_state": design_state,
                    "wns_ns": parts[0],
                    "tns_ns": parts[1],
                    "tns_failing_endpoints": parts[2],
                    "tns_total_endpoints": parts[3],
                    "whs_ns": parts[4],
                    "ths_ns": parts[5],
                    "ths_failing_endpoints": parts[6],
                    "ths_total_endpoints": parts[7],
                    "wpws_ns": parts[8],
                    "tpws_ns": parts[9],
                    "tpws_failing_endpoints": parts[10],
                    "tpws_total_endpoints": parts[11],
                }
    return {"source": str(path), "design_state": design_state}


def choose_stage_report(paths: list[Path], stem: str) -> Path | None:
    for stage in ("routed", "placed", "synthed"):
        suffix = f"{stem}_{stage}.rpt"
        candidates = [p for p in paths if p.name == suffix or p.name.endswith(f"_{suffix}")]
        if candidates:
            return sorted(candidates)[-1]
    return None


def choose_timing_report(paths: list[Path]) -> Path | None:
    priority = (
        "dr_timing_summary.rpt",
        "hw_bb_locked_timing_summary_postroute_physopted.rpt",
        "hw_bb_locked_timing_summary_routed.rpt",
    )
    for name in priority:
        matches = [p for p in paths if p.name == name or p.name.endswith(f"_{name}")]
        if matches:
            return sorted(matches)[-1]
    return sorted(paths)[-1] if paths else None


def artifact_rows(paths: list[Path], build_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        stat = path.stat()
        rows.append(
            {
                "path": str(path),
                "path_from_build_root": relpath(path, build_root),
                "size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
                "sha256": sha256_file(path),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Short name for this evidence bundle.")
    parser.add_argument("--build-root", required=True, type=Path, help="Root containing Vitis/Vivado artifacts.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Directory to write TSVs and copied reports.")
    parser.add_argument("--artifact", action="append", default=[], type=Path, help="Extra artifact path to hash.")
    parser.add_argument("--note", action="append", default=[], help="Extra note to include in summary.md.")
    args = parser.parse_args()

    build_root = args.build_root.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    link_summaries = discover(build_root, ["*.xclbin.link_summary"])
    system_estimates = discover(build_root, ["system_estimate*.xtxt"])
    xclbins = discover(build_root, ["*.xclbin"])
    util_reports = discover(build_root, ["*kernel_util_*.rpt", "*full_util_*.rpt", "*slr_util_*.rpt"])
    timing_reports = discover(build_root, ["dr_timing_summary.rpt", "*timing_summary*.rpt"])

    extra_artifacts = [path.resolve() for path in args.artifact if path.exists()]
    artifact_candidates = sorted({*xclbins, *extra_artifacts})

    link_kernel_rows: list[dict[str, Any]] = []
    connectivity_rows: list[dict[str, Any]] = []
    command_rows: list[dict[str, Any]] = []
    for path in link_summaries:
        k_rows, c_rows, cmd_rows = parse_link_summary(path)
        link_kernel_rows.extend(k_rows)
        connectivity_rows.extend(c_rows)
        command_rows.extend(cmd_rows)

    estimate_meta_rows: list[dict[str, Any]] = []
    estimate_kernel_rows: list[dict[str, Any]] = []
    hls_area_rows: list[dict[str, Any]] = []
    for path in system_estimates:
        meta, k_rows, area_rows = parse_system_estimate(path)
        estimate_meta_rows.append(meta)
        estimate_kernel_rows.extend(k_rows)
        hls_area_rows.extend(area_rows)

    selected_kernel_util = choose_stage_report(util_reports, "kernel_util")
    selected_slr_util = choose_stage_report(util_reports, "slr_util")
    selected_full_util = choose_stage_report(util_reports, "full_util")
    selected_timing = choose_timing_report(timing_reports)

    accelerator_rows = parse_accelerator_util(selected_kernel_util) if selected_kernel_util else []
    slr_rows = parse_slr_util(selected_slr_util) if selected_slr_util else []
    timing_rows = [parse_timing(selected_timing)] if selected_timing else []

    copied_report_rows: list[dict[str, Any]] = []
    for path in sorted({*link_summaries, *system_estimates, *(p for p in [selected_kernel_util, selected_slr_util, selected_full_util, selected_timing] if p)}):
        copied_path = copy_report(path, out_dir, build_root)
        copied_report_rows.append(
            {
                "source": str(path),
                "copied_path": copied_path,
                "path_from_build_root": relpath(path, build_root),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    write_tsv(out_dir / "artifacts.tsv", artifact_rows(artifact_candidates, build_root), ["path", "path_from_build_root", "size_bytes", "mtime", "sha256"])
    write_tsv(out_dir / "copied_reports.tsv", copied_report_rows, ["source", "copied_path", "path_from_build_root", "size_bytes", "sha256"])
    write_tsv(out_dir / "link_kernels.tsv", link_kernel_rows, ["source", "target", "binary_name", "binary_file", "kernel", "xo_file", "cu_count", "cu_names", "kernel_type"])
    write_tsv(out_dir / "connectivity.tsv", connectivity_rows, ["source", "ini_path", "kind", "kernel", "cu", "port", "target", "count", "connections", "raw"])
    write_tsv(out_dir / "commands.tsv", command_rows, ["source", "entry_type", "step_name", "command"])
    write_tsv(out_dir / "system_estimate_meta.tsv", estimate_meta_rows, ["source", "design_name", "target_device", "target_clock_mhz", "total_kernels"])
    write_tsv(out_dir / "system_estimate_kernels.tsv", estimate_kernel_rows, ["source", "kernel", "type", "target", "opencl_library", "compute_units"])
    write_tsv(out_dir / "hls_area.tsv", hls_area_rows, ["source", "compute_unit", "kernel", "module", "ff", "lut", "dsp", "bram", "uram", "is_top_module"])
    write_tsv(
        out_dir / "accelerator_util.tsv",
        accelerator_rows,
        ["source", "stage", "design_state", "name", "indent", "is_cu", "lut", "lut_pct", "lut_as_mem", "lut_as_mem_pct", "reg", "reg_pct", "bram", "bram_pct", "uram", "uram_pct", "dsp", "dsp_pct"],
    )
    write_tsv(out_dir / "slr_util.tsv", slr_rows, ["source", "stage", "design_state", "site_type", "slr0", "slr1", "slr2", "slr0_pct", "slr1_pct", "slr2_pct"])
    write_tsv(
        out_dir / "timing.tsv",
        timing_rows,
        ["source", "design_state", "wns_ns", "tns_ns", "tns_failing_endpoints", "tns_total_endpoints", "whs_ns", "ths_ns", "ths_failing_endpoints", "ths_total_endpoints", "wpws_ns", "tpws_ns", "tpws_failing_endpoints", "tpws_total_endpoints"],
    )

    top_hls = []
    seen_top_hls = set()
    for row in hls_area_rows:
        if row.get("is_top_module") != "yes":
            continue
        key = (row.get("kernel"), row.get("compute_unit"), row.get("module"))
        if key in seen_top_hls:
            continue
        seen_top_hls.add(key)
        top_hls.append(row)
    used_resources = next((row for row in accelerator_rows if row.get("name") == "Used Resources"), None)
    summary = [
        f"# {args.label} Vitis Evidence",
        "",
        f"- build_root: `{build_root}`",
        f"- link_summaries: {len(link_summaries)}",
        f"- system_estimates: {len(system_estimates)}",
        f"- xclbins: {len(xclbins)}",
        f"- selected_kernel_util: `{selected_kernel_util}`" if selected_kernel_util else "- selected_kernel_util: missing",
        f"- selected_slr_util: `{selected_slr_util}`" if selected_slr_util else "- selected_slr_util: missing",
        f"- selected_timing: `{selected_timing}`" if selected_timing else "- selected_timing: missing",
    ]
    for note in args.note:
        summary.append(f"- note: {note}")
    if used_resources:
        summary.extend(
            [
                "",
                "## Selected Kernel Utilization Used Resources",
                "",
                "| LUT | LUTAsMem | REG | BRAM | URAM | DSP |",
                "| --- | -------- | --- | ---- | ---- | --- |",
                f"| {used_resources.get('lut')} | {used_resources.get('lut_as_mem')} | {used_resources.get('reg')} | {used_resources.get('bram')} | {used_resources.get('uram')} | {used_resources.get('dsp')} |",
            ]
        )
    if timing_rows and timing_rows[0].get("wns_ns"):
        t = timing_rows[0]
        summary.extend(
            [
                "",
                "## Timing",
                "",
                "| WNS(ns) | TNS(ns) | WHS(ns) | THS(ns) |",
                "| ------- | ------- | ------- | ------- |",
                f"| {t.get('wns_ns')} | {t.get('tns_ns')} | {t.get('whs_ns')} | {t.get('ths_ns')} |",
            ]
        )
    if top_hls:
        summary.extend(["", "## HLS Top-Module Area", "", "| Kernel | Compute Unit | FF | LUT | BRAM | URAM | DSP |", "| ------ | ------------ | -- | --- | ---- | ---- | --- |"])
        for row in top_hls[:64]:
            summary.append(
                f"| {row.get('kernel')} | {row.get('compute_unit')} | {row.get('ff')} | {row.get('lut')} | {row.get('bram')} | {row.get('uram')} | {row.get('dsp')} |"
            )
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n")

    print(f"Wrote evidence to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
