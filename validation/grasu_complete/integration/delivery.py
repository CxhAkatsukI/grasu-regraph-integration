"""Seal connected-host evidence, keeping failed attempts and hardware gates separate."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json, sha256_file
from spine_cycle_sim.experiments.original_regraph_execution.sssp_real_round.delivery import seal
from .. import preparation as common
from . import analysis

PASS = "CONNECTED_G_HOST_FUNCTIONAL_PASS_NOT_RTL_OR_DEVICE_REFRESH"
CLAIMS = ("rtl_validated", "device_metadata_refresh_validated", "routed", "board_validated",
          "performance_matched", "publication_matched")


def terminal(report):
    if (report["status"] not in (PASS, "FAILED_RETAINED") or
            bool(report["errors"]) != (report["status"] == "FAILED_RETAINED") or
            any(report.get(key) is not False for key in CLAIMS)):
        raise ValueError("terminal connected-host result without hardware claims required")


def replay(report, read):
    terminal(report)
    if report["status"] != PASS:
        return
    phases = ("compile-0", "link", "execute", "negative-stale-metadata")
    if [step["phase"] for step in report["steps"]] != list(phases):
        raise ValueError("complete connected-host execution matrix required")
    for step in report["steps"]:
        name = "stale-metadata" if step["phase"] == phases[-1] else step["phase"]
        raw = json.loads(read("raw/connected-" + name + ".resources.json"))
        if raw != {key: value for key, value in step.items() if key not in ("variant", "phase")}:
            raise ValueError("connected-host resource record changed")
        if (step["exit_code"] != (1 if name == "stale-metadata" else 0) or
                step["stop_reason"] != "process_exit" or step["cleanup_snapshot_error"]):
            raise ValueError("connected-host child did not finish as declared")
    if (analysis.functional(read("raw/connected-execute.stdout.txt")) != report["functional"] or
            analysis.diagnostics(read("raw/connected-execute.stderr.txt")) != report["diagnostics"] or
            analysis.stale_rejection(report["steps"][-1], read("raw/connected-stale-metadata.stdout.txt"),
                                     read("raw/connected-stale-metadata.stderr.txt")) !=
            report["stale_metadata_control"]):
        raise ValueError("connected-host raw outputs and analysis disagree")
    events = dict(line.split() for line in report["memory_events_after"].splitlines())
    if not events or any(int(value) for value in events.values()) or not report["admission"]["admitted"]:
        raise ValueError("safe admitted execution without memory events required")


def recheck(attempt):
    report = json.loads((attempt / "results.json").read_text())
    replay(report, lambda name: (attempt / name).read_text())
    # Earlier failures may refer to subsequently fixed editable analyzers. Only
    # their frozen copies are immutable; passing inputs must all still match.
    pins = report["pins"] if report["status"] == PASS else [pin for pin in report["pins"]
                                                          if Path(pin["path"]).is_relative_to(attempt)]
    if not pins:
        raise ValueError("frozen connected-host inputs required")
    common.unchanged(pins)
    owner = attempt / "source/grasu_complete"
    common.reviewed(owner, json.loads((owner / "provenance.json").read_text()))
    return report


def package(output, attempts):
    if not attempts or len({path.name for path in attempts}) != len(attempts):
        raise ValueError("distinct named connected-host attempts required")
    reports = [recheck(path) for path in attempts]
    if sum(report["status"] == PASS for report in reports) != 1:
        raise ValueError("one passing connected-host attempt required")
    files, entries = [], []
    for attempt, report in zip(attempts, reports):
        for path in sorted(attempt.rglob("*")):
            if path.is_symlink():
                raise ValueError("symlink in connected-host evidence")
            relative = path.relative_to(attempt)
            if (path.is_file() and (relative.parts[0] in ("raw", "runner") or
                    relative.parts[0] == "source" and relative.parts[1] != "vendor" or
                    relative.as_posix() in ("results.json", "connected/unit.d"))):
                files.append((path, attempt.name + "/" + relative.as_posix()))
        entries.append({"attempt": attempt.name, "source": str(attempt), "status": report["status"],
                        "errors": report["errors"], "rows": len(report.get("functional", [])),
                        "external_pins": [pin for pin in report["pins"] if
                                          not Path(pin["path"]).is_relative_to(attempt)]})
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "connected_host.tar.gz"
    index = {"status": PASS, "attempts": entries, "archive": archive.name,
             "files": seal(files, archive), "sha256": sha256_file(archive),
             "bytes": archive.stat().st_size, **dict.fromkeys(CLAIMS, False),
             "indexed_not_archived": ["installed vendor headers", "compiled executable/object",
                                      "external compiler and runtime dependencies"]}
    atomic_write_json(output / "index.json", index)
    return verify(output)


def verify(output):
    index = json.loads((output / "index.json").read_text())
    if index["status"] != PASS or any(index.get(key) is not False for key in CLAIMS):
        raise ValueError("invalid connected-host capsule boundary")
    archive = output / index["archive"]
    if archive.parent != output or sha256_file(archive) != index["sha256"]:
        raise ValueError("connected-host archive changed")
    with tarfile.open(archive) as bundle:
        if bundle.getnames() != [row["path"] for row in index["files"]]:
            raise ValueError("connected-host archive membership changed")
        for row in index["files"]:
            name, info = PurePosixPath(row["path"]), bundle.getmember(row["path"])
            if (name.is_absolute() or ".." in name.parts or not info.isfile() or info.size != row["bytes"] or
                    hashlib.sha256(bundle.extractfile(info).read()).hexdigest() != row["sha256"]):
                raise ValueError("connected-host archive member changed")
        passed = 0
        for entry in index["attempts"]:
            name = entry["attempt"]
            if PurePosixPath(name).name != name:
                raise ValueError("unsafe connected-host attempt name")
            read = lambda member: bundle.extractfile(name + "/" + member).read().decode()
            report = json.loads(read("results.json"))
            replay(report, read)
            if (report["status"] != entry["status"] or report["errors"] != entry["errors"] or
                    len(report.get("functional", [])) != entry["rows"]):
                raise ValueError("connected-host index disagrees with archived result")
            passed += report["status"] == PASS
        if passed != 1:
            raise ValueError("one complete passing attempt required")
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    args = parser.parse_args()
    print(package(args.output.resolve(), [path.resolve() for path in args.attempt])["status"], flush=True)
