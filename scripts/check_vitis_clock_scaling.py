#!/usr/bin/env python3
"""Reject silently scaled clocks in the frozen U55C/150-MHz configuration."""
import argparse
import hashlib
import json
import math
from pathlib import Path


EXPECTED = {
    ("kernel", "0", "ulp_ucs/aclk_kernel_00"): 150.0,
    ("kernel", "1", "ulp_ucs/aclk_kernel_01"): 500.0,
    ("system", "", "hbm_aclk"): 450.0,
}


def check(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    actual = {}
    for line in data.decode("ascii").splitlines():
        fields = line.split(":")
        if len(fields) != 4:
            raise ValueError("complete Vitis clock rows required")
        key = tuple(fields[:3])
        if key not in EXPECTED or key in actual:
            raise ValueError("unexpected or duplicate platform clock: " + repr(key))
        value = float(fields[3])
        if not math.isfinite(value) or value <= 0:
            raise ValueError("positive finite frequency required")
        actual[key] = value
    if actual.keys() != EXPECTED.keys():
        raise ValueError("all frozen platform clocks must be recorded")
    rows = [dict(kind=key[0], clock_id=key[1], name=key[2],
                 expected_mhz=value, achieved_mhz=actual[key])
            for key, value in EXPECTED.items()]
    return {"status": "FIXED_CLOCK_METADATA_PASS_NOT_TIMING_OR_BOARD_TESTED"
            if all(row["achieved_mhz"] == row["expected_mhz"] for row in rows)
            else "CLOCK_CONFIGURATION_MISMATCH",
            "source": {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
                       "size": len(data)}, "clocks": rows,
            "scope": "Vitis _new_clk_freq metadata; final checkpoint, xclbin and board checks remain required"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clock_file", type=Path)
    args = parser.parse_args()
    result = check(args.clock_file)
    print(json.dumps(result, indent=2))
    return 0 if result["status"].startswith("FIXED_CLOCK_METADATA_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
