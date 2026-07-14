#!/usr/bin/env python3

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


METRICS = (
    "resident_batch_end_to_end_ms",
    "cold_workload_end_to_end_ms",
    "workload_end_to_end_ms",
    "update_device_ms",
    "compute_device_ms",
    "combined_device_ms",
    "device_kernel_sum_ms",
    "transfer_ms",
    "bridge_host_ms",
    "host_wall_ms",
    "host_pipeline_wall_ms",
    "regraph_e2e_ms",
)
REQUIRED_SYSTEMS = ("grasu_accugraph", "spine", "grasu_regraph")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def metric_stats(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "minimum": min(values),
        "p10": percentile(values, 0.10),
        "median": statistics.median(values),
        "p90": percentile(values, 0.90),
        "maximum": max(values),
    }


def system_name(record: dict[str, object]) -> str:
    explicit = record.get("system")
    if explicit:
        return str(explicit)
    raise ValueError(
        "record has no explicit system identity; fail closed rather than "
        "inferring AccuGraph provenance")


def claim_eligible(record: dict[str, object]) -> bool:
    if "performance_claim_eligible" in record:
        return bool(record["performance_claim_eligible"])
    return bool(record.get("performance_valid", False))


def source_clean(record: dict[str, object]) -> bool:
    states = record.get("source_states")
    if isinstance(states, dict):
        for state in states.values():
            if not isinstance(state, dict) or state.get("commit") is None:
                return False
            if state.get("tracked_dirty") is not False:
                return False
        return True
    return record.get("integration_dirty") is False


def artifact_identity_ok(records: list[dict[str, object]]) -> bool:
    hash_keys = sorted({
        key for record in records for key, value in record.items()
        if key.endswith("_sha256") and value is not None and
        any(token in key for token in ("host", "xclbin"))
    })
    if not hash_keys:
        return False
    return all(len({record.get(key) for record in records}) == 1
               for key in hash_keys)


def summarize_group(records: list[dict[str, object]], expected: dict[str, object],
                    minimum_repeats: int) -> dict[str, object]:
    measured = [record for record in records if not bool(record.get("warmup", False))]
    correct = [record for record in measured if bool(record.get("correct", False))]
    identity_ok = all(
        record.get("graph_sha256") == expected["graph_sha256"] and
        int(record.get("source", -1)) == int(expected["bfs_source"])
        for record in measured)
    stats = {}
    for metric in METRICS:
        values = [float(record[metric]) for record in correct
                  if record.get(metric) is not None]
        if values:
            stats[metric] = metric_stats(values)

    blockers = []
    if len(measured) < minimum_repeats:
        blockers.append(f"measured_runs={len(measured)}<{minimum_repeats}")
    if len(correct) != len(measured):
        blockers.append(f"correct_runs={len(correct)}/{len(measured)}")
    if not identity_ok:
        blockers.append("input_identity_mismatch")
    if not measured or not all(claim_eligible(record) for record in measured):
        blockers.append("performance_claim_not_eligible")
    if not measured or not all(source_clean(record) for record in measured):
        blockers.append("source_provenance_missing_or_dirty")
    if not artifact_identity_ok(measured):
        blockers.append("artifact_pair_not_unique")
    if "resident_batch_end_to_end_ms" not in stats or (
            stats["resident_batch_end_to_end_ms"]["count"] != len(measured)):
        blockers.append("comparable_resident_batch_end_to_end_missing")
    return {
        "runs_total": len(records),
        "warmups": len(records) - len(measured),
        "measured_runs": len(measured),
        "correct_runs": len(correct),
        "identity_ok": identity_ok,
        "statistics": stats,
        "claim_eligible": not blockers,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--minimum-repeats", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.minimum_repeats < 1:
        parser.error("--minimum-repeats must be positive")

    selection_path = args.selection.resolve()
    selection = json.loads(selection_path.read_text(encoding="ascii"))
    expected = {case["case_id"]: case for case in selection["cases"]}
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    input_hashes = {}
    for path in args.input:
        resolved = path.resolve()
        input_hashes[str(resolved)] = sha256(resolved)
        with resolved.open("r", encoding="ascii") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                case_id = str(record["case_id"])
                if case_id not in expected:
                    raise ValueError(f"unknown case {case_id}: {resolved}:{line_number}")
                grouped[(case_id, system_name(record))].append(record)

    groups = {}
    rankings = {}
    case_ids = sorted({case_id for case_id, _ in grouped})
    for case_id in case_ids:
        groups[case_id] = {}
        for system in REQUIRED_SYSTEMS:
            records = grouped.get((case_id, system), [])
            groups[case_id][system] = summarize_group(
                records, expected[case_id], args.minimum_repeats)
        eligible = all(groups[case_id][system]["claim_eligible"]
                       for system in REQUIRED_SYSTEMS)
        if eligible:
            medians = {
                system: groups[case_id][system]["statistics"]
                ["resident_batch_end_to_end_ms"]["median"]
                for system in REQUIRED_SYSTEMS
            }
            winner = min(medians, key=medians.get)
            rankings[case_id] = {
                "eligible": True,
                "winner": winner,
                "median_resident_batch_end_to_end_ms": medians,
            }
        else:
            rankings[case_id] = {
                "eligible": False,
                "winner": None,
                "reason": "one or more system groups fail the no-trick gates",
            }

    summary = {
        "schema_version": 2,
        "selection_sha256": sha256(selection_path),
        "minimum_repeats": args.minimum_repeats,
        "input_sha256": input_hashes,
        "groups": groups,
        "rankings": rankings,
        "all_rankings_eligible": bool(rankings) and all(
            ranking["eligible"] for ranking in rankings.values()),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                         encoding="ascii")

    markdown = [
        "# Canonical Cross-System Summary",
        "",
        "| Case | System | Measured | Correct | Median resident-batch E2E (ms) | Eligible | Blockers |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for case_id in case_ids:
        for system in REQUIRED_SYSTEMS:
            group = groups[case_id][system]
            workload = group["statistics"].get("resident_batch_end_to_end_ms")
            median = "" if workload is None else f"{workload['median']:.6f}"
            markdown.append(
                f"| {case_id} | {system} | {group['measured_runs']} | "
                f"{group['correct_runs']} | {median} | "
                f"{'yes' if group['claim_eligible'] else 'no'} | "
                f"{', '.join(group['blockers'])} |")
    markdown.extend((
        "",
        "Winner fields remain empty until all three systems pass every gate.",
    ))
    markdown_path = args.output_dir / "summary.md"
    markdown_path.write_text("\n".join(markdown) + "\n", encoding="ascii")
    print(json_path)
    print(markdown_path)
    print(f"all_rankings_eligible={summary['all_rankings_eligible']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
