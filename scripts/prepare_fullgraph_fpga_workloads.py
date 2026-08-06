#!/usr/bin/env python3
"""Materialize the eight-graph FPGA matrix in the PMA host format."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from convert_spine_slices_to_pma_graph import convert, sha256  # noqa: E402


DEFAULT_DATASETS = {
    "AU": "sx_askubuntu",
    "SU": "sx_superuser",
    "WK": "wiki_talk_temporal",
    "SO": "sx_stackoverflow",
    "PK": "soc_pokec",
    "LJ": "soc_livejournal1",
    "LJ08": "ljournal_2008",
    "R19": "rmat_19_32",
}

ALGORITHM_LAYOUTS = {
    "weighted_sssp": ("directed", "directed"),
    "connected_components": ("reciprocal", "reciprocal"),
    "residual_pagerank": ("residual_sink_free", "residual_sink_free"),
}


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def select_update(
    manifest: dict[str, object], projection: str, batch_size: int
) -> dict[str, object]:
    matches = [
        update
        for update in manifest["updates"]
        if update["scenario"] == "insert"
        and update["projection"] == projection
        and update["user_mutations"] == batch_size
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one insert/u{batch_size}/{projection} update, got "
            f"{len(matches)}"
        )
    return matches[0]


def reusable(metadata_path: Path, initial: Path, update: Path, output: Path) -> bool:
    if not metadata_path.is_file() or not output.is_file():
        return False
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return (
        metadata.get("initial_slice_sha256") == sha256(initial)
        and metadata.get("update_slice_sha256") == sha256(update)
        and metadata.get("pma_graph_sha256") == sha256(output)
        and metadata.get("streaming_conversion") is True
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--materialization-root",
        type=Path,
        default=Path("/data/tmp/chuxiao/large_graph_campaign_v1/workloads"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/data/tmp/chuxiao/fullgraph_fpga_workloads_20260806"),
    )
    parser.add_argument(
        "--datasets", default=",".join(DEFAULT_DATASETS), help="comma-separated"
    )
    parser.add_argument(
        "--algorithms",
        default=",".join(ALGORITHM_LAYOUTS),
        help="comma-separated",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    datasets = parse_csv(args.datasets)
    algorithms = parse_csv(args.algorithms)
    unknown_datasets = sorted(set(datasets) - set(DEFAULT_DATASETS))
    unknown_algorithms = sorted(set(algorithms) - set(ALGORITHM_LAYOUTS))
    if unknown_datasets or unknown_algorithms:
        raise ValueError(
            f"unknown datasets={unknown_datasets} algorithms={unknown_algorithms}"
        )
    if args.batch_size <= 0:
        raise ValueError("batch size must be positive")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for abbreviation in datasets:
        dataset_id = DEFAULT_DATASETS[abbreviation]
        source_manifest_path = (
            args.materialization_root / dataset_id / "materialization_manifest.json"
        )
        source_manifest = json.loads(
            source_manifest_path.read_text(encoding="utf-8")
        )
        if source_manifest.get("status") != "pass":
            raise ValueError(f"materialization is not admitted: {dataset_id}")

        for algorithm in algorithms:
            graph_key, update_projection = ALGORITHM_LAYOUTS[algorithm]
            graph_entry = source_manifest["graphs"][graph_key]
            update_entry = select_update(
                source_manifest, update_projection, args.batch_size
            )
            initial = Path(graph_entry["path"])
            update = Path(update_entry["path"])
            stem = f"{abbreviation.lower()}_{algorithm}_insert_u{args.batch_size}"
            output = args.out_dir / f"{stem}.graph"
            metadata_path = args.out_dir / f"{stem}.json"
            was_reused = (
                not args.force and reusable(metadata_path, initial, update, output)
            )
            if was_reused:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            else:
                metadata = convert(initial, update, output, metadata_path)
            record = {
                "dataset": abbreviation,
                "dataset_id": dataset_id,
                "algorithm": algorithm,
                "batch_size": args.batch_size,
                "graph": str(output.resolve()),
                "metadata": str(metadata_path.resolve()),
                "vertices": metadata["vertices"],
                "initial_edges": metadata["initial_edges"],
                "updates": metadata["updates"],
                "source": (
                    graph_entry.get("source_cohorts", {}).get("median_degree", 0)
                    if algorithm == "weighted_sssp"
                    else 0
                ),
                "sha256": metadata["pma_graph_sha256"],
                "reused": was_reused,
            }
            records.append(record)
            print(
                "FULLGRAPH_FPGA_WORKLOAD "
                f"dataset={abbreviation} algorithm={algorithm} "
                f"vertices={record['vertices']} edges={record['initial_edges']} "
                f"updates={record['updates']} reused={int(was_reused)}"
            )

    aggregate = {
        "schema_version": 1,
        "status": "pass",
        "batch_size": args.batch_size,
        "records": records,
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (args.out_dir / "manifest.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "dataset\talgorithm\tvertices\tinitial_edges\tupdates\tsource\tgraph\tsha256\n"
        )
        for record in records:
            handle.write(
                "\t".join(
                    str(record[key])
                    for key in (
                        "dataset",
                        "algorithm",
                        "vertices",
                        "initial_edges",
                        "updates",
                        "source",
                        "graph",
                        "sha256",
                    )
                )
                + "\n"
            )
    print(
        f"FULLGRAPH_FPGA_WORKLOADS_PASS records={len(records)} out={args.out_dir}"
    )


if __name__ == "__main__":
    main()
