#!/usr/bin/env python3
"""Classify Spine edge files by partitioned ratio-2 level capacity."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


COLUMNS = [
    "case",
    "status",
    "raw_edges",
    "batches",
    "final_edges",
    "final_max_level",
    "max_partition_edges",
    "first_failure_batch",
    "failure_level",
    "failure_partition",
    "failure_partition_edges",
    "failure_partition_capacity",
    "failure_reason",
    "edge_file",
]


@dataclass(frozen=True)
class Edge:
    src: int
    dst: int
    weight: int
    diff: int


@dataclass
class AnalysisResult:
    case: str
    status: str
    raw_edges: int
    batches: int
    final_edges: int = 0
    final_max_level: int = -1
    max_partition_edges: int = 0
    first_failure_batch: int = 0
    failure_level: int = -1
    failure_partition: int = -1
    failure_partition_edges: int = 0
    failure_partition_capacity: int = 0
    failure_reason: str = ""
    edge_file: str = ""

    def as_row(self) -> dict[str, str]:
        return {
            "case": self.case,
            "status": self.status,
            "raw_edges": str(self.raw_edges),
            "batches": str(self.batches),
            "final_edges": str(self.final_edges),
            "final_max_level": str(self.final_max_level),
            "max_partition_edges": str(self.max_partition_edges),
            "first_failure_batch": str(self.first_failure_batch),
            "failure_level": str(self.failure_level),
            "failure_partition": str(self.failure_partition),
            "failure_partition_edges": str(self.failure_partition_edges),
            "failure_partition_capacity": str(self.failure_partition_capacity),
            "failure_reason": self.failure_reason,
            "edge_file": self.edge_file,
        }


def parse_edge_file(path: Path, max_sort_n: int) -> tuple[list[list[Edge]], int]:
    batches: list[list[Edge]] = []
    batch: list[Edge] = []
    raw_edges = 0
    with path.open("r", encoding="ascii", errors="replace") as infile:
        for line_no, line in enumerate(infile, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                raise ValueError(f"{path}: missing dst at line {line_no}")
            if len(parts) > 4:
                raise ValueError(f"{path}: extra token at line {line_no}")
            src = int(parts[0], 0)
            dst = int(parts[1], 0)
            weight = int(parts[2], 0) if len(parts) >= 3 else 1
            diff = int(parts[3], 0) if len(parts) >= 4 else 1
            batch.append(Edge(src, dst, weight, diff))
            raw_edges += 1
            if len(batch) == max_sort_n:
                batches.append(batch)
                batch = []
    if batch:
        batches.append(batch)
    if raw_edges == 0:
        raise ValueError(f"{path}: no edges")
    return batches, raw_edges


def sort_and_coalesce(edges: Iterable[Edge]) -> list[Edge]:
    sorted_edges = sorted(edges, key=lambda e: (e.src, e.dst, e.weight, e.diff))
    compacted: list[Edge] = []
    pos = 0
    while pos < len(sorted_edges):
        cur = sorted_edges[pos]
        diff_sum = 0
        weight = cur.weight
        while (
            pos < len(sorted_edges)
            and sorted_edges[pos].src == cur.src
            and sorted_edges[pos].dst == cur.dst
        ):
            diff_sum += sorted_edges[pos].diff
            weight = min(weight, sorted_edges[pos].weight)
            pos += 1
        if diff_sum != 0:
            if diff_sum < -32768 or diff_sum > 32767:
                raise ValueError("duplicate diff sum exceeds int16")
            compacted.append(Edge(cur.src, cur.dst, weight, diff_sum))
    return compacted


def level_total_capacity(level: int, max_sort_n: int, ratio: int) -> int:
    return max_sort_n * (ratio**level)


def level_partition_capacity(
    level: int, max_sort_n: int, ratio: int, partitions: int
) -> int:
    if level == 0:
        return max_sort_n
    total = level_total_capacity(level, max_sort_n, ratio)
    return (total + partitions - 1) // partitions


def first_empty_level(occupied: list[bool]) -> int:
    for level, is_occupied in enumerate(occupied):
        if not is_occupied:
            return level
    return -1


def dst_partition(dst: int, vs_partition_size: int, partitions: int) -> int:
    partition = dst // vs_partition_size
    if partition < 0 or partition >= partitions:
        return -1
    return partition


def partition_counts(
    edges: Iterable[Edge], vs_partition_size: int, partitions: int
) -> tuple[list[int], int]:
    counts = [0] * partitions
    invalid = 0
    for edge in edges:
        partition = dst_partition(edge.dst, vs_partition_size, partitions)
        if partition < 0:
            invalid += 1
        else:
            counts[partition] += 1
    return counts, invalid


def infer_case_name(path: Path) -> str:
    parent = path.parent.name
    suffix = ".from_grasu.sssp.edges"
    if path.name.endswith(suffix):
        return path.name[: -len(suffix)]
    if parent:
        return parent
    return path.stem


def analyze_path(
    path: Path,
    *,
    max_sort_n: int,
    ratio: int,
    levels_count: int,
    partitions: int,
    vs_partition_size: int,
) -> AnalysisResult:
    raw_batches, raw_edges = parse_edge_file(path, max_sort_n)
    batches: list[list[Edge]] = []
    result = AnalysisResult(
        case=infer_case_name(path),
        status="FITS",
        raw_edges=raw_edges,
        batches=len(raw_batches),
        edge_file=str(path),
    )
    try:
        for batch in raw_batches:
            batches.append(sort_and_coalesce(batch))
    except ValueError as exc:
        result.status = "INVALID_INPUT"
        result.failure_reason = str(exc)
        return result

    levels: list[list[Edge]] = [[] for _ in range(levels_count)]
    occupied = [False] * levels_count

    for batch_index, batch in enumerate(batches, 1):
        target = first_empty_level(occupied)
        if target < 0:
            result.status = "UNSUPPORTED_CAPACITY"
            result.first_failure_batch = batch_index
            result.failure_reason = "all_levels_occupied"
            return result

        carry: list[Edge] = list(batch)
        for level in range(target):
            carry.extend(levels[level])
        try:
            carry = sort_and_coalesce(carry)
        except ValueError as exc:
            result.status = "INVALID_INPUT"
            result.first_failure_batch = batch_index
            result.failure_level = target
            result.failure_reason = str(exc)
            return result

        total_cap = level_total_capacity(target, max_sort_n, ratio)
        if len(carry) > total_cap:
            result.status = "UNSUPPORTED_CAPACITY"
            result.first_failure_batch = batch_index
            result.failure_level = target
            result.failure_partition = -1
            result.failure_partition_edges = len(carry)
            result.failure_partition_capacity = total_cap
            result.failure_reason = "level_total_capacity"
            return result

        counts, invalid = partition_counts(carry, vs_partition_size, partitions)
        if invalid:
            result.status = "INVALID_INPUT"
            result.first_failure_batch = batch_index
            result.failure_level = target
            result.failure_reason = "dst_outside_partition_range"
            return result

        part_cap = level_partition_capacity(target, max_sort_n, ratio, partitions)
        max_partition_edges = max(counts) if counts else 0
        result.max_partition_edges = max(result.max_partition_edges, max_partition_edges)
        for partition, count in enumerate(counts):
            if count > part_cap:
                result.status = "UNSUPPORTED_CAPACITY"
                result.first_failure_batch = batch_index
                result.failure_level = target
                result.failure_partition = partition
                result.failure_partition_edges = count
                result.failure_partition_capacity = part_cap
                result.failure_reason = "level_partition_capacity"
                return result

        for level in range(target):
            levels[level] = []
            occupied[level] = False
        levels[target] = carry
        occupied[target] = bool(carry)

    result.final_edges = sum(len(level) for level in levels)
    result.final_max_level = max((i for i, level in enumerate(levels) if level), default=-1)
    return result


def collect_paths(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = [Path(p).resolve() for p in args.edge_files]
    for root_s in args.chain_root:
        root = Path(root_s).resolve()
        paths.extend(sorted(root.glob("*/*.from_grasu.sssp.edges")))
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path not in seen:
            deduped.append(path)
            seen.add(path)
    return deduped


def write_rows(results: list[AnalysisResult], output: Path | None) -> None:
    lines = ["\t".join(COLUMNS)]
    for result in results:
        row = result.as_row()
        lines.append("\t".join(row[col] for col in COLUMNS))
    text = "\n".join(lines) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edge_files", nargs="*", help="Edge files to analyze.")
    parser.add_argument(
        "--chain-root",
        action="append",
        default=[],
        help="Result root containing */*.from_grasu.sssp.edges files.",
    )
    parser.add_argument("--out", type=Path, help="Write TSV to this path.")
    parser.add_argument("--max-sort-n", type=int, default=131072)
    parser.add_argument("--ratio", type=int, default=2)
    parser.add_argument("--levels", type=int, default=11)
    parser.add_argument("--partitions", type=int, default=16)
    parser.add_argument("--vs-partition-size", type=int, default=1048576)
    args = parser.parse_args()

    paths = collect_paths(args)
    if not paths:
        parser.error("provide edge files or --chain-root")

    results = [
        analyze_path(
            path,
            max_sort_n=args.max_sort_n,
            ratio=args.ratio,
            levels_count=args.levels,
            partitions=args.partitions,
            vs_partition_size=args.vs_partition_size,
        )
        for path in paths
    ]
    write_rows(results, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
