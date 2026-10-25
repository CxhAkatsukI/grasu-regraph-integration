"""Audit a successful Spine route rejected only by the dependency postprocessor.

The failed attempt stays immutable. A fresh report admits its exact binary to
board correctness testing, not to a timing-closure or performance claim.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from validation.grasu_complete import preparation
from .board import clocks


def timing_summary(text):
    section = text.split("| Design Timing Summary", 1)[1]
    for line in section.splitlines():
        values = line.split()
        if len(values) == 12 and all(re.fullmatch(r"-?\d+(?:\.\d+)?", value) for value in values):
            return dict(zip(("wns_ns", "tns_ns", "setup_failing_endpoints", "setup_endpoints",
                             "whs_ns", "ths_ns", "hold_failing_endpoints", "hold_endpoints",
                             "wpws_ns", "tpws_ns", "pulse_failing_endpoints", "pulse_endpoints"),
                            map(float, values)))
    raise ValueError("missing routed timing summary")


def validate(source):
    report_path, manifest_path = source / "results.json", source / "manifest.json"
    evidence = [preparation.pin(path) for path in (report_path, manifest_path)]
    report, manifest = (json.loads(path.read_text()) for path in (report_path, manifest_path))
    if report.get("status") != "FAILED_RETAINED" or report.get("board_tested") is not False or \
            report.get("error") != "FileNotFoundError(2, 'No such file or directory')":
        raise ValueError("only the retained dependency-postprocessing failure is recoverable")
    steps = report.get("steps", [])
    if len(steps) != 1:
        raise ValueError("exactly one completed compiler step required")
    step = steps[0]
    command = step.get("command", [])
    if step.get("phase") != "compile-route" or step.get("variant") != "spine-respr" or \
            step.get("exit_code") != 0 or step.get("stop_reason") != "process_exit" or \
            step.get("cleanup_snapshot_error") is not None:
        raise ValueError("compiler failure or watchdog stop cannot be recovered")
    if len(command) != 5 or command != manifest.get("command") or command[0] != "bash" or \
            Path(command[1]).name != "build_partitioned_algorithms.sh" or command[2:] != \
            ["hw", str(source / "build"), "respr"] or (source / "respr.d").exists():
        raise ValueError("unexpected compiler command or dependency-file failure")
    if manifest.get("selector") != "SPINE_RESIDUAL_SPARSE_APPLY=1":
        raise ValueError("sparse residual apply selector required")
    events = dict(line.split() for line in report["memory_events_after"].splitlines())
    if any(int(events[key]) for key in ("oom", "oom_kill", "oom_group_kill")):
        raise ValueError("OOM events cannot be recovered")
    evidence += report["pins"] + manifest["pins"]
    preparation.unchanged(evidence)
    build = source / "build/respr"
    provenance = build / "build_provenance.json"
    built = json.loads(provenance.read_text())
    probes = [row for row in evidence if Path(row["path"]).name == "host_memory.py"]
    if built.get("target") != "hw" or built.get("algorithm") != "thresholded_residual_pagerank" or \
            built.get("residual_sparse_apply") != 1 or built.get("git_dirty") is not False or \
            built.get("git_commit") != manifest.get("source_commit") or not probes or \
            any(row["sha256"] != built.get("host_memory_probe_sha256") for row in probes):
        raise ValueError("wrong or changed build provenance")
    stdout = source / "raw/spine-respr-compile-route.stdout.txt"
    marker = "BUILD_PASS target=hw algorithm=thresholded_residual_pagerank root=" + str(build)
    if stdout.read_text().splitlines()[-1] != marker:
        raise ValueError("missing terminal compiler success marker")
    timing = build / "reports/link/imp/impl_1_hw_bb_locked_timing_summary_routed.rpt"
    vivado = build / "logs/link/vivado.log"
    bus_skew = build / "reports/link/imp/impl_1_bus_skew_routed.rpt"
    binary = build / "xclbin/spine_partitioned_split_e2e.respr.hw.xclbin"
    evidence += [preparation.pin(path) for path in
                 (provenance, stdout, timing, vivado, bus_skew, binary, Path(__file__))]
    return {"pins": evidence, "xclbin": preparation.pin(binary),
            "provenance": preparation.pin(provenance), "timing": timing_summary(timing.read_text()),
            "frequency_scaling_messages": [line for line in vivado.read_text().splitlines()
                                           if "[AUTO-FREQ-SCALING-" in line]}


def run(source, output):
    audit = validate(source)
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "VERIFYING_RETAINED_ARTIFACT", "board_tested": False,
              "recovery_kind": "POSTPROCESS_DEPENDENCY_SCAN_ONLY", "source": str(source), **audit}
    try:
        binary = Path(audit["xclbin"]["path"])
        report["clocks"] = clocks(binary, output / "clocks.json")
        metadata = output / "embedded-metadata.xml"
        subprocess.run(["/opt/xilinx/xrt/bin/xclbinutil", "--input", str(binary),
                        "--dump-section", "EMBEDDED_METADATA:RAW:" + str(metadata)],
                       check=True, capture_output=True, timeout=120)
        kernels = [node.attrib["name"] for node in ET.parse(metadata).iter("kernel")]
        expected = {"spine_vertex_lifecycle_kernel", "spine_partconv_compute_kernel",
                    "spine_partconv_rdmaint_kernel"}
        if len(kernels) != 3 or set(kernels) != expected:
            raise ValueError("unexpected Spine kernel layout")
        report["kernels"] = kernels
        report["pins"] += [preparation.pin(output / name) for name in
                           ("clocks.json", "embedded-metadata.xml")]
        preparation.unchanged(report["pins"])
        report.update(status="ROUTED_NOT_BOARD_TESTED",
            acceptance="exact retained binary; correctness and board performance remain untested",
            timing_scope="routed report at requested clocks; actual clocks and compiler scaling retained")
    except BaseException as error:
        report.update(status="FAILED_RETAINED", error=repr(error))
        raise
    finally:
        atomic_write_json(output / "results.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(run(args.source.resolve(), args.output.resolve())["status"], flush=True)


if __name__ == "__main__":
    main()
