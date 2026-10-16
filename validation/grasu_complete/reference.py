"""Require fresh functional evidence for the exact inputs being synthesized."""

import json
from pathlib import Path
import shutil

from . import analysis
from .commands import VARIANTS
from .preparation import pin, unchanged


def freeze(output: Path, reference: Path, sources: list[dict]) -> list[dict]:
    report_path = reference / "results.json"
    report = json.loads(report_path.read_text())
    if report["status"] != "SOURCE_FUNCTIONAL_PASS_NOT_RTL" or report["stage"] != "source":
        raise ValueError("passing source functional campaign required before HLS")
    unchanged(report["pins"])
    keys = lambda rows: {row["member"]: row["sha256"] for row in rows}
    if keys(sources) != keys(report["sources"]):
        raise ValueError("HLS inputs differ from fresh source functional campaign")
    expected = [(variant, phase) for variant in VARIANTS
                for phase in ("compile-0", "link", "execute")]
    if [(row["variant"], row["phase"]) for row in report["steps"]] != expected:
        raise ValueError("source reference command matrix incomplete")
    for row in report["steps"]:
        if row["exit_code"] or row["stop_reason"] != "process_exit" or row["cleanup_snapshot_error"]:
            raise ValueError("failed source reference step")
    files = [report_path]
    for variant in VARIANTS:
        prefix = reference / "raw" / (variant + "-execute")
        stdout, stderr = [prefix.with_suffix(suffix) for suffix in (".stdout.txt", ".stderr.txt")]
        if stderr.read_text().strip() or analysis.functional(stdout.read_text(), variant) != report["functional"][variant]:
            raise ValueError("source reference oracle logs changed")
        files += [stdout, stderr]
    pins = []
    for original in files:
        frozen = output / "reference" / original.relative_to(reference)
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, frozen)
        pins += [pin(original), pin(frozen)]
    return pins
