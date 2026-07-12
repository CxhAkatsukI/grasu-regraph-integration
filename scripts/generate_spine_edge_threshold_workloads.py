#!/usr/bin/env python3
"""Generate edge-file workloads for probing Spine batching thresholds."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaseSpec:
    name: str
    family: str
    vertices: int
    updates: int = 0
    weight: int = 1


DEFAULT_CASES = [
    CaseSpec("chain_v98305_e98304", "chain", 98_305),
    CaseSpec("chain_v131074_e131073", "chain", 131_074),
    CaseSpec("hotdst_v65536_u16384", "hot-dest", 65_536, 16_384),
    CaseSpec("hotdst_v98304_u32768_e131071", "hot-dest", 98_304, 32_768),
    CaseSpec("hotdst_v98304_u32770_e131073", "hot-dest", 98_304, 32_770),
    CaseSpec("hotdst_v131072_u32768_e163839", "hot-dest", 131_072, 32_768),
]

LARGE_CASES = [
    CaseSpec("chain_v262144_e262143", "chain", 262_144),
    CaseSpec("hotdst_v262144_u65536_e327679", "hot-dest", 262_144, 65_536),
]


def build_edges(spec: CaseSpec) -> list[tuple[int, int]]:
    if spec.vertices < 2:
        raise ValueError(f"{spec.name}: vertices must be at least 2")

    edges = {(src, src + 1) for src in range(spec.vertices - 1)}
    if spec.family == "chain":
        if spec.updates:
            raise ValueError(f"{spec.name}: chain does not use updates")
    elif spec.family == "hot-dest":
        hot_dst = spec.vertices - 1
        usable_sources = spec.vertices - 2
        if spec.updates > usable_sources:
            raise ValueError(
                f"{spec.name}: updates={spec.updates} exceeds usable sources={usable_sources}"
            )
        for i in range(spec.updates):
            edges.add((1 + i, hot_dst))
    else:
        raise ValueError(f"{spec.name}: unknown family {spec.family}")
    return sorted(edges)


def write_case(out_root: Path, spec: CaseSpec) -> dict[str, object]:
    edges = build_edges(spec)
    case_dir = out_root / spec.name
    case_dir.mkdir(parents=True, exist_ok=True)

    edge_path = case_dir / f"{spec.name}.from_grasu.sssp.edges"
    with edge_path.open("w", encoding="ascii") as out:
        for src, dst in edges:
            out.write(f"{src} {dst} {spec.weight}\n")

    row: dict[str, object] = {
        "case": spec.name,
        "family": spec.family,
        "vertices": spec.vertices,
        "updates": spec.updates,
        "edges": len(edges),
        "weight": spec.weight,
        "edge_file": str(edge_path.resolve()),
    }
    (case_dir / f"{spec.name}.json").write_text(
        json.dumps(row, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument(
        "--include-large",
        action="store_true",
        help="Also emit known-slow larger two/three-batch cases.",
    )
    args = parser.parse_args()

    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    cases = list(DEFAULT_CASES)
    if args.include_large:
        cases.extend(LARGE_CASES)

    rows = [write_case(out_root, spec) for spec in cases]
    manifest = out_root / "manifest.tsv"
    with manifest.open("w", encoding="ascii") as out:
        out.write("case\tfamily\tvertices\tupdates\tedges\tweight\tedge_file\n")
        for row in rows:
            out.write(
                "{case}\t{family}\t{vertices}\t{updates}\t{edges}\t{weight}\t{edge_file}\n".format(
                    **row
                )
            )

    print(f"cases={len(rows)} manifest={manifest}")
    for row in rows:
        print(
            "case={case} family={family} vertices={vertices} updates={updates} edges={edges}".format(
                **row
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
