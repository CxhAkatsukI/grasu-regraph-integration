#!/usr/bin/env python3
"""Check pure-pipeline xclbin metadata against the required kernel contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


TARGETS = ("sw_emu", "hw_emu", "hw")

REQUIRED_KERNELS = (
    "bin_search",
    "dispatch",
    "process_cache",
    "process_ddr",
    "pma_completion_barrier",
    "pma_to_regraph_adapter",
    "lksg_stream",
    "kernelLittleGSMerger",
    "kernelBigGSMerger",
    "bigKernelScatterGather",
    "kernelApply",
    "kernelHBMWrapper",
)

REQUIRED_INSTANCES = (
    "bin_search_1",
    "bin_search_2",
    "bin_search_3",
    "bin_search_4",
    "dispatch_1",
    "process_cache_1",
    "process_cache_2",
    "process_ddr_1",
    "process_ddr_2",
    "pma_completion_barrier_1",
    "pma_to_regraph_adapter_1",
    "lksg_stream_1",
    "kernelLittleGSMerger_1",
    "kernelBigGSMerger_1",
    "bigKernelScatterGather_1",
    "kernelApply_1",
    "kernelHBMWrapper_1",
)

REQUIRED_METADATA_NEEDLES = (
    "Content:                SW Emulation Binary",
    "Kernel: pma_to_regraph_adapter",
    "Signature: pma_to_regraph_adapter (void* pma0, void* pma1, void* pma2, void* pma3, void* row_offset, unsigned int node_count, unsigned int pma_slot_count, unsigned int max_cache_segment",
    "Argument:          edge_burst_out",
    "Kernel: pma_completion_barrier",
    "Argument:          done0",
    "Argument:          done1",
    "Argument:          done2",
    "Argument:          done3",
    "Kernel: process_cache",
    "Argument:          completion_token",
    "Kernel: process_ddr",
    "Kernel: lksg_stream",
    "Argument:          edge_burst_in",
)

REQUIRED_LINK_CONNECTIVITY = (
    "--connectivity.nk bin_search:4:bin_search_1.bin_search_2.bin_search_3.bin_search_4",
    "--connectivity.nk process_cache:2:process_cache_1.process_cache_2",
    "--connectivity.nk process_ddr:2:process_ddr_1.process_ddr_2",
    "--connectivity.nk pma_completion_barrier:1:pma_completion_barrier_1",
    "--connectivity.nk pma_to_regraph_adapter:1:pma_to_regraph_adapter_1",
    "--connectivity.nk lksg_stream:1:lksg_stream_1",
    "--connectivity.stream_connect process_cache_1.completion_token:pma_completion_barrier_1.done0:16",
    "--connectivity.stream_connect process_ddr_1.completion_token:pma_completion_barrier_1.done1:16",
    "--connectivity.stream_connect process_cache_2.completion_token:pma_completion_barrier_1.done2:16",
    "--connectivity.stream_connect process_ddr_2.completion_token:pma_completion_barrier_1.done3:16",
    "--connectivity.stream_connect pma_to_regraph_adapter_1.edge_burst_out:lksg_stream_1.edge_burst_in:32",
    "--connectivity.sp pma_to_regraph_adapter_1.pma0:HBM[0]",
    "--connectivity.sp pma_to_regraph_adapter_1.pma1:HBM[1]",
    "--connectivity.sp pma_to_regraph_adapter_1.pma2:HBM[2]",
    "--connectivity.sp pma_to_regraph_adapter_1.pma3:HBM[3]",
    "--connectivity.sp pma_to_regraph_adapter_1.row_offset:HBM[0]",
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(repo: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def default_xclbin(repo: Path, target: str) -> Path:
    return repo / f".tmp_build/pure_pipeline_{target}_stage0/build/grasu_regraph_pure_pipeline.{target}.xclbin"


def row(check: str, ok: bool, detail: str) -> dict[str, str]:
    return {"check": check, "ok": "yes" if ok else "no", "detail": detail}


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("check", "ok", "detail"), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for item in rows:
            writer.writerow(item)


def contains_all(text: str, needles: tuple[str, ...]) -> list[str]:
    return [needle for needle in needles if needle not in text]


def run_check(repo: Path, target: str, xclbin: Path, info: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    rows.append(row("xclbin_exists", xclbin.is_file(), display_path(repo, xclbin)))
    if xclbin.is_file():
        rows.append(row("xclbin_sha256", True, sha256(xclbin)))
    rows.append(row("info_exists", info.is_file(), display_path(repo, info)))
    if not info.is_file():
        return rows

    text = info.read_text(encoding="ascii", errors="replace")
    rows.append(row("info_sha256", True, sha256(info)))
    rows.append(row("target", target in text or target == "sw_emu", target))

    missing_kernels = [kernel for kernel in REQUIRED_KERNELS if f"Kernel: {kernel}" not in text and f"{kernel}," not in text]
    rows.append(row("required_kernels", not missing_kernels, ",".join(missing_kernels)))

    missing_instances = [instance for instance in REQUIRED_INSTANCES if f"Instance:        {instance}" not in text]
    rows.append(row("required_instances", not missing_instances, ",".join(missing_instances)))

    metadata_needles = REQUIRED_METADATA_NEEDLES
    if target != "sw_emu":
        metadata_needles = tuple(needle for needle in metadata_needles if not needle.startswith("Content:"))
    missing_metadata = contains_all(text, metadata_needles)
    rows.append(row("kernel_metadata_contract", not missing_metadata, " || ".join(missing_metadata)))

    missing_connectivity = contains_all(text, REQUIRED_LINK_CONNECTIVITY)
    rows.append(row("link_connectivity_contract", not missing_connectivity, " || ".join(missing_connectivity)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--target", choices=TARGETS, default="sw_emu")
    parser.add_argument("--xclbin", type=Path, default=None)
    parser.add_argument("--info", type=Path, default=None)
    parser.add_argument("--label", default=None)
    parser.add_argument("--out-file", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    target = args.target
    xclbin = args.xclbin if args.xclbin is not None else default_xclbin(repo, target)
    if not xclbin.is_absolute():
        xclbin = repo / xclbin
    info = args.info if args.info is not None else Path(str(xclbin) + ".info")
    if not info.is_absolute():
        info = repo / info
    label = args.label or target

    out_file = args.out_file
    if out_file is None:
        out_file = repo / ".tmp_build" / "pure_pipeline_xclbin_contracts" / f"xclbin_contract_{target}_{label}.tsv"
    elif not out_file.is_absolute():
        out_file = repo / out_file

    rows = run_check(repo, target, xclbin, info)
    write_tsv(out_file, rows)
    failed = [item["check"] for item in rows if item["ok"] != "yes"]

    print("pure_pipeline_xclbin_contract")
    print(f"target={target}")
    print(f"xclbin={display_path(repo, xclbin)}")
    print(f"info={display_path(repo, info)}")
    print(f"out_file={display_path(repo, out_file)}")
    print(f"check_count={len(rows)}")
    print(f"failed_count={len(failed)}")
    for item in rows:
        print(f"check={item['check']} ok={item['ok']}")
    if failed:
        print("FAILED checks=" + ",".join(failed))
        return 3
    print("PASS xclbin contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
