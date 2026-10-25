"""Package terminal FPGA evidence, rechecking logs rather than trusting a CSV."""

import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil

from .matrix_inputs import ALGORITHMS, DATASETS

TERMINAL = {"RESIDENT_PAIR_PASS", "FAILED_RETAINED", "BLOCKED_BY_INVALID_ARTIFACT",
            "BLOCKED_BY_FAILED_BUILD", "BLOCKED_BY_FAILED_AU_GATE", "TIMED_OUT_WAITING_FOR_BUILD"}
BOUNDARY = "resident_update_to_final_readback_wall_including_host_relaunch"


def read(path):
    return json.loads(path.read_text())


def log_parser():
    path = Path(__file__).resolve().parents[2] / "scripts/compare_resident_fpga_logs.py"
    spec = importlib.util.spec_from_file_location("resident_delivery_logs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Pins:
    """Hash each large resident binary once during one immutable export."""

    def __init__(self):
        self.checked = {}

    def verify(self, rows):
        for row in rows:
            path = Path(row["path"])
            if path not in self.checked:
                with path.open("rb") as stream:
                    self.checked[path] = hashlib.file_digest(stream, "sha256").hexdigest()
            if self.checked[path] != row["sha256"]:
                raise ValueError("evidence pin changed: " + str(path))


def data_clocks(rows):
    values = [float(row["m_freq_Mhz"]) for row in rows if row["m_type"] == "DATA"]
    if not values or any(not 0 < value < float("inf") for value in values):
        raise ValueError("positive finite actual data clocks required")
    return ";".join(format(value, "g") for value in values)


def verify_case(row, plan, parser, pins):
    path = Path(row["results"])
    report, manifest = read(path), read(path.with_name("manifest.json"))
    config = report["config"]
    if report["status"] != "RESIDENT_PAIR_PASS" or report.get("board_tested") is not True:
        raise ValueError("passing matrix row lacks a passing board measurement")
    if report["boundary"] != BOUNDARY or manifest["boundary"] != BOUNDARY:
        raise ValueError("resident timing boundary changed")
    if config["kernel_variant"] != "complete-search-cache-bounded":
        raise ValueError("old full-cache control is not the revised FPGA matrix")
    workload = row["workload"]
    expected_records = 16 if row["algorithm"] == "cc" else 8
    if workload["batch_size"] != 8 or workload["updates"] != expected_records:
        raise ValueError("expected eight batch edits, with reciprocal records for CC")
    if config["logical"] != ALGORITHMS[row["algorithm"]] or config["dataset"] != row["dataset"] or \
            any(config[key] != workload[key] for key in ("graph", "source")):
        raise ValueError("case does not match its declared workload")
    frozen = [item for item in plan["workloads"] if item["algorithm"] == config["logical"]
              and item["dataset"] == row["dataset"]]
    if frozen != [workload] or manifest["config"] != config or manifest["clocks"] != report["clocks"]:
        raise ValueError("case manifest differs from the frozen plan or board report")
    pins.verify(manifest["pins"])
    pinned = {item["path"] for item in manifest["pins"]}
    required = [config[key] for key in ("gr_host", "spine_host", "gr_binary", "spine_binary", "graph")]
    if not set(required) <= pinned:
        raise ValueError("missing host, bitstream or workload identity")
    recomputed = []
    if len(report["samples"]) != 4:
        raise ValueError("one warmup and three measured pairs required")
    for index, sample in enumerate(report["samples"]):
        order = ["gr", "spine"] if index % 2 == 0 else ["spine", "gr"]
        if sample["sample_index"] != index or sample["warmup"] != (index == 0) or sample["order"] != order:
            raise ValueError("warmup, repetition or alternating order changed")
        if set(sample["resources"]) != {"gr", "spine"}:
            raise ValueError("both architectures need successful execution records")
        for resource in sample["resources"].values():
            if resource["exit_code"] != 0 or resource["stop_reason"] != "process_exit" or \
                    resource["cleanup_snapshot_error"] is not None:
                raise ValueError("unsuccessful raw execution cannot produce a speedup")
        directory = path.parent / ("sample-" + str(index))
        pair = parser.compare(config["logical"], (directory / "gr/run.log").read_text(),
                              (directory / "spine.stdout.txt").read_text(), config["source"])
        if pair != sample["pair"] or any(pair[key] != workload["updates"] for key in
                                        ("logical_updates", "physical_updates")):
            raise ValueError("raw log or input-record count differs from the frozen workload")
        recomputed.append({**sample, "pair": pair})
    summary = parser.summarize(recomputed)
    if summary != report["summary"] or summary != row["summary"]:
        raise ValueError("raw-log medians differ from the saved summary")
    clocks = {}
    for name in ("gr", "spine"):
        dumped = read(path.with_name(name + "-clocks.json"))["clock_freq_topology"]["m_clock_freq"]
        if dumped != report["clocks"][name]:
            raise ValueError("actual clock dump differs from the board report")
        clocks[name] = data_clocks(dumped)
    return {"gr_ms": summary["walls"]["gr"]["median_ms"],
            "spine_ms": summary["walls"]["spine"]["median_ms"],
            "speedup_gr_over_spine": summary["speedup_ratio_of_median_walls"],
            "gr_data_mhz": clocks["gr"], "spine_data_mhz": clocks["spine"],
            "batch_size": workload["batch_size"], "input_update_records": workload["updates"],
            "logical_updates": summary["logical_updates"], "physical_updates": summary["physical_updates"]}


def inspect(matrix_path):
    report = read(matrix_path)
    if report["status"] not in ("FPGA_MATRIX_PASS", "FPGA_MATRIX_INCOMPLETE_RETAINED"):
        raise ValueError("matrix is still running; do not export it as final evidence")
    expected = {(algorithm, dataset) for algorithm in ALGORITHMS for dataset in DATASETS}
    keys = [(row["algorithm"], row["dataset"]) for row in report["cases"]]
    if len(keys) != 24 or set(keys) != expected or any(row["status"] not in TERMINAL for row in report["cases"]):
        raise ValueError("exactly 24 unique terminal cases required, including failures")
    passed = sum(row["status"] == "RESIDENT_PAIR_PASS" for row in report["cases"])
    if report["passed_cases"] != passed or (report["status"] == "FPGA_MATRIX_PASS") != (passed == 24):
        raise ValueError("terminal matrix status or passing-case count is inconsistent")
    plan = read(Path(report["plan"]))
    if plan["boundary"] != BOUNDARY or plan["repeats"] != {"warmup_pairs": 1, "measured_pairs": 3}:
        raise ValueError("frozen measurement contract changed")
    pins, parser, rows = Pins(), log_parser(), []
    pins.verify(plan["pins"])
    for row in report["cases"]:
        measured = verify_case(row, plan, parser, pins) if row["status"] == "RESIDENT_PAIR_PASS" else {}
        rows.append({"algorithm": row["algorithm"], "dataset": row["dataset"],
                     "status": row["status"], **measured, "source_results": row.get("results", ""),
                     "error": row.get("error", "")})
    return report, rows


def package(matrix_path, output):
    report, rows = inspect(matrix_path)
    if output.exists():
        raise ValueError("use a fresh delivery directory; existing evidence is never overwritten")
    files = [(matrix_path, Path("matrix.json")), (Path(report["plan"]), Path("plan.json"))]
    for row in report["cases"]:
        key = row["algorithm"] + "-" + row["dataset"].lower()
        driver = matrix_path.parent / (key + ".driver.log")
        if driver.is_file():
            files.append((driver, Path("cases") / key / "driver.log"))
        if not row.get("results"):
            continue
        source = Path(row["results"]).parent
        destination = Path("cases") / key
        names = ["results.json", "manifest.json", "gr-clocks.json", "spine-clocks.json"]
        names += [f"sample-{index}/{name}" for index in range(4)
                  for name in ("gr/run.log", "gr.stdout.txt", "gr.stderr.txt",
                               "spine.stdout.txt", "spine.stderr.txt")]
        files += [(source / name, destination / name) for name in names if (source / name).is_file()]
    sizes = [source.stat().st_size for source, _ in files]
    if any(size > 16 * 1024**2 for size in sizes) or sum(sizes) > 256 * 1024**2:
        raise ValueError("delivery logs exceed 16-MiB/file or 256-MiB total; review before packaging")
    output.mkdir(parents=True)
    index = []
    for source, destination in files:
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        with target.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        index.append({"path": str(destination), "sha256": digest, "source": str(source)})
    columns = ("algorithm", "dataset", "status", "gr_ms", "spine_ms", "speedup_gr_over_spine",
               "gr_data_mhz", "spine_data_mhz", "batch_size", "input_update_records",
               "logical_updates", "physical_updates", "source_results", "error")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    (output / "summary.csv").write_text(buffer.getvalue())
    (output / "files.json").write_text(json.dumps(index, indent=2) + "\n")
    (output / "README.md").write_text(description(report, rows))
    return {"status": report["status"], "passed_cases": report["passed_cases"], "output": str(output)}


def description(report, rows):
    lines = ["# Revised G+R Versus Spine: Resident FPGA Results", "",
        f"Status: **{report['status']}**, {report['passed_cases']}/24 correctness-admitted pairs.", "",
        "These are FPGA wall-time measurements, not simulator predictions. Ratios above one favor Spine.",
        "One warmup pair is excluded; values are the medians of three alternating-order measured pairs.", "",
        "Both systems start with the same resident converged old graph and apply eight logical updates",
        "until new convergence. Timing includes updates, propagation, host launch/wait, inter-round",
        "relaunch and final readback. Initial graph/PMA creation, initial residency, old-state preload,",
        "batch preparation/upload and CPU oracles are excluded symmetrically. This is not application",
        "setup-inclusive latency. Actual DATA clocks are in the CSV; HBM/system clocks remain in each manifest.", "",
        "The frozen batch size is eight. CC encodes eight undirected insertions as sixteen reciprocal",
        "directed records; SSSP and ResPR each encode eight directed insertions. Both hosts' raw",
        "`logical_updates` and `physical_updates` fields count input records in this matrix. Those",
        "fields are preserved verbatim, not divided by two. `batch_size` and `input_update_records`",
        "in the CSV distinguish the declared batch size from its encoded record count.", "",
        "The G+R hosts use GCC 15.2 -O2; Spine uses GCC 15.2 -O3. The earlier approximately 2.47x",
        "ReGraph publication-scale gap remains a limitation, not a successful reproduction claim.",
        "Source changes, HLS export, routed artifacts and FPGA measurement are separate gates.",
        "The bounded-cache simulator component passed regression, but this package does not claim",
        "new full-system simulator timing calibration or promotion of the production SST plugin.", "",
        "## Results", "", "| Algorithm | Dataset | Status | G+R ms | Spine ms | G+R / Spine |",
        "| --- | --- | --- | ---: | ---: | ---: |"]
    for row in rows:
        numbers = [format(row[key], ".6g") if key in row else "" for key in
                   ("gr_ms", "spine_ms", "speedup_gr_over_spine")]
        lines.append("| " + " | ".join([row["algorithm"], row["dataset"], row["status"], *numbers]) + " |")
    lines += ["", "## Evidence", "", "`summary.csv` retains every declared case, including failures.",
        "`cases/` contains copied board reports, manifests and raw paired logs; `files.json` records hashes",
        "and original locations. The frozen plan and case manifests identify hosts, bitstreams, workloads",
        "and source pins. Large binaries, graphs and compiler trees stay at those indexed locations.",
        "Passing rows were rechecked against raw logs, binary/source hashes and recomputed medians.",
        "Incomplete rows are not speedups and may require another build or run. No paper was modified.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.matrix.resolve(), args.output.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
