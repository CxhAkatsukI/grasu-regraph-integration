#!/usr/bin/env python3
"""Generate deterministic GraSU + ReGraph SSSP benchmark workloads."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


INF = 2_147_483_646


@dataclass(frozen=True)
class CaseSpec:
    name: str
    family: str
    vertices: int
    updates: int
    supersteps: int
    source: int = 0
    weight: int = 1


PRESETS: dict[str, list[CaseSpec]] = {
    "smoke": [
        CaseSpec("tiny_chain_v16", "chain", 16, 0, 16),
        CaseSpec("tiny_star_v16_u12", "hot-source", 16, 12, 2),
        CaseSpec("tiny_hotdst_v64_u32", "hot-dest", 64, 32, 16),
    ],
    "review": [
        CaseSpec("small_chain_v64", "chain", 64, 0, 64),
        CaseSpec("small_star_v4096_u1024", "hot-source", 4096, 1024, 2),
        CaseSpec("small_spread_v4096_u1024", "spread", 4096, 1024, 16),
        CaseSpec("small_hotdst_v4096_u1024", "hot-dest", 4096, 1024, 32),
        CaseSpec("medium_star_v65536_u8192", "hot-source", 65536, 8192, 2),
        CaseSpec("medium_spread_v65536_u16384", "spread", 65536, 16384, 32),
    ],
}


def dedupe_sorted(edges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return sorted(set(edges))


def build_case(spec: CaseSpec) -> tuple[list[tuple[int, int]], list[tuple[int, int, int]], list[tuple[int, int]]]:
    if spec.vertices < 2:
        raise ValueError("vertices must be at least 2")
    if spec.source < 0 or spec.source >= spec.vertices:
        raise ValueError(f"{spec.name}: invalid source {spec.source}")

    static_edges: list[tuple[int, int]]
    updates: list[tuple[int, int, int]] = []

    if spec.family == "chain":
        static_edges = [(i, i + 1) for i in range(spec.vertices - 1)]
    elif spec.family == "hot-source":
        static_edges = [(i, (i + 1) % spec.vertices) for i in range(spec.vertices)]
        fanout = min(spec.updates, max(0, spec.vertices - 2))
        updates = [(spec.source, dst, 1) for dst in range(2, 2 + fanout)]
    elif spec.family == "spread":
        static_edges = [(i, (i + 1) % spec.vertices) for i in range(spec.vertices)]
        for i in range(spec.updates):
            src = i % spec.vertices
            hop = 2 + (i // spec.vertices)
            dst = (src + hop) % spec.vertices
            if dst == src:
                dst = (dst + 1) % spec.vertices
            if dst == (src + 1) % spec.vertices:
                dst = (dst + 1) % spec.vertices
            updates.append((src, dst, 1))
    elif spec.family == "hot-dest":
        static_edges = [(i, i + 1) for i in range(spec.vertices - 1)]
        hot_dst = spec.vertices - 1
        usable_sources = max(1, spec.vertices - 2)
        for i in range(spec.updates):
            src = 1 + (i % usable_sources)
            if src != hot_dst:
                updates.append((src, hot_dst, 1))
    else:
        raise ValueError(f"{spec.name}: unknown family {spec.family}")

    final_edges = set(static_edges)
    for src, dst, typ in updates:
        if typ == 0:
            final_edges.discard((src, dst))
        else:
            final_edges.add((src, dst))

    return dedupe_sorted(static_edges), updates, dedupe_sorted(list(final_edges))


def expected_distances(vertices: int, edges: list[tuple[int, int]], source: int, weight: int, supersteps: int) -> list[int]:
    dist = [INF] * vertices
    dist[source] = 0
    for _ in range(supersteps):
        next_dist = dist[:]
        for src, dst in edges:
            if dist[src] == INF:
                continue
            cand = dist[src] + weight
            if cand < next_dist[dst]:
                next_dist[dst] = cand
        dist = next_dist
    return dist


def write_case(out_root: Path, spec: CaseSpec) -> dict[str, str | int]:
    static_edges, updates, final_edges = build_case(spec)
    case_dir = out_root / spec.name
    case_dir.mkdir(parents=True, exist_ok=True)

    graph_path = case_dir / f"{spec.name}.graph"
    result_path = case_dir / f"{spec.name}.result"
    regraph_path = case_dir / f"{spec.name}.sssp.edges"
    expected_path = case_dir / f"{spec.name}.expected.tsv"
    metadata_path = case_dir / f"{spec.name}.json"

    with graph_path.open("w", encoding="ascii") as out:
        out.write(f"{spec.vertices} {len(static_edges)} {len(updates)}\n")
        for src, dst in static_edges:
            out.write(f"{src} {dst}\n")
        for src, dst, typ in updates:
            out.write(f"{src} {dst} {typ}\n")

    with result_path.open("w", encoding="ascii") as out:
        for src, dst in final_edges:
            out.write(f"{src:x} -> {dst:x}\n")

    with regraph_path.open("w", encoding="ascii") as out:
        for src, dst in final_edges:
            out.write(f"{src} {dst} {spec.weight}\n")

    distances = expected_distances(spec.vertices, final_edges, spec.source, spec.weight, spec.supersteps)
    with expected_path.open("w", encoding="ascii") as out:
        out.write("vertex\tdistance_after_supersteps\n")
        for vertex, distance in enumerate(distances):
            out.write(f"{vertex}\t{distance if distance != INF else 'INF'}\n")

    row: dict[str, str | int] = {
        "case": spec.name,
        "family": spec.family,
        "vertices": spec.vertices,
        "static_edges": len(static_edges),
        "update_edges": len(updates),
        "final_edges": len(final_edges),
        "source": spec.source,
        "supersteps": spec.supersteps,
        "default_weight": spec.weight,
        "graph": str(graph_path.resolve()),
        "result": str(result_path.resolve()),
        "regraph_sssp_edges": str(regraph_path.resolve()),
        "expected": str(expected_path.resolve()),
        "metadata": str(metadata_path.resolve()),
    }

    metadata = {
        **row,
        "intent": scenario_intent(spec.family),
        "unit_weight_note": "Use unit weights for fair SSSP comparison with Spine.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return row


def scenario_intent(family: str) -> str:
    if family == "chain":
        return "High-diameter graph: stresses fixed per-superstep overhead and many SSSP levels."
    if family == "hot-source":
        return "Low-diameter fanout from the source: stresses broad early frontier and edge throughput."
    if family == "spread":
        return "Updates spread across vertices: tests balanced partition traffic."
    if family == "hot-dest":
        return "Many updates converge on one destination: stresses gather/min reduction hot spot behavior."
    return "General SSSP workload."


def write_manifest(out_root: Path, rows: list[dict[str, str | int]]) -> Path:
    manifest = out_root / "manifest.tsv"
    fields = [
        "case",
        "family",
        "vertices",
        "static_edges",
        "update_edges",
        "final_edges",
        "source",
        "supersteps",
        "default_weight",
        "graph",
        "result",
        "regraph_sssp_edges",
        "expected",
        "metadata",
    ]
    with manifest.open("w", encoding="ascii") as out:
        out.write("\t".join(fields) + "\n")
        for row in rows:
            out.write("\t".join(str(row[field]) for field in fields) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=sorted(PRESETS), default="smoke")
    parser.add_argument("--out-root", type=Path, default=None)
    args = parser.parse_args()

    out_root = args.out_root
    if out_root is None:
        out_root = Path("workloads") / f"sssp_benchmark_{args.preset}"
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    rows = [write_case(out_root, spec) for spec in PRESETS[args.preset]]
    manifest = write_manifest(out_root, rows)
    print(f"preset={args.preset} cases={len(rows)} manifest={manifest}")
    for row in rows:
        print(
            "case={case} family={family} vertices={vertices} "
            "updates={update_edges} final_edges={final_edges} supersteps={supersteps}".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
