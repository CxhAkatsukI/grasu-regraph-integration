#!/usr/bin/env python3
"""Fail closed when a Vitis XO exposes an unexpected AXI master count."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile


def master_interfaces(xo: Path) -> list[str]:
    with zipfile.ZipFile(xo) as archive:
        kernel_jsons = [name for name in archive.namelist() if name.endswith("/kernel.json")]
        if len(kernel_jsons) != 1:
            raise ValueError(f"expected one kernel.json in {xo}, found {len(kernel_jsons)}")
        metadata = json.loads(archive.read(kernel_jsons[0]))
    interfaces = metadata.get("Interfaces")
    if not isinstance(interfaces, dict):
        raise ValueError(f"missing Interfaces metadata in {xo}")
    return sorted(
        name
        for name, description in interfaces.items()
        if description.get("type") == "axi4" and description.get("mode") == "master"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xo", type=Path, required=True)
    parser.add_argument("--expected-masters", type=int, required=True)
    args = parser.parse_args()
    masters = master_interfaces(args.xo)
    if len(masters) != args.expected_masters:
        parser.error(
            f"{args.xo} exposes {len(masters)} AXI masters, expected "
            f"{args.expected_masters}: {','.join(masters)}"
        )
    print(f"PASS {args.xo.name}: AXI masters={len(masters)} {','.join(masters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
