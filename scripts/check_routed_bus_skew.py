"""Fail-closed validation of an unfiltered Vivado 2024.1 routed bus-skew report."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shlex


def parse_report(text):
    version = re.search(r"^\| Tool Version\s*: Vivado v\.([^ ]+)", text, re.M)
    state = re.search(r"^\| Design State\s*: (.+)$", text, re.M)
    command = re.search(r"^\| Command\s*: (.+)$", text, re.M)
    if not version or version[1] != "2024.1" or not state or \
            state[1].strip() not in ("Routed", "Physopt postRoute") or not command:
        raise ValueError("Vivado 2024.1 routed report header required")
    argv = shlex.split(command[1])
    if len(argv) not in (3, 4) or argv[:2] != ["report_bus_skew", "-file"] or \
            (len(argv) == 4 and argv[3] != "-warn_on_violation") or argv[2].startswith("-"):
        raise ValueError("unfiltered default min/max report command required")

    # Cell selectors wrap over several lines. Numeric rows end with corner/skew/slack.
    sections = re.split(r"^1\. Bus Skew Report Summary\n-+\n", text, flags=re.M)
    if len(sections) != 2:
        raise ValueError("one complete bus-skew summary required")
    ends = re.split(r"^2\. Bus Skew Report Per Constraint\n-+\n", sections[1], flags=re.M)
    if len(ends) != 2 or not re.search(
            r"^Id\s+Position\s+From\s+To\s+Corner\s+Requirement\(ns\)\s+Actual\(ns\)\s+Slack\(ns\)$",
            ends[0], re.M):
        raise ValueError("complete 2024.1 summary columns and following section required")
    starts = list(re.finditer(r"^(\d+)\s+(\d+)\s+", ends[0], re.M))
    if not starts:
        raise ValueError("no bus-skew constraints; coverage must be checked separately")
    rows, unmeasured = [], []
    for index, start in enumerate(starts):
        block = ends[0][start.start():starts[index + 1].start() if index + 1 < len(starts) else None]
        values = re.findall(r"\b(Slow|Fast|NA)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", block, re.M)
        if int(start[1]) != index + 1 or len(values) != 1:
            raise ValueError("missing, duplicated or incomplete bus-skew summary row")
        corner, *numbers = values[0]
        if corner == "NA":
            requirement = float(numbers[0])
            if numbers[1:] != ["NA", "NA"] or not math.isfinite(requirement) or requirement <= 0:
                raise ValueError("malformed unmeasured constraint: " + start[1])
            unmeasured.append(dict(id=index + 1, position=int(start[2]),
                                   requirement_ns=requirement, summary=block.strip()))
            continue
        requirement, actual, slack = map(float, numbers)
        if not all(math.isfinite(value) for value in (requirement, actual, slack)) or \
                requirement <= 0 or slack < 0 or abs(requirement - actual - slack) > 0.0031:
            raise ValueError("bus-skew violation or malformed numeric row: " + start[1])
        rows.append(dict(id=index + 1, position=int(start[2]), corner=corner,
                         requirement_ns=requirement, actual_ns=actual, slack_ns=slack))
    if not rows:
        raise ValueError("no numerically checked bus-skew constraints")
    return dict(status="ROUTED_BUS_SKEW_REVIEW_REQUIRED" if unmeasured else
                "ROUTED_BUS_SKEW_PASS_NOT_BOARD_TESTED", tool_version=version[1],
                design_state=state[1].strip(), constraints=len(starts),
                measured_constraints=len(rows), unmeasured=unmeasured,
                min_slack_ns=min(row["slack_ns"] for row in rows), rows=rows)


def check(path):
    data = Path(path).read_bytes()
    return dict(parse_report(data.decode()), report=dict(
        path=str(Path(path).resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.report)
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    if result["unmeasured"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
