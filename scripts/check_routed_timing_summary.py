"""Check routed setup/hold/pulse-width timing; not clocks or bus-skew signoff."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


FIELDS = ("wns_ns", "tns_ns", "setup_failing", "setup_total",
          "whs_ns", "ths_ns", "hold_failing", "hold_total",
          "wpws_ns", "tpws_ns", "pulse_failing", "pulse_total")


def parse_report(text):
    version = re.search(r"^\| Tool Version\s*: Vivado v\.([^ ]+)", text, re.M)
    state = re.search(r"^\| Design State\s*: (.+)$", text, re.M)
    if not version or version[1] != "2024.1" or not state or \
            state[1].strip() not in ("Routed", "Physopt postRoute"):
        raise ValueError("Vivado 2024.1 routed timing report required")
    sections = re.split(r"^\| Design Timing Summary\s*$", text, flags=re.M)
    if len(sections) != 2:
        raise ValueError("one complete design timing summary required")
    sections = re.split(r"^\| Clock Summary\s*$", sections[1], flags=re.M)
    if len(sections) != 2:
        raise ValueError("complete summary and following clock section required")
    section = sections[0]
    rows = re.findall(r"^\s*WNS\(ns\)[^\n]*\n[ -]+\n([^\n]+)", section, re.M)
    if len(rows) != 1 or len(rows[0].split()) != 12:
        raise ValueError("one complete twelve-column timing row required")
    values = list(map(float, rows[0].split()))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("finite timing values required")
    for index in (2, 3, 6, 7, 10, 11):
        if values[index] < 0 or not values[index].is_integer():
            raise ValueError("nonnegative integral endpoint counts required")
        values[index] = int(values[index])
    if any(values[index] <= 0 for index in (3, 7, 11)):
        raise ValueError("nonempty setup, hold and pulse-width coverage required")
    passed = (all(values[index] >= 0 for index in (0, 4, 8)) and
              all(values[index] == 0 for index in (1, 2, 5, 6, 9, 10)) and
              section.count("All user specified timing constraints are met.") == 1 and
              "Timing constraints are not met." not in section)
    return dict(status="ROUTED_TIMING_PASS_NOT_CLOCK_BUS_SKEW_OR_BOARD_TESTED" if passed
                else "ROUTED_TIMING_FAILED", values=dict(zip(FIELDS, values)),
                design_state=state[1].strip(), tool_version=version[1])


def check(path):
    data = Path(path).read_bytes()
    return dict(parse_report(data.decode()), report=dict(path=str(Path(path).resolve()),
                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = check(args.report)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"].startswith("ROUTED_TIMING_PASS") else 1)
