#!/usr/bin/env python3
"""Audit evidence for the GraSU -> ReGraph pure hardware pipeline goal."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_CASES = {
    "tiny_chain_v16": "chain",
    "tiny_star_v16_u12": "hot-source",
    "tiny_spread_v16_u8": "spread",
    "tiny_hotdst_v64_u32": "hot-destination",
}

TARGETS = ("sw_emu", "hw_emu", "hw")


def run_git(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(repo: Path, path: Path | None) -> str:
    if path is None:
        return "MISSING"
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def artifact(repo: Path, name: str, path: Path | None) -> dict[str, Any]:
    exists = path is not None and path.exists()
    return {
        "name": name,
        "path": display_path(repo, path),
        "exists": exists,
        "sha256": sha256(path) if path is not None and path.is_file() else None,
        "size_bytes": path.stat().st_size if path is not None and path.is_file() else None,
    }


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_kv_line(line: str) -> dict[str, str]:
    return {key: value for key, value in re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line or "")}


def newest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def newest_glob(repo: Path, pattern: str) -> Path | None:
    return newest(list(repo.glob(pattern)))


def newest_xclbin_contract(repo: Path, target: str) -> Path | None:
    candidates = []
    prefix = f"xclbin_contract_{target}_"
    patterns = (
        ".tmp_build/pure_pipeline_xclbin_contracts/xclbin_contract_*.tsv",
        f".tmp_build/pure_pipeline_{target}_stage0/run_logs/xclbin_contract_{target}_*.tsv",
    )
    seen: set[Path] = set()
    for pattern in patterns:
        for path in repo.glob(pattern):
            if path in seen:
                continue
            seen.add(path)
            name = path.name
            if target == "hw":
                if name.startswith(prefix) and not name.startswith("xclbin_contract_hw_emu_"):
                    candidates.append(path)
            elif name.startswith(prefix):
                candidates.append(path)
    return newest(candidates)


def newest_launch_packet_source_fingerprints(repo: Path) -> Path | None:
    return newest(list(repo.glob(".tmp_build/pure_pipeline_launch_packet_*/source_fingerprints.tsv")))


def newest_readiness(repo: Path, target: str) -> Path | None:
    candidates = list(repo.glob(f".tmp_build/pure_pipeline_{target}_stage0/run_logs/readiness_*.txt"))
    strict_candidates = []
    for path in candidates:
        if "allow_active_builders=0" in path.read_text(encoding="ascii", errors="replace"):
            strict_candidates.append(path)
    return newest(strict_candidates) or newest(candidates)


def has_all_expected_cases(path: Path) -> bool:
    rows = read_tsv(path)
    cases = {row.get("case", "") for row in rows}
    return all(case in cases for case in EXPECTED_CASES)


def newest_complete_pure_summary(repo: Path, target: str) -> Path | None:
    candidates = sorted(
        repo.glob(f"results/pure_pipeline_{target}_smoke_*/summary.tsv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        if has_all_expected_cases(path):
            return path
    return candidates[0] if candidates else None


def pure_summary(repo: Path, path: Path | None) -> dict[str, Any]:
    rows = read_tsv(path) if path is not None else []
    by_case = {row.get("case", ""): row for row in rows}
    missing_cases = [case for case in EXPECTED_CASES if case not in by_case]
    failed_cases = [
        case
        for case in EXPECTED_CASES
        if by_case.get(case, {}).get("status") != "PASS"
    ]
    mismatch_cases = [
        case
        for case in EXPECTED_CASES
        if "mismatches=0" not in by_case.get(case, {}).get("result_line", "")
    ]
    timing_keys = ("grasu_ms", "barrier_ms", "adapter_ms", "lksg_ms", "apply_ms", "event_e2e_ms")
    missing_timing: dict[str, list[str]] = {}
    max_vertices = 0
    for case, row in by_case.items():
        timing = parse_kv_line(row.get("timing_line", ""))
        missing = [key for key in timing_keys if key not in timing]
        if missing:
            missing_timing[case] = missing
        try:
            max_vertices = max(max_vertices, int(row.get("vertices", "0") or 0))
        except ValueError:
            pass
    return {
        "path": display_path(repo, path),
        "exists": path is not None and path.exists(),
        "sha256": sha256(path) if path is not None else None,
        "row_count": len(rows),
        "expected_cases": sorted(EXPECTED_CASES),
        "missing_cases": missing_cases,
        "failed_cases": failed_cases,
        "mismatch_cases": mismatch_cases,
        "missing_timing_fields": missing_timing,
        "all_expected_pass": bool(rows) and not missing_cases and not failed_cases and not mismatch_cases,
        "has_required_timing_fields": bool(rows) and not missing_cases and not missing_timing,
        "max_vertices_seen": max_vertices,
    }


def xclbin_contract_summary(repo: Path, path: Path | None) -> dict[str, Any]:
    rows = read_tsv(path) if path is not None else []
    failed = [row.get("check", "") for row in rows if row.get("ok") != "yes"]
    return {
        "path": display_path(repo, path),
        "exists": path is not None and path.exists(),
        "sha256": sha256(path) if path is not None else None,
        "row_count": len(rows),
        "failed_checks": failed,
        "all_checks_pass": bool(rows) and not failed,
    }


def prepare_summary(repo: Path, path: Path | None) -> dict[str, Any]:
    rows = read_tsv(path) if path is not None else []
    failed_cases = [row.get("case", "") for row in rows if row.get("status") != "PASS"]
    missing_prep_line = [row.get("case", "") for row in rows if "status=PASS" not in row.get("prep_line", "")]
    max_vertices = 0
    boundary_cases: list[str] = []
    missing_boundary_fields: dict[str, list[str]] = {}
    required_prep_fields = ("pma_slots", "partition_size", "little_dst_buffer", "unit_weight")
    for row in rows:
        try:
            vertices = int(row.get("vertices", "0") or 0)
        except ValueError:
            vertices = 0
        max_vertices = max(max_vertices, vertices)
        if vertices == 65536 and row.get("status") == "PASS":
            boundary_cases.append(row.get("case", ""))
        prep = parse_kv_line(row.get("prep_line", ""))
        missing = [field for field in required_prep_fields if field not in prep]
        if missing:
            missing_boundary_fields[row.get("case", "")] = missing
    return {
        "path": display_path(repo, path),
        "exists": path is not None and path.exists(),
        "sha256": sha256(path) if path is not None else None,
        "row_count": len(rows),
        "failed_cases": failed_cases,
        "missing_prep_line": missing_prep_line,
        "missing_boundary_fields": missing_boundary_fields,
        "max_vertices_seen": max_vertices,
        "v65536_pass_cases": boundary_cases,
        "has_v65536_pass": bool(boundary_cases) and not failed_cases and not missing_prep_line,
    }


def host_summary(repo: Path, path: Path) -> dict[str, Any]:
    rows = read_tsv(path)
    by_case = {row.get("case", ""): row for row in rows}
    missing_cases = [case for case in EXPECTED_CASES if case not in by_case]
    failed_cases = [
        case
        for case in EXPECTED_CASES
        if by_case.get(case, {}).get("status") != "PASS"
    ]
    mismatch_cases = [
        case
        for case in EXPECTED_CASES
        if by_case.get(case, {}).get("mismatch_count") not in ("0", "0.0")
    ]
    zero_cost_ms: dict[str, float] = {}
    for case, row in by_case.items():
        try:
            zero_cost_ms[case] = float(row.get("grasu_ms", "0")) + float(row.get("regraph_e2e_ms", "0"))
        except ValueError:
            pass
    return {
        "path": display_path(repo, path),
        "exists": path.exists(),
        "sha256": sha256(path),
        "missing_cases": missing_cases,
        "failed_cases": failed_cases,
        "mismatch_cases": mismatch_cases,
        "zero_cost_ms": zero_cost_ms,
        "all_expected_pass": bool(rows) and not missing_cases and not failed_cases and not mismatch_cases,
    }


def spine_summary(repo: Path, path: Path) -> dict[str, Any]:
    rows = read_tsv(path)
    by_case = {row.get("case", ""): row for row in rows}
    missing_cases = [case for case in EXPECTED_CASES if case not in by_case]
    failed_cases = [
        case
        for case in EXPECTED_CASES
        if by_case.get(case, {}).get("status") != "PASS"
    ]
    error_cases = [
        case
        for case in EXPECTED_CASES
        if by_case.get(case, {}).get("errors") not in ("0", "0.0")
    ]
    return {
        "path": display_path(repo, path),
        "exists": path.exists(),
        "sha256": sha256(path),
        "missing_cases": missing_cases,
        "failed_cases": failed_cases,
        "error_cases": error_cases,
        "all_expected_pass": bool(rows) and not missing_cases and not failed_cases and not error_cases,
    }


def input_identity_summary(repo: Path, path: Path | None) -> dict[str, Any]:
    rows = read_tsv(path) if path is not None else []
    by_case = {row.get("case", ""): row for row in rows}
    missing_cases = [case for case in EXPECTED_CASES if case not in by_case]
    failed_cases = [
        case
        for case in EXPECTED_CASES
        if by_case.get(case, {}).get("ok") != "yes"
    ]
    missing_hash_cases = [
        case
        for case in EXPECTED_CASES
        if not by_case.get(case, {}).get("manifest_edge_sha256")
        or by_case.get(case, {}).get("manifest_edge_sha256")
        != by_case.get(case, {}).get("host_edge_sha256")
        or by_case.get(case, {}).get("manifest_edge_sha256")
        != by_case.get(case, {}).get("spine_edge_sha256")
    ]
    return {
        "path": display_path(repo, path),
        "exists": path is not None and path.exists(),
        "sha256": sha256(path) if path is not None else None,
        "row_count": len(rows),
        "missing_cases": missing_cases,
        "failed_cases": failed_cases,
        "missing_hash_cases": missing_hash_cases,
        "all_expected_pass": bool(rows) and not missing_cases and not failed_cases and not missing_hash_cases,
    }


def source_contains(path: Path, needles: list[str]) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="ascii", errors="replace")
    return all(needle in text for needle in needles)


def target_build_scripts_cover_pure_pipeline(repo: Path) -> dict[str, Any]:
    paths: list[str] = []
    missing: dict[str, list[str]] = {}
    for target in ("hw_emu", "hw"):
        build_root = repo / f".tmp_build/pure_pipeline_{target}_stage0"
        manifest = build_root / "manifest.env"
        compile_commands = build_root / "compile_commands.sh"
        link_command = build_root / "link_command.sh"
        link_cfg = build_root / "config" / f"pure_pipeline_{target}.cfg"
        paths.extend([
            display_path(repo, manifest),
            display_path(repo, compile_commands),
            display_path(repo, link_command),
            display_path(repo, link_cfg),
        ])
        checks = {
            f"{target}:manifest": (
                manifest,
                [
                    f"TARGET={target}",
                    f"LINK_CFG={link_cfg}",
                    f"OUT_XCLBIN={build_root}/build/grasu_regraph_pure_pipeline.{target}.xclbin",
                    f"COMPILE_COMMANDS={compile_commands}",
                    f"LINK_COMMAND={link_command}",
                ],
            ),
            f"{target}:compile_commands": (
                compile_commands,
                [
                    f"v++ --target {target} --compile",
                    "process_cache",
                    "process_ddr",
                    "pma_completion_barrier",
                    "pma_to_regraph_adapter",
                    "lksg_stream",
                    "kernelApply",
                    "kernelHBMWrapper",
                    "GRASU_ENABLE_COMPLETION_TOKEN",
                ],
            ),
            f"{target}:link_command": (
                link_command,
                [
                    f"v++ --target {target} --link",
                    f"--config {link_cfg}",
                    f"-o {build_root}/build/grasu_regraph_pure_pipeline.{target}.xclbin",
                    f"{build_root}/build/process_cache.{target}.xo",
                    f"{build_root}/build/process_ddr.{target}.xo",
                    f"{build_root}/build/pma_completion_barrier.{target}.xo",
                    f"{build_root}/build/pma_to_regraph_adapter.{target}.xo",
                    f"{build_root}/build/lksg_stream.{target}.xo",
                ],
            ),
            f"{target}:link_config": (
                link_cfg,
                [
                    "nk=process_cache:2:process_cache_1.process_cache_2",
                    "nk=process_ddr:2:process_ddr_1.process_ddr_2",
                    "nk=pma_completion_barrier:1:pma_completion_barrier_1",
                    "nk=pma_to_regraph_adapter:1:pma_to_regraph_adapter_1",
                    "nk=lksg_stream:1:lksg_stream_1",
                    "stream_connect=process_cache_1.completion_token:pma_completion_barrier_1.done0:16",
                    "stream_connect=process_ddr_1.completion_token:pma_completion_barrier_1.done1:16",
                    "stream_connect=process_cache_2.completion_token:pma_completion_barrier_1.done2:16",
                    "stream_connect=process_ddr_2.completion_token:pma_completion_barrier_1.done3:16",
                    "stream_connect=pma_to_regraph_adapter_1.edge_burst_out:lksg_stream_1.edge_burst_in:32",
                    "sp=pma_to_regraph_adapter_1.pma0:HBM[0]",
                    "sp=pma_to_regraph_adapter_1.pma1:HBM[1]",
                    "sp=pma_to_regraph_adapter_1.pma2:HBM[2]",
                    "sp=pma_to_regraph_adapter_1.pma3:HBM[3]",
                    "sp=pma_to_regraph_adapter_1.row_offset:HBM[0]",
                    "stream_connect=kernelApply_1.prop_write_burst_stm:kernelHBMWrapper_1.prop_write_burst_stm:16",
                ],
            ),
        }
        for check_name, (path, needles) in checks.items():
            if not source_contains(path, needles):
                text = path.read_text(encoding="ascii", errors="replace") if path.is_file() else ""
                missing[check_name] = [needle for needle in needles if needle not in text]
    return {
        "ok": not missing,
        "paths": paths,
        "contract": "generated hw_emu/hw manifest, compile, link, and connectivity config cover the pure GraSU->barrier->adapter->ReGraph pipeline",
        "missing": missing,
    }


def host_runtime_matches_generated_config(repo: Path) -> dict[str, Any]:
    host = repo / "tools/pure_pipeline_host.cpp"
    configs = {
        target: repo / f".tmp_build/pure_pipeline_{target}_stage0/config/pure_pipeline_{target}.cfg"
        for target in ("hw_emu", "hw")
    }
    paths = [display_path(repo, host)] + [display_path(repo, path) for path in configs.values()]

    host_checks = {
        "host:kernel_cu_names": [
            'cl::Kernel bin_search_1(program, "bin_search:{bin_search_1}"',
            'cl::Kernel bin_search_2(program, "bin_search:{bin_search_2}"',
            'cl::Kernel bin_search_3(program, "bin_search:{bin_search_3}"',
            'cl::Kernel bin_search_4(program, "bin_search:{bin_search_4}"',
            'cl::Kernel dispatch(program, "dispatch:{dispatch_1}"',
            'cl::Kernel process_cache_1(program, "process_cache:{process_cache_1}"',
            'cl::Kernel process_cache_2(program, "process_cache:{process_cache_2}"',
            'cl::Kernel process_ddr_1(program, "process_ddr:{process_ddr_1}"',
            'cl::Kernel process_ddr_2(program, "process_ddr:{process_ddr_2}"',
            'cl::Kernel barrier(program, "pma_completion_barrier:{pma_completion_barrier_1}"',
            'cl::Kernel adapter(program, "pma_to_regraph_adapter:{pma_to_regraph_adapter_1}"',
            'cl::Kernel lksg(program, "lksg_stream:{lksg_stream_1}"',
            'cl::Kernel apply(program, "kernelApply:{kernelApply_1}"',
            'cl::Kernel hbm(program, "kernelHBMWrapper:{kernelHBMWrapper_1}"',
        ],
        "host:actual_pma_adapter_args": [
            "adapter.setArg(0, pma_dev[0])",
            "adapter.setArg(1, pma_dev[1])",
            "adapter.setArg(2, pma_dev[2])",
            "adapter.setArg(3, pma_dev[3])",
            "adapter.setArg(4, row_dev[0])",
            "adapter.setArg(5, static_cast<unsigned>(dataset.node_size))",
            "adapter.setArg(6, static_cast<unsigned>(prepared.pma_slot_count))",
            "adapter.setArg(7, static_cast<unsigned>(MAX_CACHE_SEGMENT))",
        ],
        "host:grasu_writer_args": [
            "process_cache_1.setArg(0, pma_dev[0])",
            "process_cache_2.setArg(0, pma_dev[2])",
            "process_ddr_1.setArg(arg, pma_dev[1])",
            "process_ddr_2.setArg(arg, pma_dev[3])",
        ],
        "host:regraph_args": [
            "hbm.setArg(0, *read_props[0])",
            "hbm.setArg(1, *read_props[1])",
            "hbm.setArg(2, *write_props[0])",
            "hbm.setArg(3, *write_props[1])",
            "apply.setArg(0, apply_prop_dev)",
            "lksg.setArg(1, part_edge_num)",
            "lksg.setArg(4, reset_tmp_prop)",
        ],
        "host:barrier_and_pipeline_events": [
            "pipeline_queue.enqueueTask(barrier, nullptr, &barrier_event)",
            "adapter_wait_events.push_back(barrier_event)",
            "pipeline_queue.enqueueTask(adapter, adapter_wait_list, &adapter_event)",
            "pipeline_queue.enqueueTask(lksg, nullptr, &lksg_event)",
            "pipeline_queue.enqueueTask(hbm, nullptr, &hbm_event)",
            "pipeline_queue.enqueueTask(apply, nullptr, &apply_event)",
        ],
        "host:timing_record": [
            "PURE_PIPELINE_TIMING",
            "grasu_ms=",
            "barrier_ms=",
            "adapter_ms=",
            "lksg_ms=",
            "apply_ms=",
            "event_e2e_ms=",
        ],
    }

    config_checks = {
        "config:kernel_cu_names": [
            "nk=bin_search:4:bin_search_1.bin_search_2.bin_search_3.bin_search_4",
            "nk=dispatch:1:dispatch_1",
            "nk=process_cache:2:process_cache_1.process_cache_2",
            "nk=process_ddr:2:process_ddr_1.process_ddr_2",
            "nk=pma_completion_barrier:1:pma_completion_barrier_1",
            "nk=pma_to_regraph_adapter:1:pma_to_regraph_adapter_1",
            "nk=lksg_stream:1:lksg_stream_1",
            "nk=kernelApply:1",
            "nk=kernelHBMWrapper:1",
        ],
        "config:pma_to_barrier_and_regraph_streams": [
            "stream_connect=process_cache_1.completion_token:pma_completion_barrier_1.done0:16",
            "stream_connect=process_ddr_1.completion_token:pma_completion_barrier_1.done1:16",
            "stream_connect=process_cache_2.completion_token:pma_completion_barrier_1.done2:16",
            "stream_connect=process_ddr_2.completion_token:pma_completion_barrier_1.done3:16",
            "stream_connect=pma_to_regraph_adapter_1.edge_burst_out:lksg_stream_1.edge_burst_in:32",
        ],
        "config:pma_and_regraph_hbm_ports": [
            "sp=pma_to_regraph_adapter_1.pma0:HBM[0]",
            "sp=pma_to_regraph_adapter_1.pma1:HBM[1]",
            "sp=pma_to_regraph_adapter_1.pma2:HBM[2]",
            "sp=pma_to_regraph_adapter_1.pma3:HBM[3]",
            "sp=pma_to_regraph_adapter_1.row_offset:HBM[0]",
            "sp=kernelApply_1.vertex_prop:HBM[30]",
            "sp=kernelHBMWrapper_1.src_prop_1:HBM[1]",
            "sp=kernelHBMWrapper_1.src_prop_2:HBM[3]",
        ],
    }

    missing: dict[str, list[str]] = {}
    host_text = host.read_text(encoding="ascii", errors="replace") if host.is_file() else ""
    for check_name, needles in host_checks.items():
        absent = [needle for needle in needles if needle not in host_text]
        if absent:
            missing[check_name] = absent

    for target, config in configs.items():
        text = config.read_text(encoding="ascii", errors="replace") if config.is_file() else ""
        for check_name, needles in config_checks.items():
            absent = [needle for needle in needles if needle not in text]
            if absent:
                missing[f"{target}:{check_name}"] = absent

    return {
        "ok": not missing,
        "paths": paths,
        "contract": "host runtime opens the generated CU names and binds PMA, barrier, stream ReGraph, apply, HBM, and timing arguments consistently with hw_emu/hw link configs",
        "missing": missing,
    }


def source_proofs(repo: Path) -> dict[str, dict[str, Any]]:
    host = repo / "tools/pure_pipeline_host.cpp"
    adapter = repo / "kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
    barrier = repo / "kernels/pma_completion_barrier/pma_completion_barrier.cpp"
    lksg_stream = repo / "kernels/regraph_stream_little_gs/little_gs_stream.cpp"
    prepare = repo / "scripts/prepare_pure_hw_pipeline_build.sh"
    return {
        "single_context_program": {
            "ok": source_contains(host, [
                "cl::Context context(device",
                "cl::Program program(context",
                "cl::Kernel barrier(program",
                "cl::Kernel adapter(program",
                "cl::Kernel lksg(program",
                "cl::Kernel apply(program",
            ]),
            "path": display_path(repo, host),
        },
        "adapter_receives_actual_pma_buffers": {
            "ok": source_contains(host, [
                "adapter.setArg(0, pma_dev[0])",
                "adapter.setArg(1, pma_dev[1])",
                "adapter.setArg(2, pma_dev[2])",
                "adapter.setArg(3, pma_dev[3])",
                "adapter.setArg(4, row_dev[0])",
            ]),
            "path": display_path(repo, host),
        },
        "pma_row_offset_begin_end_contract": {
            "ok": source_contains(host, [
                "(graph.row_offset[i] << 32)",
                "graph.row_offset[i + 1]",
                "prepared.row_offsets[copy][i] = packed",
            ]) and source_contains(adapter, [
                "begin = packed.range(63, 32)",
                "end = packed.range(31, 0)",
                "unpack_row_bounds(row_offset[src], begin, end)",
                "unpack_row_bounds(row_offset[node_count - 1], last_begin, total_slots)",
            ]),
            "paths": [display_path(repo, host), display_path(repo, adapter)],
            "contract": "host packs row_offset[src] as begin[63:32], end[31:0]; adapter decodes the same fields",
        },
        "completion_token_barrier": {
            "ok": source_contains(prepare, [
                "process_cache_1.completion_token:pma_completion_barrier_1.done0",
                "process_ddr_1.completion_token:pma_completion_barrier_1.done1",
                "process_cache_2.completion_token:pma_completion_barrier_1.done2",
                "process_ddr_2.completion_token:pma_completion_barrier_1.done3",
            ]) and source_contains(barrier, [
                "pma_completion_barrier",
                "done0.read()",
                "(void)done1.read()",
                "(void)done2.read()",
                "(void)done3.read()",
            ]) and source_contains(host, [
                "adapter_wait_events.push_back(barrier_event)",
                "pipeline_queue.enqueueTask(adapter, adapter_wait_list, &adapter_event)",
            ]),
            "paths": [display_path(repo, prepare), display_path(repo, barrier), display_path(repo, host)],
        },
        "adapter_to_regraph_stream": {
            "ok": source_contains(prepare, [
                "pma_to_regraph_adapter_1.edge_burst_out:lksg_stream_1.edge_burst_in",
            ]) and source_contains(adapter, [
                "typedef ap_axiu<512, 0, 0, 0> edge_burst_pkt_t",
                "lane < 8",
                "#pragma HLS INTERFACE axis port=edge_burst_out",
            ]),
            "paths": [display_path(repo, prepare), display_path(repo, adapter)],
        },
        "stream_burst_8_edge_contract": {
            "ok": source_contains(adapter, [
                "typedef ap_axiu<512, 0, 0, 0> edge_burst_pkt_t",
                "const unsigned base = lane * 64",
                "pkt.data.range(base + 31, base) = src",
                "pkt.data.range(base + 63, base + 32) = dst",
                "for (unsigned lane = 0; lane < 8; ++lane)",
            ]) and source_contains(lksg_stream, [
                "typedef ap_axiu<512, 0, 0, 0> edge_burst_pkt_t",
                "for (int lane = 0; lane < NUM_EDGE_PER_BURST; lane++)",
                "const int base = lane * 64",
                "burst.edges[lane].src = pkt.data.range(base + 31, base)",
                "burst.edges[lane].dst = pkt.data.range(base + 63, base + 32)",
                "part_edge_num >> LOG2_NUM_EDGE_PER_BURST",
            ]),
            "paths": [display_path(repo, adapter), display_path(repo, lksg_stream)],
            "contract": "512-bit AXI packet, 64 bits per edge record, 8 edge lanes per burst",
        },
        "unit_weight_sssp_packing": {
            "ok": source_contains(adapter, [
                "kUnitWeight = 1u",
                "kWeightShift = 19",
                "pack_regraph_dst",
            ]),
            "path": display_path(repo, adapter),
        },
        "timing_fields": {
            "ok": source_contains(host, [
                "grasu_ms=",
                "barrier_ms=",
                "adapter_ms=",
                "lksg_ms=",
                "apply_ms=",
                "event_e2e_ms=",
                "timing.barrier_ms = event_duration_ms(barrier_event)",
            ]),
            "path": display_path(repo, host),
        },
        "prepare_only_boundary_mode": {
            "ok": source_contains(host, [
                "--prepare-only",
                "PURE_PIPELINE_PREP",
                "partition_size=",
                "little_dst_buffer=",
            ]),
            "path": display_path(repo, host),
        },
        "target_build_scripts_cover_pure_pipeline": target_build_scripts_cover_pure_pipeline(repo),
        "host_runtime_matches_generated_config": host_runtime_matches_generated_config(repo),
    }


def target_state(repo: Path, target: str) -> dict[str, Any]:
    build_root = repo / f".tmp_build/pure_pipeline_{target}_stage0"
    xclbin = build_root / "build" / f"grasu_regraph_pure_pipeline.{target}.xclbin"
    summary_path = newest_complete_pure_summary(repo, target)
    run_env_path = summary_path.parent / "run.env" if summary_path is not None else None
    xclbin_contract_path = newest_xclbin_contract(repo, target)
    return {
        "target": target,
        "build_root": display_path(repo, build_root),
        "xclbin": artifact(repo, f"pure_{target}_xclbin", xclbin),
        "xclbin_contract": xclbin_contract_summary(repo, xclbin_contract_path),
        "xclbin_contract_artifact": artifact(repo, f"pure_{target}_xclbin_contract", xclbin_contract_path),
        "manifest": artifact(repo, f"pure_{target}_manifest", build_root / "manifest.env"),
        "compile_commands": artifact(repo, f"pure_{target}_compile_commands", build_root / "compile_commands.sh"),
        "link_command": artifact(repo, f"pure_{target}_link_command", build_root / "link_command.sh"),
        "smoke_summary": pure_summary(repo, summary_path),
        "smoke_summary_artifact": artifact(repo, f"pure_{target}_smoke_summary", summary_path),
        "run_env": artifact(repo, f"pure_{target}_run_env", run_env_path),
    }


def status_if_hw_valid(hw_valid: bool, source_ok: bool, sw_valid: bool) -> str:
    if hw_valid and source_ok:
        return "proven"
    if source_ok or sw_valid:
        return "partial"
    return "missing"


def requirement(
    req_id: int,
    title: str,
    status: str,
    evidence: list[str],
    gaps: list[str],
) -> dict[str, Any]:
    return {
        "id": req_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "gaps": gaps,
    }


def build_audit(repo: Path, label: str) -> dict[str, Any]:
    git_head = run_git(repo, ["rev-parse", "HEAD"])
    git_short = run_git(repo, ["rev-parse", "--short", "HEAD"])
    git_branch = run_git(repo, ["branch", "--show-current"])
    dirty = bool(run_git(repo, ["status", "--short"]))

    targets = {target: target_state(repo, target) for target in TARGETS}
    proofs = source_proofs(repo)

    host_path = repo / "results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv"
    spine_path = repo / "results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv"
    three_way_path = repo / "results/pure_pipeline_smoke_compare_stage1_with_spine/comparison.tsv"
    three_way_md = repo / "results/pure_pipeline_smoke_compare_stage1_with_spine/comparison.md"
    zero_vs_spine_path = repo / "results/spine_vs_grasu_regraph_smoke_same_input_hw_stage0/comparison.tsv"
    same_input_path = newest_glob(repo, "results/smoke_input_identity_*/identity.tsv")
    boundary_prepare_path = newest_glob(repo, "results/pure_pipeline_prepare_boundary_*/summary.tsv")
    boundary_prepare_env = boundary_prepare_path.parent / "run.env" if boundary_prepare_path is not None else None

    host = host_summary(repo, host_path)
    spine = spine_summary(repo, spine_path)
    same_input = input_identity_summary(repo, same_input_path)
    boundary_prepare = prepare_summary(repo, boundary_prepare_path)

    sw_valid = targets["sw_emu"]["smoke_summary"]["all_expected_pass"]
    hw_emu_valid = targets["hw_emu"]["smoke_summary"]["all_expected_pass"]
    hw_valid = targets["hw"]["smoke_summary"]["all_expected_pass"]
    all_targets_valid = sw_valid and hw_emu_valid and hw_valid
    hw_xclbin_exists = targets["hw"]["xclbin"]["exists"]
    hw_emu_xclbin_exists = targets["hw_emu"]["xclbin"]["exists"]

    source_same_context = proofs["single_context_program"]["ok"]
    source_barrier = proofs["completion_token_barrier"]["ok"]
    source_actual_pma = proofs["adapter_receives_actual_pma_buffers"]["ok"]
    source_stream = proofs["adapter_to_regraph_stream"]["ok"]
    source_row_bounds = proofs["pma_row_offset_begin_end_contract"]["ok"]
    source_stream_contract = proofs["stream_burst_8_edge_contract"]["ok"]
    source_unit = proofs["unit_weight_sssp_packing"]["ok"]
    source_timing = proofs["timing_fields"]["ok"]

    baseline_ok = (
        host["all_expected_pass"]
        and spine["all_expected_pass"]
        and three_way_path.exists()
        and same_input["all_expected_pass"]
    )
    max_vertices_seen = max(
        [targets[target]["smoke_summary"]["max_vertices_seen"] for target in TARGETS]
        + [boundary_prepare["max_vertices_seen"]]
    )
    boundary_prepare_ok = boundary_prepare["has_v65536_pass"] and proofs["prepare_only_boundary_mode"]["ok"]

    requirements = [
        requirement(
            1,
            "GraSU and ReGraph are in one xclbin and one OpenCL context",
            status_if_hw_valid(hw_valid, source_same_context, sw_valid),
            [
                proofs["single_context_program"]["path"],
                targets["sw_emu"]["xclbin"]["path"],
                targets["sw_emu"]["xclbin_contract"]["path"],
                targets["sw_emu"]["smoke_summary"]["path"],
            ],
            [] if hw_valid else ["pure hw_emu/hw xclbins and smoke evidence are still missing"],
        ),
        requirement(
            2,
            "Four GraSU PMA writers form a completion-token batch barrier",
            status_if_hw_valid(hw_valid, source_barrier, sw_valid),
            [
                "scripts/prepare_pure_hw_pipeline_build.sh stream_connect completion_token lines",
                "kernels/pma_completion_barrier/pma_completion_barrier.cpp done0..done3 reads",
                "tools/pure_pipeline_host.cpp adapter waits on barrier_event before step 0",
            ],
            [] if hw_valid else ["barrier is source/sw_emu-proven; needs hw_emu/hw validation"],
        ),
        requirement(
            3,
            "Adapter reads actual GraSU PMA, not expected edge files",
            status_if_hw_valid(hw_valid, source_actual_pma and source_row_bounds, sw_valid),
            [
                proofs["adapter_receives_actual_pma_buffers"]["path"],
                "adapter args 0..3 are pma_dev[0..3], arg 4 is row_dev[0]",
                proofs["pma_row_offset_begin_end_contract"]["contract"],
            ],
            [] if hw_valid else ["needs pure hw_emu/hw smoke to prove the same path beyond sw_emu"],
        ),
        requirement(
            4,
            "Adapter and ReGraph use AXI4-Stream at 8 edges/cycle steady width",
            status_if_hw_valid(hw_valid, source_stream and source_stream_contract, sw_valid),
            [
                "ap_axiu<512> edge_burst_pkt_t",
                "8 lanes per burst in adapter lane loop",
                "adapter edge_burst_out connects to lksg_stream edge_burst_in",
                proofs["stream_burst_8_edge_contract"]["contract"],
                targets["sw_emu"]["xclbin_contract"]["path"],
            ],
            [] if hw_valid else ["needs linked hw_emu/hw xclbin evidence for the stream connection"],
        ),
        requirement(
            5,
            "No graph D2H, host conversion, or graph H2D between GraSU and ReGraph",
            status_if_hw_valid(hw_valid, source_actual_pma and source_row_bounds and source_stream, sw_valid),
            [
                proofs["adapter_receives_actual_pma_buffers"]["path"],
                proofs["pma_row_offset_begin_end_contract"]["contract"],
                "pure sw_emu summary passes without GraSU edge export files",
            ],
            [] if hw_valid else ["host baseline still exists separately; pure hw path needs hw_emu/hw smoke"],
        ),
        requirement(
            6,
            "First stage supports V <= 65536 unit-weight SSSP",
            "proven" if all_targets_valid and boundary_prepare_ok and source_unit else (
                "partial" if source_unit and (sw_valid or boundary_prepare_ok) else "missing"
            ),
            [
                proofs["unit_weight_sssp_packing"]["path"],
                proofs["prepare_only_boundary_mode"]["path"],
                boundary_prepare["path"],
                f"max_vertices_seen_in_pure_or_prepare={max_vertices_seen}",
                "v65536_prepare_cases=" + ",".join(boundary_prepare["v65536_pass_cases"]),
            ],
            [] if all_targets_valid and boundary_prepare_ok else (
                ["prepare-only reaches V=65536; pure hw_emu/hw boundary execution is still missing"]
                if boundary_prepare_ok else
                ["no passing V=65536 boundary prepare-check or hardware run is present yet"]
            ),
        ),
        requirement(
            7,
            "chain, hot-source, spread, hot-destination pass sw_emu, hw_emu, and hw CPU-oracle checks",
            "proven" if all_targets_valid else (
                "blocked_by_missing_artifact" if sw_valid and (not hw_emu_xclbin_exists or not hw_xclbin_exists)
                else "partial"
            ),
            [
                targets["sw_emu"]["smoke_summary"]["path"],
                targets["hw_emu"]["smoke_summary"]["path"],
                targets["hw"]["smoke_summary"]["path"],
            ],
            [] if all_targets_valid else ["sw_emu passes; hw_emu/hw xclbin smoke outputs are not present yet"],
        ),
        requirement(
            8,
            "Record GraSU, barrier, Adapter/ReGraph, Apply, and unified pipeline E2E",
            "proven" if all_targets_valid and all(
                targets[target]["smoke_summary"]["has_required_timing_fields"] for target in TARGETS
            ) else ("partial" if source_timing and targets["sw_emu"]["smoke_summary"]["has_required_timing_fields"] else "missing"),
            [
                proofs["timing_fields"]["path"],
                targets["sw_emu"]["smoke_summary"]["path"],
            ],
            [] if all_targets_valid else ["sw_emu records profiled barrier timing; hw_emu/hw timing evidence is still missing"],
        ),
        requirement(
            9,
            "Retain host baseline and zero-cost handoff baseline on identical inputs",
            "proven" if baseline_ok else "partial",
            [
                host["path"],
                spine["path"],
                same_input["path"],
                display_path(repo, three_way_path),
                display_path(repo, zero_vs_spine_path),
            ],
            [] if baseline_ok else ["same-input comparison or input-identity evidence is incomplete"],
        ),
        requirement(
            10,
            "Build commands, source hash, xclbin hash, logs, and results are reproducible",
            "proven" if all_targets_valid else "partial",
            [
                f"git_head={git_head}",
                targets["hw_emu"]["compile_commands"]["path"],
                targets["hw_emu"]["link_command"]["path"],
                targets["hw"]["compile_commands"]["path"],
                targets["hw"]["link_command"]["path"],
            ],
            [] if all_targets_valid else ["hw_emu/hw xclbin hashes, full build logs, and final smoke results are missing"],
        ),
    ]

    artifacts = [
        artifact(repo, "host_baseline_summary", host_path),
        artifact(repo, "spine_summary", spine_path),
        artifact(repo, "three_way_comparison_tsv", three_way_path),
        artifact(repo, "three_way_comparison_md", three_way_md),
        artifact(repo, "zero_vs_spine_comparison_tsv", zero_vs_spine_path),
        artifact(repo, "latest_smoke_input_identity", same_input_path),
        artifact(repo, "boundary_prepare_summary", boundary_prepare_path),
        artifact(repo, "boundary_prepare_run_env", boundary_prepare_env),
        artifact(repo, "latest_source_contracts", newest_glob(repo, ".tmp_build/pure_pipeline_source_contracts/source_contracts_*.tsv")),
        artifact(repo, "latest_launch_packet_source_fingerprints", newest_launch_packet_source_fingerprints(repo)),
        artifact(repo, "start_state_source_fingerprints", newest_glob(repo, ".tmp_build/pure_hw_start_state_*/source_fingerprints.tsv")),
        artifact(repo, "latest_hw_emu_source_contracts", newest_glob(repo, ".tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_*.tsv")),
        artifact(repo, "latest_hw_source_contracts", newest_glob(repo, ".tmp_build/pure_pipeline_hw_stage0/run_logs/source_contracts_*.tsv")),
        artifact(repo, "latest_sw_emu_xclbin_contract", newest_xclbin_contract(repo, "sw_emu")),
        artifact(repo, "latest_hw_emu_xclbin_contract", newest_xclbin_contract(repo, "hw_emu")),
        artifact(repo, "latest_hw_xclbin_contract", newest_xclbin_contract(repo, "hw")),
        artifact(repo, "latest_hw_emu_build_evidence", newest_glob(repo, ".tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_*_evidence.tsv")),
        artifact(repo, "latest_hw_emu_finalize_evidence", newest_glob(repo, ".tmp_build/pure_pipeline_hw_emu_stage0/run_logs/finalize_*_evidence.tsv")),
        artifact(repo, "latest_hw_emu_target_flow_env", newest_glob(repo, ".tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_*.env")),
        artifact(repo, "latest_hw_emu_readiness", newest_readiness(repo, "hw_emu")),
        artifact(repo, "latest_hw_emu_monitor", newest_glob(repo, ".tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_*.txt")),
        artifact(repo, "latest_hw_target_flow_env", newest_glob(repo, ".tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_*.env")),
        artifact(repo, "latest_hw_readiness", newest_readiness(repo, "hw")),
        artifact(repo, "latest_hw_finalize_evidence", newest_glob(repo, ".tmp_build/pure_pipeline_hw_stage0/run_logs/finalize_*_evidence.tsv")),
    ]
    for target in TARGETS:
        artifacts.extend([
            targets[target]["xclbin"],
            targets[target]["manifest"],
            targets[target]["compile_commands"],
            targets[target]["link_command"],
            targets[target]["smoke_summary_artifact"],
            targets[target]["run_env"],
        ])

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "label": label,
        "repo": str(repo),
        "git": {
            "branch": git_branch,
            "head": git_head,
            "short_head": git_short,
            "dirty": dirty,
        },
        "targets": targets,
        "source_proofs": proofs,
        "baselines": {
            "host": host,
            "spine": spine,
            "same_input": same_input,
            "boundary_prepare": boundary_prepare,
            "three_way_comparison": artifact(repo, "three_way_comparison_tsv", three_way_path),
            "zero_vs_spine_comparison": artifact(repo, "zero_vs_spine_comparison_tsv", zero_vs_spine_path),
        },
        "requirements": requirements,
        "artifacts": artifacts,
        "next_commands": [
            "./scripts/check_pure_pipeline_source_contracts.py --label after_" + git_short,
            "./scripts/check_pure_pipeline_xclbin_contract.py --target sw_emu --label after_" + git_short,
            "./scripts/check_smoke_input_identity.py --label after_" + git_short,
            "./scripts/refresh_pure_pipeline_readiness_bundle.sh --label refresh_after_" + git_short,
            "./scripts/run_pure_pipeline_prepare_check.sh --preset boundary --out-dir results/pure_pipeline_prepare_boundary_after_" + git_short,
            "./scripts/check_pure_pipeline_build_readiness.sh --target hw_emu --label after_" + git_short,
            "./scripts/run_pure_pipeline_target_flow.sh --target hw_emu --label after_" + git_short + " --prepare --wait-idle 7200 --idle-poll 60 --idle-settle 120 --clean-build-artifacts --gate-case tiny_star_v16_u12 --gate-timeout 900",
            "./scripts/check_pure_pipeline_build_readiness.sh --target hw --label after_" + git_short,
            "./scripts/run_pure_pipeline_target_flow.sh --target hw --label after_" + git_short + " --prepare --wait-idle 7200 --idle-poll 60 --idle-settle 120 --clean-build-artifacts --gate-case tiny_star_v16_u12 --gate-timeout 300",
            "./scripts/export_pure_pipeline_evidence_bundle.py --out-dir results/pure_pipeline_evidence_bundle_after_" + git_short,
        ],
    }


def status_counts(requirements: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for req in requirements:
        counts[req["status"]] = counts.get(req["status"], 0) + 1
    return counts


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


def write_markdown(repo: Path, path: Path, audit: dict[str, Any]) -> None:
    counts = status_counts(audit["requirements"])
    req_rows = []
    for req in audit["requirements"]:
        req_rows.append([
            str(req["id"]),
            req["status"],
            req["title"],
            "<br>".join(req["gaps"]) if req["gaps"] else "",
        ])

    target_rows = []
    for target in TARGETS:
        state = audit["targets"][target]
        summary = state["smoke_summary"]
        target_rows.append([
            target,
            "yes" if state["xclbin"]["exists"] else "no",
            state["xclbin"]["sha256"] or "",
            "yes" if summary["all_expected_pass"] else "no",
            summary["path"],
        ])

    proof_rows = []
    for name, proof in sorted(audit["source_proofs"].items()):
        paths = proof.get("paths")
        if paths is None:
            paths = [proof.get("path", "")]
        proof_rows.append([
            name,
            "yes" if proof.get("ok") else "no",
            str(proof.get("contract", "")),
            "<br>".join(str(path) for path in paths if path),
        ])

    artifact_rows = []
    for item in audit["artifacts"]:
        artifact_rows.append([
            item["name"],
            "yes" if item["exists"] else "no",
            item["sha256"] or "",
            item["path"],
        ])

    command_block = "\n".join(audit["next_commands"])
    lines = [
        "# Pure Pipeline Requirement Audit",
        "",
        f"Generated: `{audit['generated_at']}`",
        f"Repository: `{repo}`",
        f"Branch: `{audit['git']['branch']}`",
        f"Commit: `{audit['git']['head']}`",
        f"Dirty: `{audit['git']['dirty']}`",
        "",
        "## Status Counts",
        "",
        markdown_table(["status", "count"], [[key, str(counts[key])] for key in sorted(counts)]),
        "",
        "## Requirement Matrix",
        "",
        markdown_table(["id", "status", "requirement", "current gap"], req_rows),
        "",
        "## Target Matrix",
        "",
        markdown_table(["target", "xclbin_exists", "xclbin_sha256", "smoke_pass", "smoke_summary"], target_rows),
        "",
        "## Source Proofs",
        "",
        markdown_table(["proof", "ok", "contract", "path"], proof_rows),
        "",
        "## Key Artifacts",
        "",
        markdown_table(["name", "exists", "sha256", "path"], artifact_rows),
        "",
        "## Next Commands",
        "",
        "```bash",
        "cd " + str(repo),
        command_block,
        "```",
        "",
        "## Interpretation",
        "",
        "The current state is intentionally conservative: the pure pipeline has",
        "`sw_emu` correctness evidence, while `hw_emu` and `hw` pure-pipeline",
        "xclbins are not present yet. Therefore the final hardware requirements",
        "remain partial or blocked until those artifacts are built and finalized.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--label", default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    label = args.label or run_git(repo, ["rev-parse", "--short", "HEAD"])
    out_dir = args.out_dir or repo / "results" / f"pure_pipeline_requirement_audit_{label}"
    if not out_dir.is_absolute():
        out_dir = repo / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    audit = build_audit(repo, label)
    json_path = out_dir / "audit.json"
    md_path = out_dir / "audit.md"
    json_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="ascii")
    write_markdown(repo, md_path, audit)

    print(f"audit_json={display_path(repo, json_path)}")
    print(f"audit_md={display_path(repo, md_path)}")
    print("status_counts=" + json.dumps(status_counts(audit["requirements"]), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
