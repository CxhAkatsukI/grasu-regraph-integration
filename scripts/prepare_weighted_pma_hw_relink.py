#!/usr/bin/env python3
"""Prepare an isolated timing-closure relink from verified weighted-PMA XOs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import stat
from pathlib import Path


PROFILES = {
    "route-aggressive": {
        "place": "AltSpreadLogic_high",
        "phys_opt": "AggressiveExplore",
        "route": "AggressiveExplore",
        "post_route_phys_opt": "AggressiveExplore",
    },
    "place-extranet": {
        "place": "ExtraNetDelay_high",
        "phys_opt": "AggressiveExplore",
        "route": "AlternateCLBRouting",
        "post_route_phys_opt": "AggressiveExplore",
    },
}

XO_PATTERNS = (
    "bin_search.hw.xo",
    "dispatch.hw.xo",
    "kernelApply.hw.*.xo",
    "kernelHBMWrapper.hw.*.xo",
    "kernelLittleGSMerger.hw.*.xo",
    "process_cache.hw.xo",
    "process_ddr.hw.xo",
    "pma_completion_barrier.hw.xo",
    "pma_to_regraph_adapter.hw.xo",
    "lksg_stream.hw.xo",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def require_source_contract(source_root: Path, manifest: dict[str, str]) -> Path:
    if manifest.get("TARGET") != "hw":
        raise ValueError("source manifest TARGET must be hw")
    if manifest.get("PIPELINE_MODE") != "weighted-axis":
        raise ValueError("source manifest PIPELINE_MODE must be weighted-axis")
    link_cfg = Path(manifest.get("LINK_CFG", ""))
    if not link_cfg.is_file():
        raise FileNotFoundError(f"source link config is missing: {link_cfg}")
    if source_root not in link_cfg.parents:
        raise ValueError("source LINK_CFG must be contained by source build root")
    return link_cfg


def find_xos(source_root: Path) -> list[Path]:
    build_dir = source_root / "build"
    result: list[Path] = []
    for pattern in XO_PATTERNS:
        matches = sorted(build_dir.glob(pattern))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"expected exactly one input matching {pattern}, found {len(matches)}"
            )
        result.append(matches[0].resolve())
    return result


def rewrite_link_config(
    source: Path,
    destination: Path,
    packet_root: Path,
    profile: str,
) -> None:
    replacements = {
        "messageDb": packet_root / "build" / "grasu_regraph_weighted_pma_native.mdb",
        "temp_dir": packet_root / "build" / "link",
        "report_dir": packet_root / "reports" / "link",
        "log_dir": packet_root / "logs" / "link",
        "remote_ip_cache": packet_root / "ip_cache",
    }
    output: list[str] = []
    skip_vivado = False
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and line.endswith("]"):
            skip_vivado = line == "[vivado]"
            if skip_vivado:
                continue
        if skip_vivado:
            continue
        key = line.split("=", 1)[0] if "=" in line else ""
        if key in replacements:
            output.append(f"{key}={replacements[key]}")
        else:
            output.append(line)

    directives = PROFILES[profile]
    output.extend(
        [
            "",
            "[vivado]",
            f"prop=run.impl_1.STEPS.PLACE_DESIGN.ARGS.DIRECTIVE={directives['place']}",
            f"prop=run.impl_1.STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE={directives['phys_opt']}",
            f"prop=run.impl_1.STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE={directives['route']}",
            "prop=run.impl_1.STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE="
            f"{directives['post_route_phys_opt']}",
            "",
        ]
    )
    destination.write_text("\n".join(output), encoding="utf-8")


def write_executable(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def prepare(args: argparse.Namespace) -> Path:
    source_root = args.source_build_root.resolve()
    packet_root = args.out_root.resolve()
    if packet_root == source_root:
        raise ValueError("output root must differ from source build root")
    source_manifest_path = source_root / "manifest.env"
    if not source_manifest_path.is_file():
        raise FileNotFoundError(f"source manifest is missing: {source_manifest_path}")
    source_manifest = read_manifest(source_manifest_path)
    source_cfg = require_source_contract(source_root, source_manifest)
    xos = find_xos(source_root)

    for child in ("build", "config", "logs", "reports", "tmp", "ip_cache"):
        (packet_root / child).mkdir(parents=True, exist_ok=True)

    link_cfg = packet_root / "config" / "weighted_pma_native_hw_relink.cfg"
    rewrite_link_config(source_cfg, link_cfg, packet_root, args.profile)
    output_xclbin = packet_root / "build" / "grasu_regraph_weighted_pma_native.hw.xclbin"
    link_command = packet_root / "link_command.sh"
    command = [
        "v++",
        "--target",
        "hw",
        "--link",
        "--kernel_frequency",
        str(args.kernel_frequency),
        "--config",
        str(link_cfg),
        "--vivado.synth.jobs",
        str(args.jobs),
        "--vivado.impl.jobs",
        str(args.jobs),
        "-o",
        str(output_xclbin),
        *(str(path) for path in xos),
    ]
    write_executable(
        link_command,
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh",
            f"export TMPDIR={shlex.quote(str(packet_root / 'tmp'))}",
            f"export TMP={shlex.quote(str(packet_root / 'tmp'))}",
            f"export TEMP={shlex.quote(str(packet_root / 'tmp'))}",
            "exec " + shlex.join(command),
        ],
    )

    collector = Path(__file__).resolve().with_name("collect_weighted_pma_hw_relink.py")
    collect_command = packet_root / "collect_result.sh"
    write_executable(
        collect_command,
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            shlex.join(
                [
                    "python3",
                    str(collector),
                    "--packet-root",
                    str(packet_root),
                ]
            ),
        ],
    )

    input_rows = ["role\tsha256\tbytes\tpath"]
    for role, path in (
        ("source_manifest", source_manifest_path),
        ("source_link_config", source_cfg),
        *(("input_xo", path) for path in xos),
    ):
        input_rows.append(f"{role}\t{sha256(path)}\t{path.stat().st_size}\t{path}")
    (packet_root / "inputs.tsv").write_text(
        "\n".join(input_rows) + "\n", encoding="utf-8"
    )

    manifest = {
        "schema": 1,
        "claim_class": "timing_closure_relink_candidate",
        "algorithm": "weighted_sssp",
        "handoff": "weighted_pma_to_axis_stream",
        "conversion_cost": "absent",
        "target": "hw",
        "profile": args.profile,
        "kernel_frequency_mhz": args.kernel_frequency,
        "jobs": args.jobs,
        "source_build_root": str(source_root),
        "source_git_head": source_manifest.get("GRI_GIT_HEAD", "unknown"),
        "source_manifest_sha256": sha256(source_manifest_path),
        "source_link_config_sha256": sha256(source_cfg),
        "input_xo_count": len(xos),
        "input_xos": [
            {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in xos
        ],
        "directives": PROFILES[args.profile],
        "link_config": str(link_cfg),
        "link_command": str(link_command),
        "output_xclbin": str(output_xclbin),
        "collector": str(collector),
        "collect_command": str(collect_command),
    }
    (packet_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return packet_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-build-root", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--kernel-frequency", type=int, default=200)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.kernel_frequency <= 0:
        parser.error("--kernel-frequency must be positive")
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    result = prepare(parsed)
    print(f"Prepared weighted-PMA hw relink packet: {result}")
    print(f"Run: {result / 'link_command.sh'}")
    print(f"Collect: {result / 'collect_result.sh'}")
