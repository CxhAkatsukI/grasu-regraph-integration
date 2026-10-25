"""Replace only the cache XO, then admit a finite full-hardware link job."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware import concurrent
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware.containment import current
from validation.grasu_complete import preparation, runtime
from .abi import review

GIB = 1024**3


def verify(group, memory_gib=96):
    fields = {key: (group / key).read_text().strip() for key in
              ("memory.max", "memory.high", "memory.swap.max", "memory.oom.group")}
    if (fields["memory.max"] == "max" or fields["memory.high"] == "max" or
            not 0 < int(fields["memory.max"]) <= min(memory_gib, 96) * GIB or
            not 0 < int(fields["memory.high"]) < int(fields["memory.max"]) or
            fields["memory.swap.max"] != "0" or fields["memory.oom.group"] != "1"):
        raise ValueError("finite memory/high, zero swap and whole-group OOM required")
    return {"path": str(group), "limits": fields}


def isolate_config(original, output):
    destinations = {"messageDb": output / "link.mdb", "temp_dir": output / "work",
                    "report_dir": output / "reports", "log_dir": output / "logs",
                    "remote_ip_cache": output / "ip_cache"}
    rows, found = [], set()
    for line in original.read_text().splitlines():
        key = line.partition("=")[0]
        if key in destinations:
            if key in found:
                raise ValueError("duplicate build output key")
            line = key + "=" + str(destinations[key])
            found.add(key)
        rows.append(line)
    if found != set(destinations):
        raise ValueError("all five link output paths must be isolated")
    path = output / "link.cfg"
    path.write_text("\n".join(rows) + "\n")
    return path


def prepare(args, output):
    source = json.loads(args.reference.read_text())
    argv = list(source["command"])
    if argv[argv.index("--target") + 1] != "hw" or "--link" not in argv or \
            argv[argv.index("--kernel_frequency") + 1] != "150":
        raise ValueError("expected existing 150-MHz full hardware link")
    old_config = Path(argv[argv.index("--config") + 1])
    expected = {row["path"]: row["sha256"] for row in source["pins"]}
    original_xos = [Path(value) for value in argv if value.endswith(".xo")]
    for path in (old_config, *original_xos):
        if preparation.pin(path)["sha256"] != expected.get(str(path)):
            raise ValueError("reused input is not covered by the prior manifest: " + str(path))
    gate = json.loads((args.export / "results.json").read_text())
    if gate["status"] != "CACHE_EXTENT_EXPORT_PASS_NOT_ROUTED":
        raise ValueError("fresh bounded cache export required")
    preparation.unchanged(gate["pins"])
    variant = "cache-plain" if args.algorithm == "respr" else "cache-token"
    candidate = args.export / (variant + "-bounded/candidate.xo")
    exported = gate["exports"][variant]
    if preparation.pin(candidate)["sha256"] != exported["xo_sha256"]:
        raise ValueError("exported cache identity changed")
    caches = [path for path in original_xos if path.name == "process_cache.hw.xo"]
    if len(caches) != 1:
        raise ValueError("one old cache XO required")
    abi = review(candidate, caches[0])
    stage = output / "xo"
    stage.mkdir()
    for path in original_xos:
        replacement = candidate if path == caches[0] else path
        staged = stage / path.name
        staged.symlink_to(replacement)
        argv[argv.index(str(path))] = str(staged)
    argv[argv.index("--config") + 1] = str(isolate_config(old_config, output))
    binary = output / Path(argv[argv.index("-o") + 1]).name
    argv[argv.index("-o") + 1] = str(binary)
    repository = Path(__file__).resolve().parents[2]
    audit = repository / "scripts/check_pipeline_master_budget.py"
    result = subprocess.run(["python3", str(audit), "--build-dir", str(stage),
        "--compute-pipelines", "4", "--pipeline-mode", "sharded-k4", "--algorithm", args.algorithm,
        "--out", str(output / "master-budget.json")], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise ValueError("actual-XO master audit failed: " + result.stdout + result.stderr)
    pins = gate["pins"] + [preparation.pin(path) for path in (args.reference, old_config, candidate,
            args.export / "results.json", *original_xos, *stage.iterdir(),
            output / "link.cfg", output / "master-budget.json", audit,
            audit.with_name("check_xo_master_budget.py"), Path(__file__),
            Path(__file__).with_name("abi.py"), args.settings)]
    manifest = {"pins": pins, "command": argv, "abi": abi,
                "change": "only cache transfer extent; full cache capacity, topology and clock unchanged",
                "board_tested": False, "original_xos": [str(path) for path in original_xos]}
    atomic_write_json(output / "manifest.json", manifest)
    pins.append(preparation.pin(output / "manifest.json"))
    return argv, binary, pins


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    group = current()
    concurrent.verify = verify
    guard = verify(group, memory_gib=args.memory_gib)
    if int(guard["limits"]["memory.max"]) != args.memory_gib * GIB or \
            int(guard["limits"]["memory.high"]) > (args.memory_gib - 4) * GIB:
        raise ValueError("declared hard cap and at least 4-GiB high-watermark margin required")
    report = {"algorithm": args.algorithm, "status": "PREPARING", "containment": guard,
              "policy": {"tree_memory_gib": args.memory_gib, "reserve_gib": 24, "allow_bounded_builds": True},
              "board_tested": False, "pins": [], "steps": []}
    save = lambda: atomic_write_json(args.output / "results.json", report)
    lease = concurrent.Lease(Path.home() / ".cache/spine-cycle-sim/compiler-reservations", group)
    try:
        save()
        argv, binary, report["pins"] = prepare(args, args.output)
        environment = runtime.environment(args.output)
        sourced = subprocess.check_output(["bash", "-c", 'source "$1" >/dev/null && env -0',
                                           "toolchain", str(args.settings)], env=environment, timeout=60)
        environment = dict(item.split("=", 1) for item in sourced.decode().split("\0") if item)
        compiler = Path(shutil.which(argv[0], path=environment["PATH"]))
        report["pins"].append(preparation.pin(compiler))
        runtime.admit(report, args.output, lease, args.wait_seconds)
        runtime.execute(report, args.output, args.output, args.algorithm, "link-place-route",
                        argv, 43200, environment)
        if not binary.is_file():
            raise ValueError("successful link did not produce an xclbin")
        report.update(status="ROUTED_NOT_BOARD_TESTED", xclbin=preparation.pin(binary))
    except BaseException as error:
        report.update(status="FAILED_RETAINED", error=repr(error))
        raise
    finally:
        lease.release()
        report["memory_events_after"] = (group / "memory.events").read_text()
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algorithm", choices=("sssp", "cc", "respr"), required=True)
    for name in ("reference", "export", "output", "settings"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=172800)
    parser.add_argument("--memory-gib", type=int, choices=(48, 56, 64), default=64)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    print(run(args)["status"], flush=True)


if __name__ == "__main__":
    main()
