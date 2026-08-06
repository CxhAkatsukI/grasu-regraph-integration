#!/usr/bin/env python3
"""Combine Spine initial/update slices into the weighted PMA host format."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_slice_rows(path: Path):
    with path.open("r", encoding="ascii") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 4:
                raise ValueError(
                    f"{path}:{line_number}: expected src dst weight diff"
                )
            yield line_number, tuple(map(int, fields))


def scan_slice(path: Path) -> tuple[int, int, bool]:
    vertices: int | None = None
    with path.open("r", encoding="ascii") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith("#"):
                metadata = line[1:].strip()
                if metadata.startswith("vertices="):
                    vertices = int(metadata.split("=", 1)[1])
    if vertices is None or vertices <= 0:
        raise ValueError(f"{path}: missing positive vertices metadata")

    row_count = 0
    all_positive = True
    for line_number, row in iter_slice_rows(path):
        src, dst, weight, diff = row
        if not (0 <= src < vertices and 0 <= dst < vertices):
            raise ValueError(
                f"{path}:{line_number}: edge ({src}, {dst}) is out of range"
            )
        if not (1 <= weight <= 4095):
            raise ValueError(
                f"{path}:{line_number}: weight {weight} exceeds the weight12 ABI"
            )
        if diff not in (-1, 1):
            raise ValueError(f"{path}:{line_number}: diff must be -1 or 1")
        all_positive = all_positive and diff == 1
        row_count += 1
    return vertices, row_count, all_positive


def read_slice(path: Path) -> tuple[int, list[tuple[int, int, int, int]]]:
    vertices, _, _ = scan_slice(path)
    return vertices, [row for _, row in iter_slice_rows(path)]


def reciprocal_simple_graph(
    initial: list[tuple[int, int, int, int]],
    updates: list[tuple[int, int, int, int]],
) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    state: set[tuple[int, int]] = set()
    reciprocal_initial: list[tuple[int, int, int, int]] = []
    for src, dst, _weight, _diff in initial:
        variants = ((src, dst),) if src == dst else ((src, dst), (dst, src))
        for key in variants:
            if key not in state:
                state.add(key)
                reciprocal_initial.append((key[0], key[1], 1, 1))

    reciprocal_updates: list[tuple[int, int, int, int]] = []
    for src, dst, _weight, diff in updates:
        variants = ((src, dst),) if src == dst else ((src, dst), (dst, src))
        for key in variants:
            present = key in state
            if diff == 1 and not present:
                state.add(key)
                reciprocal_updates.append((key[0], key[1], 1, 1))
            elif diff == -1 and present:
                state.remove(key)
                reciprocal_updates.append((key[0], key[1], 1, -1))
    return reciprocal_initial, reciprocal_updates


def convert(
    initial: Path,
    update: Path,
    output: Path,
    metadata: Path,
    reciprocal: bool = False,
) -> dict[str, object]:
    initial_vertices, initial_count, initial_all_positive = scan_slice(initial)
    update_vertices, update_count, _ = scan_slice(update)
    if initial_vertices != update_vertices:
        raise ValueError("initial and update slices have different vertex counts")
    if not initial_all_positive:
        raise ValueError("initial slice may contain only positive edges")

    if reciprocal:
        _, initial_rows = read_slice(initial)
        _, update_rows = read_slice(update)
        initial_rows, update_rows = reciprocal_simple_graph(
            initial_rows, update_rows
        )
        initial_count = len(initial_rows)
        update_count = len(update_rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="ascii") as handle:
        handle.write(f"{initial_vertices} {initial_count} {update_count}\n")
        initial_source = (
            enumerate(initial_rows) if reciprocal else iter_slice_rows(initial)
        )
        for _, (src, dst, weight, diff) in initial_source:
            if diff != 1:
                raise ValueError("initial slice may contain only positive edges")
            handle.write(f"{src} {dst} {weight}\n")
        update_source = (
            enumerate(update_rows) if reciprocal else iter_slice_rows(update)
        )
        for _, (src, dst, weight, diff) in update_source:
            handle.write(f"{src} {dst} {weight} {1 if diff == 1 else 0}\n")

    manifest: dict[str, object] = {
        "schema_version": 1,
        "vertices": initial_vertices,
        "initial_edges": initial_count,
        "updates": update_count,
        "initial_slice": str(initial.resolve()),
        "initial_slice_sha256": sha256(initial),
        "update_slice": str(update.resolve()),
        "update_slice_sha256": sha256(update),
        "pma_graph": str(output.resolve()),
        "pma_graph_sha256": sha256(output),
        "operation_mapping": {"1": "insert", "-1": "delete"},
        "reciprocal_expansion": reciprocal,
        "reciprocal_semantics": (
            "unweighted simple graph; mirrored endpoint pairs; no-op updates removed"
            if reciprocal
            else "disabled"
        ),
        "conversion": "lossless format-only; vertex ids, weights, and order preserved",
        "streaming_conversion": not reciprocal,
    }
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial", type=Path, required=True)
    parser.add_argument("--update", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument(
        "--reciprocal",
        action="store_true",
        help="mirror every non-self edge and update for undirected CC semantics",
    )
    args = parser.parse_args()
    result = convert(
        args.initial, args.update, args.output, args.metadata, args.reciprocal
    )
    print(
        "SPINE_SLICES_TO_PMA_GRAPH_PASS "
        f"vertices={result['vertices']} initial={result['initial_edges']} "
        f"updates={result['updates']} output={args.output}"
    )


if __name__ == "__main__":
    main()
