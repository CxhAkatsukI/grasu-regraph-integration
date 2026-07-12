# Combined GraSU + ReGraph hw_emu Bring-Up, 2026-07-12

This note records the first single-xclbin integration proof for:

```text
GraSU dynamic update kernels + ReGraph weighted SSSP kernels
```

The proof here is `hw_emu`, not final real `hw`. It verifies that the two
accelerators can be linked into one Vitis binary and that the existing GraSU and
ReGraph hosts can each load that same binary on their smoke workloads.

## Build Script

Added:

```text
scripts/build_combined_grasu_regraph_xclbin.sh
```

The script:

- checks that GraSU and ReGraph `.xo` inputs exist;
- merges GraSU and ReGraph connectivity into one Vitis config;
- writes a manifest, input hashes, generated config, and exact link command;
- optionally runs `v++ --link` inside `vivado-runner:22.04-feiyang`.

For final real `hw`, the script must mount both `/home/chuxiao` and `/data`
into the Vitis container. GraSU `.xo` files live under `/home/chuxiao`, while
the successful cold-start ReGraph real `hw` `.xo` files live under
`/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch`.

Default ReGraph HBM offset is `0` because the current ReGraph host uses fixed
HBM bank IDs in `host/preprocess/partition_schedule.cpp`. A non-zero offset can
compile, but it also requires matching host-side buffer bank changes.

## Successful Combined hw_emu Link

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_combined_grasu_regraph_xclbin.sh \
  --target hw_emu \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible \
  --link
```

Main output:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin
sha256 daf8bb44c32295a27827993bdf913eb9d311f27e4d21efbaf46edfc57224995f
```

Generated command/config evidence:

```text
link command:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/link_command.sh
  sha256 f29096041f711c9dc32992b62e0ed2d9a0a417be697e940eb92c29a3ef4e2901

link config:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/config/grasu_regraph_combined_hw_emu.cfg
  sha256 9f5e0f9ec7538665c0c0ee14e27ffa0eeca8f2c68326c72ea624824a71e34377

link summary:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin.link_summary
  sha256 26431f3dd3b74c0f0e60b9aa00dc767049c93ec6194311ea1e729a48ceaa2a32
```

The combined binary contains 15 CUs:

```text
GraSU:
  bin_search:    4
  dispatch:      1
  process_cache: 2
  process_ddr:   2

ReGraph:
  kernelApply:                1
  kernelHBMWrapper:           1
  littleKernelScatterGather:  1
  kernelLittleGSMerger:       1
  bigKernelScatterGather:     1
  kernelBigGSMerger:          1
```

## Functional Smoke Evidence

### ReGraph Weighted SSSP

Workload:

```text
dataset: /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/dataset/tiny-weighted-sssp.txt
source: 0
numD: 1
supersteps: 4
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hwemu_function_20260712_020457_host_compatible_retry
```

Key result:

```text
Device[0]: program successful!
Supersteps: 4
Starting superstep 1/4
Starting superstep 2/4
Starting superstep 3/4
Starting superstep 4/4
Processed edges: 8; Graph edges: 5
All the simulator processes exited successfully
mismatch_count=0
```

### GraSU Update Smoke

Workload:

```text
graph:  /home/chuxiao/GraSU/u55c_hbm/smoke/delete_one.graph
result: /home/chuxiao/GraSU/u55c_hbm/smoke/delete_one.result
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hwemu_grasu_function_20260712_021521
```

Key result:

```text
check result passed
kernel start running...
kernel finish
All the simulator processes exited successfully
```

The `hw_emu` runtime is slow and not a performance number. ReGraph tiny SSSP on
the combined xclbin reported about 529 s, and GraSU smoke reported about 510 s.
Use these only as functional proof.

## HBM Mapping Finding

An earlier combined `hw_emu` build with `--regraph-hbm-offset 4` linked
successfully:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_link_check
```

But ReGraph host failed at runtime:

```text
XRT WARNING: Argument '0' of kernel 'kernelHBMWrapper' is allocated in memory bank 'HBM[1]';
compute unit 'kernelHBMWrapper_1' cannot be used with this argument and is ignored.
XRT ERROR: kernel 'kernelHBMWrapper' has no compute units to support required argument connectivity.
```

Interpretation: ReGraph's host-side buffers still use the original HBM bank
assignment. Keeping offset `0` is host-compatible. Moving ReGraph to HBM[4..7]
would require host changes in the ReGraph partition/buffer allocation path.

## Resource Evidence

Evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_022520_combined_hwemu_host_compatible
```

Important comparison result:

```text
GraSU baseline vs combined:
  same-component HLS changes: 0
  same-kernel CU count changes: 0

ReGraph baseline vs combined:
  same-component HLS changes: 0
  same-kernel CU count changes: 0
```

This is `hw_emu`, so there is no placed/routed utilization. Final resource
claims still require real `hw` evidence.

Automation added after this bring-up:

```text
/home/chuxiao/grasu-regraph-integration/scripts/collect_combined_hw_evidence.sh
```

The script collects standalone GraSU, standalone ReGraph, and combined xclbin
evidence in one bundle, then runs both resource comparisons. A `hw_emu` smoke
of that script was written to:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_104941_combined_hwemu_script_smoke2
```

That smoke intentionally compares the latest cold-start ReGraph `hw_emu`
standalone artifact against the older host-compatible combined `hw_emu` xclbin,
whose manifest still points to:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/xclbin_hw_emu_sssp
```

Therefore its small ReGraph HLS differences are a useful regression-test of the
comparison flow, not a final combined-resource conclusion.

## Fresh User Build Check, 2026-07-12 13:36 CST

The current host-compatible combined `hw_emu` product was rechecked after the
user reported that the `hw_emu` build had completed.

Artifact check:

```text
xclbin:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin
  size 108956445 bytes
  sha256 daf8bb44c32295a27827993bdf913eb9d311f27e4d21efbaf46edfc57224995f

link summary:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin.link_summary
  sha256 26431f3dd3b74c0f0e60b9aa00dc767049c93ec6194311ea1e729a48ceaa2a32

emconfig:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/run_grasu_smoke/emconfig.json
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/run_regraph_tiny/emconfig.json
```

Resource evidence already collected for this artifact:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_130630_combined_hwemu_usercheck
```

That first usercheck compared the old host-compatible combined xclbin against
the newer cold-start ReGraph standalone baseline. A manifest-aligned evidence
rerun now uses the ReGraph build root recorded inside the combined build's
`manifest.env`:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_manifest_aligned_hwemu_check
```

Same-component review summary from the manifest-aligned evidence:

```text
GraSU vs combined:
  accelerator_util same-component changes: 0
  hls_top_area same-component changes: 0
  kernel CU count same-kernel changes: 0
  connectivity binding same-endpoint changes: 0

ReGraph vs combined:
  accelerator_util same-component changes: 0
  hls_top_area same-component changes: 0
  kernel CU count same-kernel changes: 0
  connectivity binding same-endpoint changes: 0
```

The earlier two small ReGraph HLS deltas were therefore a baseline mismatch,
not a same-component resource change in this combined `hw_emu` artifact.

Fresh combined functional command that exposed the mismatch:

```bash
cd /home/chuxiao/grasu-regraph-integration
TIMEOUT_SECONDS=900 ./scripts/finalize_combined_hw_build.sh \
  --target hw_emu \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible \
  --session '' \
  --preset smoke \
  --skip-evidence \
  --smoke-out /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_fresh_20260712_133634
```

Fresh combined smoke result from that command:

```text
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_fresh_20260712_133634

tiny_chain_v16:
  status FAIL
  wall_seconds 555.888
  exit_code 139
```

The first stage, GraSU on the combined xclbin, did pass:

```text
check result passed
scheduler config ert(1), dataflow(1), slots(32), cudma(0), cuisr(0), cdma(0), cus(15)
kernel start running...
kernel finish
time is 494053.490105 ms
All the simulator processes exited successfully
```

The generated GraSU result was converted into ReGraph weighted SSSP input:

```text
converted_edges=15
output=/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_fresh_20260712_133634/tiny_chain_v16/tiny_chain_v16.from_grasu.sssp.edges
```

The failure occurs in the second stage, ReGraph on the same combined xclbin:

```text
Device[0]: program successful!
Creating a big kernel [bigKernelScatterGather:{bigKernelScatterGather_1}] for CU(1)
Creating a little kernel [littleKernelScatterGather:{littleKernelScatterGather_1}] for CU(1)
Creating the apply kernel [kernelApply:{kernelApply_1}]
Creating the hbm kernel [kernelHBMWrapper:{kernelHBMWrapper_1}]
[INFO] Starting superstep 1/16
Segmentation fault
```

Simulator evidence for the failed ReGraph stage:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/.run/2765907/hw_emu/device0/binary_0/behav_waveform/xsim

FATAL_ERROR:
  sim_qdma.cpp, line 105, in SystemC process
  .pfm_top_wrapper.pfm_top_i.static_region.sim_qdma_0.inst.simulate_single_cycle
```

Corrected interpretation: the command above mixed a combined xclbin built from
old ReGraph `fixed_scratch` `.xo` files with the newer cold-start ReGraph host.
The combined build manifest proves the xclbin came from:

```text
REGRAPH_XCLBIN_DIR=/home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/xclbin_hw_emu_sssp
```

The failing smoke used:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/host_graph_fpga_sssp
```

Therefore the ReGraph segfault is not valid evidence against the current
cold-start combined design. It is evidence that finalization scripts must not
mix hosts and xclbins from different ReGraph builds.

Script fix:

```text
scripts/finalize_combined_hw_build.sh
scripts/collect_combined_hw_evidence.sh
```

Both scripts now read `manifest.env` from the combined build root. When the
caller does not explicitly pass a ReGraph host or standalone baseline, the
scripts derive them from the ReGraph xclbin directory recorded in the manifest.
Dry-run check for the old host-compatible `hw_emu` artifact now selects:

```text
regraph_host=/home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/host_graph_fpga_sssp
```

The active real `hw` build is already based on the current cold-start ReGraph
`.xo` files under:

```text
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp
```

If we need a current cold-start combined `hw_emu` artifact before the real `hw`
build finishes, use a new build root rather than reusing the old
`combined_hw_emu_host_compatible` directory.

## Next hw Steps

Cold-start ReGraph real `hw` artifacts are now available and have passed a tiny
real-board smoke test. They are no longer the missing prerequisite; the active
long-running step is final combined `hw` linking.

Historical preflight status before the ReGraph real `hw` run completed:

```text
GraSU hw inputs: present
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/bin_search.hw.xo
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/dispatch.hw.xo
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/process_cache.hw.xo
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/process_ddr.hw.xo

ReGraph cold-start source: present
  /home/chuxiao/grasu-regraph-integration/repos/ReGraph -> /home/chuxiao/ReGraph
  reset_tmp_prop cold-start gather init is present in little and big kernels

ReGraph cold-start 250 MHz hw scratch: running
  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch
  all 6 ReGraph hw .xo files are present
  Vitis/Vivado is currently in vpl synth

Combined real-hw link preflight: generated
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_preflight
  inputs.tsv records hashes for 4 GraSU .xo files and 6 ReGraph .xo files
```

Latest current real-hw preflight, 2026-07-12 10:00 Asia/Shanghai:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_current_preflight
```

This generate-only run succeeded with current inputs:

```text
target: hw
kernel_frequency: 250
GraSU build root:
  /home/chuxiao/grasu-regraph-integration/repos/GraSU/.tmp_build/u55c_hbm_hw/build
ReGraph xclbin/xo dir:
  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp
link config:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_current_preflight/config/grasu_regraph_combined_hw.cfg
link command:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_current_preflight/link_command.sh
input hash table:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_current_preflight/inputs.tsv
```

The generated config keeps the same CU counts as the standalone designs:

```text
GraSU:
  bin_search:    4
  dispatch:      1
  process_cache: 2
  process_ddr:   2

ReGraph:
  kernelApply:                1
  kernelHBMWrapper:           1
  littleKernelScatterGather:  1
  kernelLittleGSMerger:       1
  bigKernelScatterGather:     1
  kernelBigGSMerger:          1
```

The current config keeps `REGRAPH_HBM_OFFSET=0` for host compatibility. That
means ReGraph still uses HBM[0], HBM[1], HBM[2], HBM[3], and HBM[30], while
GraSU also uses HBM[0..3]. This is correct for functional compatibility, but it
must be called out when explaining combined-hardware performance because the two
accelerators are not isolated onto disjoint HBM banks yet.

Build cold-start ReGraph SSSP real hardware and immediately run the tiny
weighted SSSP hardware smoke if board access is available. The current run uses
the same command shape, without `--run-tiny`, inside tmux:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_regraph_sssp.sh \
  --target hw \
  --scratch /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
  --evidence-dir /home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_coldinit_250mhz_20260712_092221 \
  --kernel-frequency-mhz 250 \
  --run-tiny \
  --source-vertex 0 \
  --supersteps 4 \
  --num-dense 1
```

If only the long build should run first, omit `--run-tiny` and run the smoke
manually after reviewing the build artifacts.

Monitor the cold-start ReGraph `hw` build:

```bash
tmux has-session -t regraph_hw_coldinit_250mhz_20260712_092221 && echo running || echo stopped

tail -120 \
  /home/chuxiao/ReGraph/.tmp_doc/regraph_hw_coldinit_250mhz_20260712_092221.tmux.log

find /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch -maxdepth 8 \
  \( -name 'graph_fpga.hw*.xclbin' \
     -o -name '*.xclbin.link_summary' \
     -o -name '*kernel_util_routed.rpt' \
     -o -name '*slr_util_routed.rpt' \
     -o -name '*timing_summary*.rpt' \
     -o -name 'dr_timing_summary.rpt' \) \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -120
```

Collect cold-start ReGraph `hw` evidence after it completes:

```bash
cd /home/chuxiao/grasu-regraph-integration
BASE=results/resource_evidence_$(date +%Y%m%d_%H%M%S)_regraph_coldinit_hw_250mhz
mkdir -p "$BASE"

./scripts/collect_vitis_evidence.py \
  --label regraph_sssp_hw_coldinit_250mhz \
  --build-root /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
  --out-dir "$BASE/regraph_sssp_hw_coldinit_250mhz" \
  --artifact /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
  --artifact /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin \
  --note 'Cold-start ReGraph weighted SSSP real hw build at 250 MHz.'
```

Then link the real combined hardware:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_combined_grasu_regraph_xclbin.sh \
  --target hw \
  --kernel-frequency 250 \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz \
  --link
```

After real `hw` completes, collect and compare evidence:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/collect_combined_hw_evidence.sh --target hw
```

The resulting top-level `README.md` points to the exact standalone and combined
evidence bundles plus both comparison summaries. Same-component HLS,
accelerator-utilization, or CU-count changes must be explained before using the
combined xclbin for final performance claims.

## Combined Real HW Attempt

Standalone ReGraph cold-start weighted SSSP real `hw` completed at 250 MHz and
passed a tiny real-board smoke test. The final ReGraph inputs for combined
linking are:

```text
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/kernelApply.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/kernelHBMWrapper.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/littleKernelScatterGather.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/kernelLittleGSMerger.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/bigKernelScatterGather.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/kernelBigGSMerger.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
```

First combined real `hw` link attempt:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112243
```

This failed immediately because the podman container did not mount `/data`, so
`v++` could not see the six ReGraph `.xo` files:

```text
ERROR: [v++ 60-602] Source file does not exist:
  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/kernelApply.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
```

Script fix:

```text
scripts/build_combined_grasu_regraph_xclbin.sh now mounts /data:/data
```

Second combined real `hw` link attempt:

```text
session:    combined_hw_coldinit_250mhz_20260712_112335
build root: /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335
log:        /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/tmux_driver.log
```

This run has passed input extraction and entered normal Vitis `system_link`:

```text
INFO: [SYSTEM_LINK 82-70] Extracting xo v3 file .../bin_search.hw.xo
INFO: [SYSTEM_LINK 82-70] Extracting xo v3 file .../kernelApply.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
INFO: [SYSTEM_LINK 82-53] Creating IP database .../xd_ip_db.xml
```

Latest observed status, 2026-07-12 11:30 Asia/Shanghai:

```text
tmux session is still running
system_link completed
VPL create_project completed
VPL create_bd completed
VPL generate_target completed
VPL config_hw_runs started
Vivado launched synth runs under prj/prj.runs
active vivado process is consuming CPU, so this is not the earlier "running but idle" failure mode
```

Useful live logs:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/tmux_driver.log
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/link/link/vivado/vpl/runme.log
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/link/link/vivado/vpl/vivado.log
```

Monitor:

```bash
tmux has-session -t combined_hw_coldinit_250mhz_20260712_112335 && echo running || echo stopped
tail -120 /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/tmux_driver.log
```

Structured monitor helper added:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/monitor_combined_hw_build.sh \
  --build-root .tmp_build/combined_hw_coldinit_250mhz_20260712_112335 \
  --session combined_hw_coldinit_250mhz_20260712_112335 \
  --idle-warn-minutes 10
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_114413.txt
```

Observed status, 2026-07-12 11:44 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final link has not completed yet
newest log updated at 2026-07-12 11:44:13, idle_seconds=0
VPL step: synth
Block-level synthesis progressed to 88 of 262 jobs complete, 7 jobs running
```

This confirms the run is still active and making forward progress. The monitor
script should be used for later status checks before deciding whether the build
is idle or stuck.

Observed status, 2026-07-12 12:08 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest log updated at 2026-07-12 12:08:02, idle_seconds=5
VPL synth completed at 03:58:04
VPL impl started at 03:58:04
impl_1 is active under prj/prj.runs/impl_1/runme.log
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_120743.txt
```

The structured monitor now also prints an `Implementation Run Tail` section
from:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/link/link/vivado/vpl/prj/prj.runs/impl_1/runme.log
```

This is useful once block synthesis is over because the top VPL log only says
`Waiting for impl_1 to finish`; the implementation run log shows lower-level
Vivado activity such as constraint parsing, implementation warnings, and later
place/route/bitstream milestones.

Observed status, 2026-07-12 12:15 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest log updated at 2026-07-12 12:14:57, idle_seconds=6
Vitis top log: Finished 2nd of 6 tasks, FPGA linking synthesized kernels to platform
Vitis top log: Starting logic optimization
Vivado impl log: link_design completed successfully
Vivado impl log: Command: opt_design
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_121503.txt
```

This is stronger evidence than the earlier synthesis-progress snapshots: the
combined design passed the `link_design` stage and is now in real implementation
optimization. There are still warnings/critical warnings, but no fatal error or
stale log condition has appeared in this snapshot.

Observed status, 2026-07-12 12:20 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest log updated at 2026-07-12 12:18:36, idle_seconds=125
Vitis top log: Finished 3rd of 6 tasks, FPGA logic optimization
Vitis top log: Starting logic placement
Vivado log: Command: place_design -retiming
Vivado log: Multithreading enabled for place_design using a maximum of 8 CPUs
```

This means the combined build has passed synthesis, `link_design`, and
`opt_design`, and is now in placement. It is still active; there is no xclbin
yet and no stale-log warning.

Observed status, 2026-07-12 12:36 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest log updated at 2026-07-12 12:36:11, idle_seconds=4
Vitis top log: still in logic placement
placement progressed through:
  Phase 2.1.1.1 PBP: Partition Driven Placement
  Phase 2.1.1.2 PBP: Clock Region Placement
  Phase 2.1.1.3 PBP: Discrete Incremental
  Phase 2.1.1.4 PBP: Compute Congestion
  Phase 2.1.1.5 PBP: Macro Placement
  Phase 2.1.1.6 PBP: UpdateTiming
  Phase 2.2 Physical Synthesis After Floorplan
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_123614.txt
```

This snapshot confirms the build is still making forward progress inside
placement. The current warnings include expected placement/SLR messages, but
there is still no fatal error and no idle-log warning.

## Monitor Activity Refinement

At 2026-07-12 12:44 Asia/Shanghai the text logs had not advanced for about
492 seconds, but the Vivado implementation process was still using CPU and
`place_design.pb` was being updated:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/link/link/vivado/vpl/prj/prj.runs/impl_1/place_design.pb
```

I updated `scripts/monitor_combined_hw_build.sh` so `idle_warning` is now based
on the newest log or Vivado progress file (`*.pb`, `*.rst`, `*.json`, `*.xutil`)
rather than logs only. The monitor still prints `newest_log`, but it now also
prints `newest_activity`.

Validation snapshot:

```text
checked_at=2026-07-12T12:45:37+08:00
newest_log=.../tmux_driver.log
newest_activity=.../impl_1/place_design.pb
idle_seconds=1
idle_warning=none
```

This prevents long `place_design` phases from being misclassified as stuck when
Vivado is actively updating implementation progress files.

Observed status, 2026-07-12 12:51 Asia/Shanghai, using the refined monitor:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest_log=.../tmux_driver.log
newest_activity=.../impl_1/place_design.pb
idle_seconds=19
idle_warning=none
Vitis top log: still in place_design -retiming
Vivado progress file: place_design.pb updated at 2026-07-12 12:51:17
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_125135.txt
```

The build remains in placement and has not produced the final xclbin yet, but
the implementation progress file is actively updating. The next actionable
step is still to run `scripts/finalize_combined_hw_build.sh` once
`build/grasu_regraph_combined.hw.xclbin` appears.

Observed status, 2026-07-12 12:58 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest_log=.../build/link/link/vivado/vpl/vivado.log
newest_activity=.../build/link/link/vivado/vpl/vivado.pb
idle_seconds=0
idle_warning=none
placement progressed to:
  Phase 2.5.1 UpdateTiming Before Physical Synthesis
  Phase 2.5.2 Physical Synthesis In Placer
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_125841.txt
```

This is forward progress beyond the earlier `Phase 2.5 Global Placement Core`
snapshot. The build is still in `place_design -retiming`, so no combined real
`hw` smoke can run yet.

## Combined hw_emu Artifact Check, 13:17

The current combined `hw_emu` product exists and was checked again:

```text
xclbin: /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin
sha256: daf8bb44c32295a27827993bdf913eb9d311f27e4d21efbaf46edfc57224995f
evidence: /home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_130630_combined_hwemu_usercheck
```

The resource evidence confirms the combined xclbin has 15 CUs:

```text
GraSU:   bin_search x4, dispatch x1, process_cache x2, process_ddr x2
ReGraph: kernelApply x1, kernelHBMWrapper x1,
         littleKernelScatterGather x1, kernelLittleGSMerger x1,
         bigKernelScatterGather x1, kernelBigGSMerger x1
```

Comparison against standalone `hw_emu` evidence:

```text
GraSU same-component resource changes: 0
GraSU same-kernel CU count changes:    0
GraSU same-endpoint HBM/SLR changes:   0

ReGraph same-kernel CU count changes:  0
ReGraph same-endpoint HBM/SLR changes: 0
ReGraph HLS top area changes:          2 small FF/LUT estimate deltas
```

Functional checks found an environment issue in the sweep wrapper rather than a
bad xclbin. The old wrapper set `XCL_EMULATION_MODE=hw_emu` only for ReGraph,
so the GraSU host failed before simulation when asked to load a `hw_emu`
xclbin. Manually sourcing Vitis/XRT and setting `EMCONFIG_PATH` allowed GraSU
to enter xsim with the combined xclbin, but a tiny chain case did not finish
within a 300 second interactive timeout:

```text
/home/chuxiao/grasu-regraph-integration/results/grasu_manual_hwemu_envcheck_20260712_130855_sourcevitis
exit_code=124
```

This is consistent with the earlier cached combined `hw_emu` runtime evidence:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/run_grasu_smoke/emulation_debug.log
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/run_regraph_tiny/emulation_debug.log
```

Both show `All the simulator processes exited successfully`, but host stdout was
not fully captured there. Therefore, the current conclusion is:

```text
combined hw_emu artifact/resources: checked
combined ReGraph/GraSU simulator runtime: known-good from cached run logs
fresh full GraSU->ReGraph smoke in this turn: not completed; hw_emu is too slow for the 300 s interactive timeout
```

I updated `scripts/run_grasu_regraph_sssp_sweep.sh` so future `hw_emu` sweeps:

```text
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
set XCL_EMULATION_MODE for both GraSU and ReGraph
set EMCONFIG_PATH for both GraSU and ReGraph
record these paths in each case.env
```

I also updated `scripts/finalize_combined_hw_build.sh` so combined `hw_emu`
finalization passes:

```text
--grasu-emconfig-path  <build-root>/run_grasu_smoke
--regraph-emconfig-path <build-root>/run_regraph_tiny
```

Validation:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/run_grasu_regraph_sssp_sweep.sh scripts/finalize_combined_hw_build.sh

./scripts/finalize_combined_hw_build.sh \
  --target hw_emu \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible \
  --session '' \
  --preset smoke \
  --skip-evidence \
  --dry-run

./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset smoke \
  --grasu-host /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hwemu/GraSU_host_u55c \
  --regraph-host /home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/host_graph_fpga_sssp \
  --combined-xclbin /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin \
  --out-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_dryrun_envcheck_20260712_131738 \
  --xcl-emulation-mode hw_emu \
  --grasu-emconfig-path /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/run_grasu_smoke \
  --regraph-emconfig-path /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/run_regraph_tiny \
  --dry-run
```

## Combined Real hw Monitor, 13:20

Observed status, 2026-07-12 13:20 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest_log=.../tmux_driver.log
newest_activity=.../tmux_driver.log
idle_seconds=189
idle_warning=none
placement progressed through:
  Phase 3.3 Small Shape DP
  Phase 3.4 Place Remaining
  Phase 3.6 Pipeline Register Optimization
  Phase 4 Post Placement Optimization and Clean-Up
  Phase 4.1.1.3 Post Placement Timing Optimization
current estimated timing after placement physopt:
  WNS=-0.666
  TNS=-25.051
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_132011.txt
```

This is still forward progress. The negative WNS is not yet the final routed
timing result, but it is important evidence to keep because it may explain a
future route/timing failure if the build cannot close timing.

## Combined Real hw Monitor, 13:23

Observed status, 2026-07-12 13:23 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final placed/routed xclbin has not completed yet
newest_log=.../build/link/link/vivado/vpl/vivado.log
newest_activity=.../build/link/link/vivado/vpl/vivado.pb
idle_seconds=1
idle_warning=none
placement progressed through:
  Phase 4.1.1.4 Replication
  Phase 4.2 Post Placement Cleanup
post-placement timing:
  WNS improved from -0.666 to -0.144 after replication
important warning:
  placer reports the design is highly congested and may have difficulty routing
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_132307.txt
```

The build is still active and has not reached route completion. The congestion
warning is now the main risk to watch.

## Combined Real hw Monitor, 13:24

Observed status, 2026-07-12 13:24 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final xclbin has not completed yet
newest_log=.../build/link/link/vivado/vpl/vivado.log
newest_activity=.../build/link/link/vivado/vpl/vivado.pb
idle_seconds=52
idle_warning=none
place_design completed successfully
place_design elapsed time: 01:05:19
place_design CPU time:     02:36:30
peak memory:               21179.605 MB
post placement WNS:        -0.144
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_132455.txt
```

This clears the placement stage. The next decisive gates are phys-opt, route,
final timing, bitstream/package, and xclbin emission.

## Combined Real hw Monitor, 13:26

Observed status, 2026-07-12 13:26 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final xclbin has not completed yet
newest_log=.../build/link/link/vivado/vpl/vivado.log
newest_activity=.../build/link/link/vivado/vpl/vivado.pb
idle_seconds=12
idle_warning=none
place_design completed successfully
current command: phys_opt_design
```

Latest monitor snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hw_monitor_20260712_132640.txt
```

This confirms the build moved past placement into post-placement physical
optimization. The next stage to watch is `route_design`.

## Combined hw_emu User-Success Check, 14:19

Observed status, 2026-07-12 14:19 Asia/Shanghai:

```text
combined_xclbin=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin
sha256=daf8bb44c32295a27827993bdf913eb9d311f27e4d21efbaf46edfc57224995f
manifest=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/manifest.env
grasu_host=/home/chuxiao/grasu-regraph-integration/repos/GraSU/.tmp_build/u55c_hbm_hwemu/GraSU_host_u55c
grasu_host_sha256=9fb21cc3000f9d3219e194d7cdf6df7fd8a5a592c65e2767247fd0b8af43d34a
regraph_host=/home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/host_graph_fpga_sssp
regraph_host_sha256=15db9e29a1cb9dc6ebc572c96214e390d331be1996ba1635145bbb0261f39032
```

Important manifest detail:

```text
REGRAPH_XCLBIN_DIR=/home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/xclbin_hw_emu_sssp
```

So this artifact must be tested with the matching `fixed_scratch` ReGraph host,
not the newer cold-init ReGraph host.

Evidence collection command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_combined_hw_build.sh \
  --target hw_emu \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible \
  --session '' \
  --preset smoke \
  --evidence-out /home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_hwemu_user_success_check \
  --smoke-out /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_user_success_check
```

Evidence directory:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_hwemu_user_success_check
```

Resource comparison summary:

```text
GraSU same-component changes:
  accelerator_util=0
  hls_top_area=0
  kernel CU count=0
  connectivity binding=0

ReGraph same-component changes:
  accelerator_util=0
  hls_top_area=0
  kernel CU count=0
  connectivity binding=0
```

Added rows/kernels/endpoints in the comparison are expected because the after
side is the combined xclbin. The review signal is the same-component delta,
which is zero for both accelerators in this hw_emu artifact.

Functional evidence:

```text
GraSU combined-xclbin run:
  log=/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_user_success_check/tiny_chain_v16/grasu.log
  result=passed
  key lines:
    check result passed
    kernel finish
    INFO: [HW-EMU 06-1] All the simulator processes exited successfully
  hw_emu kernel time: 498047.352124 ms

GraSU result converted to ReGraph SSSP input:
  edges=/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_user_success_check/tiny_chain_v16/tiny_chain_v16.from_grasu.sssp.edges
  converted_edges=15

ReGraph combined-xclbin minimal run:
  log=/home/chuxiao/grasu-regraph-integration/results/regraph_hwemu_min2_combined_user_success_check/regraph_min2.log
  input=GraSU-converted 16-vertex chain, 15 weighted edges
  source=0
  num_dense=1
  supersteps=2
  result=exit code 0
  key lines:
    Device[0]: program successful!
    [INFO] Starting superstep 1/2
    [INFO] Starting superstep 2/2
    BIG_KERNEL finished
    Verifying end-to-end on hardware vs. end-to-end on software...
    Processed edges: 16; Graph edges: 15
    INFO: [HW-EMU 06-1] All the simulator processes exited successfully
```

Manual ReGraph minimal command:

```bash
cd /home/chuxiao/grasu-regraph-integration
mkdir -p results/regraph_hwemu_min2_combined_user_success_check
bash -lc 'source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh; export XILINX_XRT=/opt/xilinx/xrt; export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}; cd /home/chuxiao/grasu-regraph-integration/repos/ReGraph; timeout 420s env REGRAPH_SOURCE=0 XCL_EMULATION_MODE=hw_emu EMCONFIG_PATH=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/run_regraph_tiny /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/host_graph_fpga_sssp /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_combined_hwemu_user_success_check/tiny_chain_v16/tiny_chain_v16.from_grasu.sssp.edges 1 2' \
  > /home/chuxiao/grasu-regraph-integration/results/regraph_hwemu_min2_combined_user_success_check/regraph_min2.log 2>&1
```

The default `smoke` preset is too slow for full chained hw_emu validation: the
first GraSU tiny-chain case alone took about 498 seconds, and the ReGraph
16-superstep half was still running at superstep 4/16 after several more
minutes. For hw_emu, use this as the recommended functional gate:

```text
1. collect combined evidence and same-component resource deltas
2. run one GraSU tiny case through the combined xclbin
3. convert the GraSU result to ReGraph weighted SSSP input
4. run a 2-superstep ReGraph minimal check through the same combined xclbin
```

## Combined Real hw Monitor, 14:24

Observed status, 2026-07-12 14:24 Asia/Shanghai:

```text
tmux=running
xclbin=missing; final xclbin has not completed yet
newest_log=.../build/link/link/vivado/vpl/vivado.log
newest_activity=.../build/link/link/vivado/vpl/vivado.pb
idle_seconds=2
idle_warning=none
current command: route_design
```

Routing progress:

```text
[05:35:33] Starting logic routing..
[05:47:53] Phase 5 Rip-up And Reroute
[05:47:53] Phase 5.1 Global Iteration 0
[06:12:35] Phase 5.2 Global Iteration 1
[06:16:11] Phase 5.3 Global Iteration 2
[06:19:47] Phase 5.4 Global Iteration 3
[06:23:54] Phase 5.5 Global Iteration 4
```

Current intermediate route timing:

```text
WNS moved through:
  -0.642
  -0.426
  -0.356
  -0.232
latest TNS=-66.504
```

Interpretation:

```text
The build is still active and not idle. Route is making forward progress and
WNS has improved since earlier route iterations, but the design still has
negative route timing and known congestion/SLL/bus-skew warnings. No action
needed yet; continue monitoring until route completion, timing failure, or
xclbin emission.
```
