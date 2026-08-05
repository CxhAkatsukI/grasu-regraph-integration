#!/usr/bin/env python3
"""Combine Spine initial/update slices into the weighted PMA host format."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_slice(path: Path) -> tuple[int, list[tuple[int, int, int, int]]]:
    vertices: int | None = None
    rows: list[tuple[int, int, int, int]] = []
    for line_number, raw in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            metadata = line[1:].strip()
            if metadata.startswith("vertices="):
                vertices = int(metadata.split("=", 1)[1])
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"{path}:{line_number}: expected src dst weight diff")
        src, dst, weight, diff = map(int, fields)
        rows.append((src, dst, weight, diff))
    if vertices is None or vertices <= 0:
        raise ValueError(f"{path}: missing positive vertices metadata")
    for src, dst, weight, diff in rows:
        if not (0 <= src < vertices and 0 <= dst < vertices):
            raise ValueError(f"{path}: edge ({src}, {dst}) is out of range")
        if not (1 <= weight <= 4095):
            raise ValueError(f"{path}: weight {weight} exceeds the weight12 ABI")
        if diff not in (-1, 1):
            raise ValueError(f"{path}: diff must be -1 or 1")
    return vertices, rows


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
    initial_vertices, initial_rows = read_slice(initial)
    update_vertices, update_rows = read_slice(update)
    if initial_vertices != update_vertices:
        raise ValueError("initial and update slices have different vertex counts")
    if any(diff != 1 for _, _, _, diff in initial_rows):
        raise ValueError("initial slice may contain only positive edges")
    if reciprocal:
        initial_rows, update_rows = reciprocal_simple_graph(
            initial_rows, update_rows
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{initial_vertices} {len(initial_rows)} {len(update_rows)}"]
    lines.extend(f"{src} {dst} {weight}" for src, dst, weight, _ in initial_rows)
    lines.extend(
        f"{src} {dst} {weight} {1 if diff == 1 else 0}"
        for src, dst, weight, diff in update_rows
    )
    output.write_text("\n".join(lines) + "\n", encoding="ascii")

    manifest: dict[str, object] = {
        "schema_version": 1,
        "vertices": initial_vertices,
        "initial_edges": len(initial_rows),
        "updates": len(update_rows),
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
