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

Current build-status snapshot:

```text
docs/pure_pipeline_status_2026-07-15.md
```

Collect the current start-state evidence:

```bash
./scripts/collect_pure_hw_start_state.sh
```

Refresh current `hw_emu`/`hw` readiness and export a report bundle without
starting Vitis. The refresh also records the source-level PMA handoff,
completion-token, AXI stream, timing, and boundary-preparation contract check:

```bash
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_$(git rev-parse --short HEAD)
```

For a short read-only status check that prints the current pure-pipeline
xclbins, active Vitis/Vivado builders, and the next target-flow command:

```bash
./scripts/report_pure_pipeline_next_steps.py
```

The report prints four command blocks:

```text
next_commands       What should run next right now.
postbuild_acceptance
                    Guarded post-build wrapper commands once a target xclbin appears.
postrun_followup    What to run if a manually built xclbin appears.
stage0_followup     Same-input matrix commands after postrun acceptance passes.
```

The `flow_current` column shows whether the latest target-flow evidence for a
target matches the current build-relevant source fingerprints. Documentation-only
commits do not invalidate it; `no` means the next target-flow invocation should
refresh prelaunch evidence before relying on it. The `readiness_ready` column
uses the newest readiness report, which may allow active external builders;
`strict_ready` and `strict_blockers` show the newest strict launch-precheck view
with `allow_active_builders=0`. The `packet_current` column shows whether a
saved launch packet exists for that target and matches the current
build-relevant source fingerprints; when it is `yes`, the helper recommends the
packet's executable `launch_command.sh` instead of asking you to regenerate an
equivalent command under a documentation-only commit label. The printed
`source_fingerprint_sha256` is the aggregate digest of the build-relevant source
roles used for that decision. The `postrun` column summarizes the newest
post-build acceptance check for each target. A target is not treated as finished
just because its xclbin exists; if the xclbin is present but `postrun` is not
`pass`, the helper recommends a `--skip-build` target-flow command that reruns
smoke correctness, same-input comparison, requirement audit, evidence bundle
export, and postrun acceptance gates on the existing xclbin. In a `--skip-build`
postrun flow, the compile/link log gates are marked `required=no`; the run still
requires the existing xclbin, xclbin metadata contract, smoke summaries,
comparison table, audit, and evidence bundle to pass.

The `stage0_gate` and `stage0_full` columns summarize same-input matrix
coverage for the target. `stage0_gate=pass` means the required chain,
hot-source, spread, and hot-destination smoke families have matched the CPU
oracle and baseline inputs. `stage0_full=pass` is reserved for the full tracked
stage-0 matrix.

Current reproducible target flow:

```bash
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_$(git rev-parse --short HEAD)
./scripts/check_pure_pipeline_source_contracts.py \
  --label pre_hwemu_$(git rev-parse --short HEAD)
./scripts/check_pure_pipeline_build_readiness.sh --target hw_emu
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_$(git rev-parse --short HEAD) \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

If unrelated Vitis/Vivado builders are active and you only need to prepare a
launch packet, add `--allow-active-builders` to the packet command. The generated
target-flow command still keeps the wait-idle guard before launching Vitis.

If a long build was run manually and produced the expected xclbin, use the
`postbuild_acceptance` command from `report_pure_pipeline_next_steps.py`. That
guarded wrapper first runs the `--skip-build` postrun flow, then launches the
same-input stage0 matrix. The low-level `postrun_followup` and
`stage0_followup` blocks remain available when the two phases need to be run or
debugged separately.

The same post-build sequence can be launched through a guarded wrapper. It
fails before running anything if the target xclbin is still missing:

```bash
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw_emu
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw --mode gate
```

If the long build is running in another terminal, wait for the target xclbin and
launch the same guarded acceptance sequence automatically:

```bash
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py --target hw_emu
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py --target hw --mode gate
```

Preview the exact postrun and matrix commands before the xclbin exists:

```bash
./scripts/run_pure_pipeline_postbuild_acceptance.py \
  --target hw_emu \
  --dry-run \
  --allow-missing-xclbin
```

The launch packet regenerates target compile/link/config scripts before its
preflight checks by default, so its source-contract and readiness evidence match
the scripts the target flow will launch. Use `--no-prepare` only when inspecting
an existing generated build directory. It also writes `source_fingerprints.tsv`
with tree hashes for the integration scripts/kernels/tools, GraSU source, and
ReGraph source directories. This is required because the local ReGraph tree is
not currently a git repository, so the launch packet must record a content hash
in addition to git commit IDs.

The target-flow wrapper records the same source fingerprints in the target
`run_logs/` directory before build launch, so direct invocations of
`run_pure_pipeline_target_flow.sh` are also source-hash reproducible.

Run the same wrapper with `--target hw` after `hw_emu` passes. The wrapper
records the build parameters, checks source-level PMA/stream/barrier contracts,
writes a readiness preflight report, waits for other Vitis/Vivado jobs to become
idle, optionally requires a continuous idle settle window, optionally
regenerates compile/link/config scripts, optionally clears stale target artifacts
from the build directory, monitors the build output, runs a staged smoke gate,
then emits the requirement audit and compact evidence bundle. Use
`--strict-readiness` when you want active external builders to abort before the
wait-idle phase. Keep the default source-contract preflight enabled;
`--no-source-contracts` is for debugging only. Use `--skip-bundle` only for
debugging runs that intentionally do not need the report matrices.

Readiness reports include a `build_artifacts` row. If the target xclbin is
missing while the target `build/` directory still contains old children, the row
is `WARN` and the recommended flow's `--clean-build-artifacts` option should be
kept enabled.

Export a compact evidence bundle for reports. The target-flow wrapper does this
automatically after its audit step; this
standalone command is useful when repacking an existing audit:

```bash
./scripts/export_pure_pipeline_evidence_bundle.py \
  --out-dir results/pure_pipeline_evidence_bundle_after_$(git rev-parse --short HEAD)
```
