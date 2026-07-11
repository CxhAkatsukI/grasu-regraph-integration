#!/usr/bin/env python3
"""Convert GraSU final-result lines into a ReGraph edge-list file."""

import argparse
import re
from pathlib import Path


EDGE_RE = re.compile(r"^\s*([0-9a-fA-FxX]+)\s*->\s*([0-9a-fA-FxX]+)\s*$")


def parse_int(text: str, base: str) -> int:
    if base == "auto":
        if text.lower().startswith("0x"):
            return int(text, 16)
        has_hex_letter = any(c in "abcdefABCDEF" for c in text)
        return int(text, 16 if has_hex_letter else 10)
    return int(text, int(base))


def convert(result_path: Path, out_path: Path, base: str, weight: int | None):
    edges = []
    with result_path.open("r", encoding="ascii") as src:
        for line_no, line in enumerate(src, 1):
            if not line.strip():
                continue
            match = EDGE_RE.match(line)
            if not match:
                raise ValueError(f"{result_path}:{line_no}: invalid edge line: {line.rstrip()}")
            edges.append((parse_int(match.group(1), base), parse_int(match.group(2), base)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="ascii") as dst:
        for src, sink in edges:
            if weight is None:
                dst.write(f"{src} {sink}\n")
            else:
                dst.write(f"{src} {sink} {weight}\n")

    return len(edges)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--base",
        choices=("auto", "10", "16"),
        default="16",
        help="GraSU result vertex-id base. Generated workloads use base 16.",
    )
    parser.add_argument(
        "--weight",
        type=int,
        default=None,
        help="When set, emit three-column weighted edges with this default weight.",
    )
    args = parser.parse_args()

    if args.weight is not None and args.weight < 0:
        raise SystemExit("--weight must be non-negative")

    edge_count = convert(Path(args.input), Path(args.output), args.base, args.weight)
    print(f"converted_edges={edge_count} output={args.output}")


if __name__ == "__main__":
    main()
