# GraSU + ReGraph Integration Workspace

This repository is a lightweight integration workspace for comparing:

```text
GraSU dynamic graph update + ReGraph static graph compute
```

against the Spine end-to-end dynamic SSSP path.

The source projects are referenced from the existing local trees instead of being
vendored here:

```text
repos/GraSU   -> /home/chuxiao/GraSU
repos/ReGraph -> /home/chuxiao/ReGraph
```

## Initial Source State

- GraSU: `/home/chuxiao/GraSU`
  - branch: `codex/explore-grasu-u55c`
  - reference commit at workspace creation: `ce7aaf4`
- ReGraph: `/home/chuxiao/ReGraph`
  - current local tree is not a git repository

## Layout

```text
docs/       Experiment plans and notes
repos/      Relative symlinks to GraSU and ReGraph
scripts/    Reusable environment and check helpers
workloads/  Shared generated graph/update inputs
results/    Local run outputs, ignored by git except .gitkeep
```

## First Goal

Build a fair baseline for:

```text
Spine update + SSSP
vs
GraSU update + ReGraph compute
```

The first fair comparison should use unit-weight graphs so Spine SSSP and
ReGraph BFS-like execution can be interpreted consistently. A stricter weighted
SSSP comparison will require adding an SSSP UDF to ReGraph.

## Quick Check

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_workspace.sh
```

## First Chained Run

The first chained script uses GraSU to run and validate an update workload, then
converts the checked final graph into a ReGraph edge list and runs the existing
ReGraph PageRank hardware build:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_grasu_regraph_pr.sh
```

For a command-only preview:

```bash
./scripts/run_grasu_regraph_pr.sh --dry-run
```

This initial chain uses the GraSU result file as the final graph because the
current GraSU host was built with `OUTPUT_RESULT=0`. Rebuilding GraSU with final
edge-list export enabled will let the chain consume GraSU's emitted graph
directly.

## Current PR Sweep

Run a small matrix for the currently available chain:

```bash
./scripts/run_current_pr_sweep.sh
```

The sweep writes one directory per case plus a tab-separated summary:

```text
results/current_pr_sweep_<timestamp>/summary.tsv
```

## Weighted SSSP Bring-Up

The current ReGraph weighted SSSP status, evidence locations, and next hardware
proof gate are recorded in:

```text
docs/regraph_weighted_sssp_status_2026-07-12.md
```

Build ReGraph SSSP from a clean fixed-source scratch:

```bash
./scripts/build_regraph_sssp.sh --target hw_emu --run-tiny
./scripts/build_regraph_sssp.sh --target hw
```

## Resource Evidence

Resource collection and comparison for GraSU/ReGraph/combined hardware builds is
documented in:

```text
docs/resource_evidence_workflow_2026-07-12.md
```

The current Spine real `hw` baseline evidence is recorded in:

```text
docs/spine_hw_evidence_2026-07-12.md
```

Main commands:

```bash
./scripts/collect_vitis_evidence.py --label <label> --build-root <build-root> --out-dir <evidence-dir>
./scripts/compare_vitis_resources.py --before <baseline-evidence> --after <new-evidence> --out-dir <delta-dir>
```

## Combined hw_emu Bring-Up

The first single-xclbin GraSU + ReGraph `hw_emu` build and smoke tests are
recorded in:

```text
docs/combined_hwemu_bringup_2026-07-12.md
```

Rebuild the host-compatible combined `hw_emu` xclbin:

```bash
./scripts/build_combined_grasu_regraph_xclbin.sh \
  --target hw_emu \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible \
  --link
```

The current combined `hw_emu` proof passes both ReGraph tiny weighted SSSP and
GraSU update smoke on the same xclbin. Real `hw` still requires fixed-source
ReGraph `hw` artifacts first.

## SSSP Benchmark Harness

The next GraSU+ReGraph SSSP sweep plan and commands are recorded in:

```text
docs/sssp_benchmark_plan_2026-07-12.md
```

Generate smoke workloads and dry-run the chain:

```bash
./scripts/generate_sssp_benchmark_workloads.py --preset smoke
./scripts/run_grasu_regraph_sssp_sweep.sh --preset smoke --dry-run
./scripts/run_spine_builtin_sweep.sh --preset smoke --dry-run
```

## Pure Hardware Pipeline Branch

The pure GraSU -> ReGraph hardware-pipeline goal starts on:

```text
codex/pure-hw-pipeline
```

Stage-0 design and reproducibility notes:

```text
docs/pure_hw_pipeline_stage0_2026-07-14.md
```

Collect the current start-state evidence:

```bash
./scripts/collect_pure_hw_start_state.sh
```
