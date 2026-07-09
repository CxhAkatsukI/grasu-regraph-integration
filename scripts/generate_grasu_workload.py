#!/usr/bin/env python3
"""Generate a small GraSU graph/update workload and final-result file."""

import argparse
from pathlib import Path


def build_edges(vertices: int, updates: int, shape: str):
    if vertices < 4:
        raise ValueError("vertices must be at least 4")
    if updates < 0:
        raise ValueError("updates must be non-negative")

    static_edges = [(i, (i + 1) % vertices) for i in range(vertices)]
    update_edges = []

    if shape == "spread":
        for i in range(updates):
            src = i % vertices
            hop = 2 + (i // vertices)
            dst = (src + hop) % vertices
            if dst == src:
                dst = (dst + 1) % vertices
            if dst == (src + 1) % vertices:
                dst = (dst + 1) % vertices
            update_edges.append((src, dst, 1))
    elif shape == "hot":
        usable = max(1, vertices - 2)
        for i in range(min(updates, usable)):
            update_edges.append((0, 2 + (i % usable), 1))
    elif shape == "delete-even":
        for i in range(min(updates, vertices)):
            src = (2 * i) % vertices
            update_edges.append((src, (src + 1) % vertices, 0))
    else:
        raise ValueError(f"unknown shape: {shape}")

    final_edges = set(static_edges)
    for src, dst, typ in update_edges:
        if typ == 0:
            final_edges.discard((src, dst))
        else:
            final_edges.add((src, dst))

    return static_edges, update_edges, sorted(final_edges)


def write_workload(out_dir: Path, case: str, vertices: int, updates: int, shape: str):
    static_edges, update_edges, final_edges = build_edges(vertices, updates, shape)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph_path = out_dir / f"{case}.graph"
    result_path = out_dir / f"{case}.result"

    with graph_path.open("w", encoding="ascii") as graph:
        graph.write(f"{vertices} {len(static_edges)} {len(update_edges)}\n")
        for src, dst in static_edges:
            graph.write(f"{src} {dst}\n")
        for src, dst, typ in update_edges:
            graph.write(f"{src} {dst} {typ}\n")

    # GraSU's checker uses %lx, so final-result IDs are written as hex.
    with result_path.open("w", encoding="ascii") as result:
        for src, dst in final_edges:
            result.write(f"{src:x} -> {dst:x}\n")

    return graph_path, result_path, len(static_edges), len(update_edges), len(final_edges)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--case", default="tiny_spread_v16_u8")
    parser.add_argument("--vertices", type=int, default=16)
    parser.add_argument("--updates", type=int, default=8)
    parser.add_argument(
        "--shape",
        choices=("spread", "hot", "delete-even"),
        default="spread",
    )
    args = parser.parse_args()

    graph, result, static_n, update_n, final_n = write_workload(
        Path(args.out_dir), args.case, args.vertices, args.updates, args.shape)
    print(
        f"case={args.case} graph={graph} result={result} "
        f"vertices={args.vertices} static={static_n} updates={update_n} final={final_n}"
    )


if __name__ == "__main__":
    main()

