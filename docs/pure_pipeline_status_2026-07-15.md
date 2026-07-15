# Pure Pipeline Status Snapshot

Date: 2026-07-15 Asia/Shanghai

Status command input tree, after enforcing hardware artifact manifests in the
claim checker:

```text
/home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head: 36b7915c86058a7a94bdf4d8491c4ad1e33178ea
source_fingerprint_sha256: f9c469e47e0a938a15991b39aac23d7b0170cb7ab1ab08e29f39937f2887dbba
dirty: false
```

Documentation-only commits do not change the build-relevant source fingerprint
used by `report_pure_pipeline_next_steps.py`.

Postbuild helper/report update:

```text
helper commit: 782ce71b6e0568de4baf564366e3e582083c9ddb
report command commit: 901b3ee6ccd22a1e0b06c5642d3827cfcebfdc4d
timing acceptance commit: 454840eac185d19ade146fbd426f462666f1eb54
claim-status report commit: ff4ea014dc2447814ff071a4ad0fc5eef5852b0a
postbuild-context commit: d5302c466db75c9b38c3ee77f5b8c830840c8ecd
claim-checker commit: 349c191640a84992d92fa36f63ad785021f4bf31
postbuild-claim-chain commit: a8d976460110fbb9e1e1c6555a82b047141c51f6
next-step-claim-wording commit: 79d2063d527529d363836e6bb8caa8a7f2525d13
artifact-manifest commit: c2be2b74fb64d3fe767bfb4ee7e9d65d1705c624
artifact-manifest claim-enforcement commit: df02afa5d79b4116fe1a22468c148f8a460b6d46
artifact-manifest audit commit: 2f461025969a679ffaa9310a81d73216966efecb
postbuild label guard commit: 238d3100ba22a0bfef27d894942fdf4dacaf445c
postbuild label source-contract commit: 36b7915c86058a7a94bdf4d8491c4ad1e33178ea
source_fingerprint_sha256: f9c469e47e0a938a15991b39aac23d7b0170cb7ab1ab08e29f39937f2887dbba
new helper: scripts/wait_for_pure_pipeline_xclbin_then_accept.py
new helper: scripts/check_pure_pipeline_claim.py
new helper: scripts/collect_pure_pipeline_artifact_manifest.py
report block: postbuild_wait
report block: claim_status
claim checker: exits 0 only when selected build/gate/full/completion claim is proven
postbuild wrappers: print source fingerprint, launch packet, and claim-status gaps before acceptance, then write an artifact manifest and run final claim validation
hardware claim rule: hw_emu/hw build/gate/full claims require a passing artifact manifest at the selected or stronger proof level
requirement audit rule: audit.json embeds the current claim report and lists missing_artifact_manifest_claims
postbuild label rule: real postbuild/wait runs fail early if --label does not match the target's current launch packet label; this is now a required source-contract proof
timing gate: same-input comparison must contain pure_grasu_ms, pure_barrier_ms, pure_adapter_ms, pure_lksg_ms, pure_apply_ms, and pure_event_e2e_ms
hw_emu xclbin: available through containerized 22.04 link
hw xclbin: available from direct after_f1c6720 build
```

This snapshot answers the narrow build-status question first: pure-pipeline
`hw_emu` and `hw` xclbins now both exist. The `hw` artifact is a successful
build/link artifact; real U55C runtime correctness and performance are still
pending.

## Target State

```text
target    xclbin  status
sw_emu    yes     stage0 gate already passed
hw_emu    yes     xclbin linked in Ubuntu 22.04 container; runtime started, gate not passed yet
hw        yes     xclbin linked; U55C runtime gate pending
```

Current `sw_emu` artifact:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
sha256: b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
```

## hw_emu Container Link Milestone

The direct host `hw_emu` link failed at `config_hw_emu.elaborate` while xsim
linked `libdpi.so`: Vivado 2024.1's bundled binutils 2.37 could not read the
host Debian glibc 2.42 `libm.so.6` / `libmvec.so.1` `.relr.dyn` sections.
The prior ReGraph report's `vivado-runner:22.04-feiyang` image avoids this
because it uses Ubuntu glibc 2.35 and its `libm.so.6` has no `.relr.dyn`.

Successful command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_hwemu_container22.sh \
  --label container22_after_038c87a
```

The wrapper preserved the existing 12 `hw_emu` `.xo` files, removed only the
old `hw_emu` link temp/log/report directories, and then ran
`scripts/run_pure_pipeline_build.sh --target hw_emu --skip-compile` inside
`vivado-runner:22.04-feiyang` with UID/GID `2009:2010`, host-network,
udev/sysfs/machine-id mounts, the original `/data/yxx/tools/xilinx` path, and
a WebTalk settings bind mount.

Successful output:

```text
xclbin: .tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin
sha256: 1ff806f1e74c89c53466831f59bd9e18a0dd4b7399eb3807ba7d798c93527762
size:   119382259 bytes
elapsed: 0h 10m 57s
```

Key proof lines:

```text
vivado.log: Done linking: "libdpi.so"
link log:   Run vpl: Step config_hw_emu.elaborate: Completed
link log:   Run Status: config_hw_emu.elaborate Complete!
link log:   Created .../grasu_regraph_pure_pipeline.hw_emu.xclbin
```

Evidence paths:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_container22_after_038c87a.env
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_container22_after_038c87a_evidence.tsv
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/link_container22_after_038c87a.log
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin.link_summary
target/container_logs/hw_emu_container22_after_038c87a.outer.log
```

The warnings that remain are platform/IP-lock and SLR locality warnings. They
did not block `hw_emu` xclbin generation. This milestone proves link/build
success only; `hw_emu` runtime correctness for chain, hot-source, spread, and
hot-destination still needs to be run against the CPU oracle.

## hw Build Milestone

The direct `hw` build for the same pure pipeline completed successfully and
created the real U55C xclbin.

Build command shape:

```bash
cd /home/chuxiao/grasu-regraph-integration
nohup ./scripts/run_pure_pipeline_build.sh \
  --target hw \
  --label after_f1c6720_direct \
  --prepare \
  --clean-build-artifacts \
  > .tmp_build/pure_pipeline_hw_stage0/run_logs/manual_hw_after_f1c6720_direct.nohup.log 2>&1 &
```

Successful output:

```text
xclbin: .tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin
sha256: d91a015a64d26100e93ae1867d34ec01dfe8e4dfe73c62de525e94d1a64b9a37
size:   74710265 bytes
created: 2026-07-15 19:41:55 +0800
v++ elapsed: 4h 0m 30s
```

Key proof lines:

```text
Run vpl: FINISHED. Run Status: impl Complete!
Vivado: Bitgen Completed Successfully.
Vivado: write_bitstream completed successfully.
xclbinutil: Successfully wrote (74710265 bytes) to .../grasu_regraph_pure_pipeline.hw.xclbin
v++: Created .../grasu_regraph_pure_pipeline.hw.xclbin
v++: Run completed.
```

Clock and timing notes from the link log:

```text
kernel DATA clock: requested 200 MHz, selected 197 MHz
system HBM clock: requested 450 MHz, selected 430 MHz
Vivado reported a timing critical warning, then auto-frequency scaling enabled proper functionality.
```

Important evidence paths:

```text
.tmp_build/pure_pipeline_hw_stage0/run_logs/build_after_f1c6720_direct.env
.tmp_build/pure_pipeline_hw_stage0/run_logs/build_after_f1c6720_direct_evidence.tsv
.tmp_build/pure_pipeline_hw_stage0/run_logs/compile_after_f1c6720_direct.log
.tmp_build/pure_pipeline_hw_stage0/run_logs/link_after_f1c6720_direct.log
.tmp_build/pure_pipeline_hw_stage0/run_logs/manual_hw_after_f1c6720_direct.nohup.log
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin.info
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin.link_summary
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.ltx
.tmp_build/pure_pipeline_hw_stage0/logs/link/link/vivado.log
.tmp_build/pure_pipeline_hw_stage0/reports/link/link/imp/impl_1_hw_bb_locked_timing_summary_routed.rpt
results/pure_pipeline_hw_artifact_manifest_after_f1c6720_build/artifact_manifest.tsv
```

The build-level artifact manifest binds the `hw` xclbin to the launch packet
and hashes the available build artifacts. Its target/build rows pass; postrun
rows are still missing because real U55C runtime acceptance has not been run.

The xclbin metadata lists the expected pure-pipeline kernels:

```text
lksg_stream, kernelHBMWrapper, kernelApply, pma_to_regraph_adapter,
dispatch, process_cache, kernelLittleGSMerger, kernelBigGSMerger,
bin_search, bigKernelScatterGather, process_ddr, pma_completion_barrier
```

This milestone proves hardware build/link success. It does not prove U55C
runtime correctness yet.

## hw_emu Runtime Partial Evidence

The freshly linked `hw_emu` xclbin was used for a same-input stage0 gate run:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw_emu \
  --mode gate \
  --label container22_after_038c87a_runtime_gate \
  --baseline-label after_64ba9c3 \
  --xclbin /home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin \
  --require-compare \
  --timeout 1200
```

The run was stopped after collecting enough evidence. Current partial results:

```text
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/summary.tsv

tiny_chain_v16:
  status: FAIL
  exit_code: 124
  reason: per-case timeout at 1200s, not a CPU-oracle mismatch
  last observed stage: wait_step step=8 of 16

tiny_star_v16_u12:
  status: manually interrupted during evidence collection
  last observed stage: PURE_PIPELINE_HOST stage=launch_grasu
```

The chain case proves that `hw_emu` runtime can load the xclbin, configure ERT
dataflow, launch the GraSU/barrier/adapter/ReGraph/apply sequence, and advance
multiple SSSP supersteps. It does not prove gate correctness because the case
timed out before all 16 supersteps completed. The star case shows that the
update-heavy GraSU PMA path is very slow in `hw_emu`; it had not passed
`launch_grasu` when the run was stopped.

Important evidence paths:

```text
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/run.env
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/postbuild_matrix.env
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/summary.tsv
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/tiny_chain_v16.log
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/tiny_chain_v16/case.env
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/tiny_star_v16_u12.log
results/pure_pipeline_hw_emu_pure_stage0_gate_container22_after_038c87a_runtime_gate/tiny_star_v16_u12/case.env
results/pure_stage0_comparison_plan_container22_after_038c87a_runtime_gate/input_identity.tsv
```

Current `sw_emu` postrun evidence was refreshed without rebuilding the xclbin:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target sw_emu \
  --label postrun_after_c29ee70 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 180
```

The postrun acceptance check passed with `PASS=11, SKIP=2`. The four smoke
families all matched the CPU oracle:

```text
tiny_chain_v16        chain       PASS mismatches=0
tiny_star_v16_u12     hot-source  PASS mismatches=0
tiny_spread_v16_u8    spread      PASS mismatches=0
tiny_hotdst_v64_u32   hot-dest    PASS mismatches=0
```

Refreshed `sw_emu` evidence hashes:

```text
source contracts:      fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
source fingerprints:   af30985c9a0c04eed67553eefbd57c66768d3aa93f842202c83086f99bebbee1
readiness report:      fed5f4aeae67f5e479c2cbf36a81c6ec8a664b269bc8ce7a4cdc3ef5746c18fc
smoke summary:         c90ca527818c253472959e7f59c00cc93715dd68f414accbfed504ac50e7e09c
same-input comparison: 7939f3ac4b3d89b46d21970dd1ead5b451577e68d050ee5f220120a85b493f8e
requirement audit:     45421ba7337a5a6cd91e50d893478d251779dfee6f9b59ff6c13ec13c7dac15c
evidence bundle:       3c3500cdb34d06b0bc552b3802f07a29b14669d5f2ec39c69bb7e224855787b0
postrun acceptance:    238b935262a4ba49b438de2d873cfc11f0d440c8f0f9c977bd6a2f43ebb1378b
xclbin contract:       1cc3d8e5ad44862262cbb1294a3b0b6b0a685bf49aefb132325dad28060adcd3
```

Current `sw_emu` pure_stage0 gate evidence was also refreshed against the
`after_64ba9c3` host/Spine baseline inputs:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target sw_emu \
  --mode gate \
  --label after_c29ee70 \
  --baseline-label after_64ba9c3 \
  --require-compare \
  --timeout 600
```

The gate covers the four required families and passed the input-identity audit
with `checks=80 failures=0`:

```text
tiny_chain_v16        chain       PASS mismatches=0
tiny_star_v16_u12     hot-source  PASS mismatches=0
tiny_spread_v16_u8    spread      PASS mismatches=0
tiny_hotdst_v64_u32   hot-dest    PASS mismatches=0
```

Refreshed `sw_emu` stage0 gate hashes:

```text
comparison plan:       50b90d87170b114f0e2c05511ec73a8fb3a0d94ab9e0d70b8ecf0e092ac9e4fd
input identity plan:   fd4a690c32bf7fc6d5f0c1264c575b79157f63ddfe21d65abe063749e5a0940b
gate summary:          29be3bd70d24723c550e4900523c23770a660bfbd79baa43b4f791baa8a1bb40
identity audit:        a24e9eea9e280b691c25644ae443f53f6f5826e5ea12e70c31dbcc02045169fd
same-input comparison: a8754cdc6a457bc76547cb755b8d82b04761bda99704d8cedaf69597a8603e78
postbuild env:         918e25919dfedf3042671095456b1fc79742f834ecd489512c66695f8b586029
```

## sw_emu Full Matrix Attempt After f461c07

The existing `sw_emu` xclbin was also used for a full 12-case
`pure_stage0` matrix attempt. This did not rebuild the xclbin:

```text
repo=/home/chuxiao/grasu-regraph-integration
branch=codex/pure-hw-pipeline
head_before_this_doc_update=2810eba83723283ad3ee047cc213ea0d91da8cfb
source_fingerprint_sha256=86d6692740c28cece89ddcb6b80a206b435f51cf8e4398ff2ae668bae63ee9a2
```

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target sw_emu \
  --mode full \
  --label after_f461c07 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

The smoke phase exited non-zero because one case timed out, but the script
continued across the full manifest and produced a useful partial-full evidence
set:

```text
rows=12
PASS=11
FAIL=1
failure=large_chain_v4096 exit_code=124 status=FAIL
```

The failed case is the deep `large_chain_v4096` workload: 4096 vertices,
4095 final edges, and 4096 SSSP supersteps. Under `sw_emu` plus verbose kernel
debug, it hit the per-case 600 second timeout before it could finish. This is
not accepted as a full pass and keeps `sw_emu` `stage0_full=fail`.

The other 11 cases matched the CPU oracle with `mismatches=0`, including the
three `V=65536` review/boundary cases:

```text
medium_star_v65536_u8192        hot-source  PASS vertices=65536 updates=8192  supersteps=2
medium_spread_v65536_u16384     spread      PASS vertices=65536 updates=16384 supersteps=32
boundary_hotdst_v65536_u4096    hot-dest    PASS vertices=65536 updates=4096  supersteps=64
```

After the run, the identity and comparison reports were generated without
rerunning kernels:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target sw_emu \
  --mode full \
  --label after_f461c07 \
  --baseline-label after_64ba9c3 \
  --require-compare \
  --skip-run
```

The same-input audit passed:

```text
checks=240 failures=0
```

Full-attempt evidence hashes:

```text
summary:              a644784ae48582f36c456bee2c17defbe86da8bafd31c192175f12a76ef93d65
run env:              bf64bba0fedc9fd534c2d0dd509d1c08a996295338ff3d131d7deb4c6dc95626
postbuild env:        e513fd6480ba01590a69ac57adf10baf2daff9f5af2cd66ae08fa7d59bd7515f
identity audit:       cbfccccda37d81897ff6bebdcfaeb0381dc317246def257feb010c83194bbf1c
same-input tsv:       d40750727c5df0d103dbb31e1b51087861f1eee333af80dacc126e8efeb65d1c
same-input md:        79d1975d59c998a1f007c0ea921b9c6976cddc439aee325d0c468bf5209cd97f
comparison run env:   88924535ac9a47ba87c0f768c465300c4f6f12ab620fc4d8ab67ddc134fd1894
input identity plan:  fd4a690c32bf7fc6d5f0c1264c575b79157f63ddfe21d65abe063749e5a0940b
comparison plan:      05156ed3f348429d837a62e965f889495659de294db18dc333e2544da2ed7688
plan summary:         392f052bd3218bf8f6c6efb9c01c0e71575770e4d3fa234a673d4dcc30c710e3
plan run env:         c267fd5c2bd2297f3b8b0daa9de698a88f27fca9998f90ff8d17017010f3d105
```

Important paths:

```text
results/pure_pipeline_sw_emu_pure_stage0_full_after_f461c07/summary.tsv
results/pure_pipeline_sw_emu_pure_stage0_full_after_f461c07/large_chain_v4096.log
results/pure_pipeline_sw_emu_pure_stage0_identity_full_after_f461c07/input_identity_check.tsv
results/pure_pipeline_sw_emu_pure_stage0_compare_after_f461c07/comparison.tsv
results/pure_pipeline_sw_emu_pure_stage0_compare_after_f461c07/comparison.md
```

This strengthens `sw_emu` large-case correctness evidence only. It does not
change the final completion status: `hw_emu_gate`, `hw_gate`, and `hw_full`
are still missing.

Follow-up tooling change: `scripts/run_pure_pipeline_smoke.sh` and
`scripts/run_pure_stage0_postbuild_matrix.sh` now support per-case timeouts
with repeated `--case-timeout CASE=SECONDS`. Use this to retry only slow
deep-propagation workloads without inflating every shallow case timeout. For
example, a `sw_emu` full retry that gives the deep chain more room is:

```bash
cd /home/chuxiao/grasu-regraph-integration
LABEL="after_$(git rev-parse --short HEAD)_longchain"
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target sw_emu \
  --mode full \
  --label "${LABEL}" \
  --baseline-label after_64ba9c3 \
  --require-compare \
  --case-timeout large_chain_v4096=7200
```

The timeout overrides are recorded in `postbuild_matrix.env` and per-case
`case.env` files, so a long-chain retry remains reproducible.

The current requirement audit and evidence bundle were refreshed by the
`sw_emu` postrun command above at commit
`c29ee70c5aa3cffd1d5e4701434dcf5a919b8534`:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/audit_pure_pipeline_status.py \
  --label postrun_after_c29ee70 \
  --out-dir results/pure_pipeline_requirement_audit_postrun_after_c29ee70
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_postrun_after_c29ee70/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_postrun_after_c29ee70
```

The target-flow wrapper ran these steps sequentially after smoke and comparison
completed.

```text
requirement audit json: 45421ba7337a5a6cd91e50d893478d251779dfee6f9b59ff6c13ec13c7dac15c
evidence manifest:      3c3500cdb34d06b0bc552b3802f07a29b14669d5f2ec39c69bb7e224855787b0
evidence summary:       5711d5eace7467e506124031550fb705c1d72d2c06d4cd1519003085a1659206
status counts:          blocked_by_missing_artifact=1, partial=8, proven=1
completion summary:     all_requirements_proven=false; missing_xclbin_targets=hw_emu,hw; missing_stage0_gate_targets=hw_emu,hw; missing_stage0_full_targets=sw_emu,hw_emu,hw
```

Missing artifacts:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin
```

## Latest Read-Only Status Command

Regenerate this status without starting Vitis:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/report_pure_pipeline_next_steps.py
```

The report has one claim section and five command sections:

```text
claim_status       direct build/gate/full claimability and missing evidence
next_commands       immediate build or postrun action
postbuild_acceptance
                    guarded wrapper commands to run after a target xclbin exists
postbuild_wait      wait-for-xclbin wrappers that run guarded acceptance automatically
postrun_followup    skip-build validation to run after a manually produced xclbin exists
stage0_followup     same-input stage0 matrix commands after postrun acceptance passes
```

The target table also reports `stage0_gate` and `stage0_full`. `stage0_gate`
means the four required smoke families have passed the same-input matrix for
that target; `stage0_full` is reserved for the full tracked stage-0 matrix.
The `claim_status` block answers whether the current evidence is strong enough
to claim the target as built, gate-validated, or fully validated.

Observed result for this snapshot:

```text
sw_emu: xclbin=yes, flow_current=no, packet_current=no,  postrun=pass:PASS=11,SKIP=2, stage0_gate=pass,    stage0_full=fail
hw_emu: xclbin=no,  flow_current=no, packet_current=yes, postrun=waiting_xclbin,        stage0_gate=missing, stage0_full=missing, artifact_manifests=build:missing,gate:missing,full:missing
hw:     xclbin=no,  flow_current=no, packet_current=yes, postrun=waiting_xclbin,        stage0_gate=missing, stage0_full=missing, artifact_manifests=build:missing,gate:missing,full:missing
completion claimable=no; missing=hw_emu_gate,hw_gate,hw_full
active_builders=related:0 external:10
```

The active builders are external Vitis/Vivado processes and are not classified
as this integration repository's pure-pipeline build.

## Next Build Command

The next required long command is the current `hw_emu` launch packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_f1c6720/launch_command.sh
```

The launch packet matches the current build-relevant source fingerprints. It
records source contracts, source fingerprints, prelaunch acceptance gates,
artifact hashes, the exact target-flow command it will execute, and packet-local
post-build helper scripts for acceptance after the xclbin appears.

The packets were regenerated with:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh --target hw_emu --allow-active-builders
./scripts/create_pure_pipeline_launch_packet.sh --target hw --allow-active-builders
```

Current build-relevant source fingerprint:

```text
d557efd41f44947798a5f204210ed6267bdcf1df9d66c786e51eacd744df3e43
```

Current launch-packet hashes:

```text
hw_emu launch_command.sh:            d26ffc93c5f9f380f8fee538281ca267ca0be9b94a2b8902ad9581b724f334c5
hw_emu postbuild_acceptance_gate.sh: 37f7ad63136116f7b61e6442502995011dd58d2eb487431448fe0369b405e773
hw_emu wait_then_accept_gate.sh:     e809a195b3bb2b1d3a439124ed694fd29caf0c2ba7133fc39bec3648404a5786
hw_emu postbuild_acceptance_full.sh: 9ace0d4b07bbde6a1c1c62414504eca6d807ae33efa2cd73ebc4a74328422baf
hw_emu wait_then_accept_full.sh:     f938e1fd80d843409e16f3a2b89457a9038d583e0eedabb2a5908e0491adb51b
hw_emu source_contracts.tsv:         48ed2c7c0adac3c7667369dacb3edb62e225d67247ed40fe420f9016fb1eaf56
hw_emu source_fingerprints.tsv:      4b9c46af585c0e61f24da1c5d9faa737522266261899cc678ddc4243117459c6
hw_emu readiness_hw_emu.txt:         c076a74f3eef684a704c8e2628b1226e4a1dfd65fb4840ac12d697ed032e302c
hw_emu acceptance_check_prelaunch:   11edc65d22f0e8a93f249db35bd89ef4bb79b30afc758701fc0c92ec1eef86a1
hw_emu packet audit:                 daabda325663eeba78a69c96d75fa6ef5d7897e947491a7da6b2fa850252c96b
hw_emu packet evidence bundle:       7aae70c8fc9599c26599ceee6e1f0cec43d9571768237af18f6169f7a3ba712d

hw launch_command.sh:                e3eff63d1771dde8f85e34903dad9a4966fad70c0008f12e09a16f4c023b9c85
hw postbuild_acceptance_gate.sh:     00b7ecac7efee0ac2dbd572e226b1901cf262a4d8f4c0e52d6fd35df5416c26d
hw wait_then_accept_gate.sh:         03809e17486a6cd4e8651e5376ea5c57d84e47e09ba89f1ed4e40fad016fa3e6
hw postbuild_acceptance_full.sh:     a6429d7c8067b98ea2d5834bb97fca0ac1cdeec82cab61015b40182e81a65af5
hw wait_then_accept_full.sh:         2e3284ef171b297ee05ab616f96cf96ca6a517cf8da0c355d9a3d0bc8363d75b
hw source_contracts.tsv:             48ed2c7c0adac3c7667369dacb3edb62e225d67247ed40fe420f9016fb1eaf56
hw source_fingerprints.tsv:          4b9c46af585c0e61f24da1c5d9faa737522266261899cc678ddc4243117459c6
hw readiness_hw.txt:                 195f0daeea5108a2c0ade70b27df4657fc2e44a9f8f8dc4e6903d187d3de8594
hw acceptance_check_prelaunch:       6eb7a990a18c82170d465db4255a162dbf5a08f342038e51079c82e78a492db1
hw packet audit:                     49a06478fc8b492e4da9490793ed38280fcfccc87383ff8bf6f077367a3f3c1a
hw packet evidence bundle:           88fc489d9ced384560d8d74f5c8ebf291b57fa34e3ee0ca0dc912d8057fe1be6
```

Current prebuild snapshot hashes:

```text
hw_emu next_steps.json:             f9d8146186f90f70bf3e6b8b8ec7e76529636a06068bbd0338b797d2d67002f4
hw_emu claim_status.tsv:            ac43cdce1b362f5d9b14f3232104c6dbab25940ee2449deaae716e439574121d
hw_emu artifact_manifest_allow_missing: 1fed2c5527d3a720810b8c743ab4fe410dde7be89beb4500e0cfc54c269b9b0f
hw_emu snapshot_artifacts.tsv:      4eff9382e790dad41e9efe0b8f512e7f4c94198f462c5120fc43fc181a0a7e27

hw next_steps.json:                 f9d8146186f90f70bf3e6b8b8ec7e76529636a06068bbd0338b797d2d67002f4
hw claim_status.tsv:                49999c07d69b7f81fc969105fe4a1f0b570b7db5f98e3eeb002a1c11412d3bed
hw artifact_manifest_allow_missing: 6be1534a228d62d8696a75c87c18b41ecbae6e6dd48bedcfaaaa4492e6b6f9c6
hw snapshot_artifacts.tsv:          3af552a80407e4631c02fe3178510c356d6b407d4d055c42c52eb932bf3b47cb
```

Because external Vitis/Vivado builders are active, these packets were generated
with `--allow-active-builders`. The target-flow launch command still includes
the wait-idle guard.

If an xclbin is produced outside the target flow, the guarded wrapper runs
skip-build postrun validation, then the same-input stage0 matrix, then an
artifact manifest, then final claim validation for the requested proof level:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_postbuild_acceptance.py \
  --target hw_emu \
  --label after_f1c6720 \
  --baseline-label after_64ba9c3 \
  --mode gate
```

If the long `hw_emu` or `hw` build is already running elsewhere, the wait helper
can watch for the expected xclbin and then run the same guarded acceptance
sequence. It does not launch Vitis:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py \
  --target hw_emu \
  --label after_f1c6720 \
  --baseline-label after_64ba9c3 \
  --mode gate

./scripts/wait_for_pure_pipeline_xclbin_then_accept.py \
  --target hw \
  --label after_f1c6720 \
  --baseline-label after_64ba9c3 \
  --mode gate
```

Equivalent packet-local helper scripts:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_f1c6720/wait_then_accept_gate.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_f1c6720/wait_then_accept_gate.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_f1c6720/wait_then_accept_full.sh
```

Equivalent low-level postrun validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label postrun_after_f1c6720 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label postrun_after_f1c6720 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

After `hw_emu` exists and postrun acceptance passes, run:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw_emu \
  --mode gate \
  --label after_f1c6720 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_f1c6720 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_f1c6720 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

## Latest Script Validation

The comparison-report path now has a regression test that covers missing
pure-pipeline rows. This prevents an absent `hw_emu` or `hw` row from being
reported as if it had real mismatches or `sw_emu` timing. The smoke-comparison
path now also emits `pure_barrier_ms`, and the postrun acceptance checker
requires all split pure-pipeline timing fields. The next-step report also has
a claim-status regression check so a target cannot be described as build,
gate, or full proven until the required evidence is present. The postbuild and
wait helpers now print source fingerprint, launch packet, and claim-status
context in their dry-run and real acceptance logs. The postbuild wrapper also
appends `collect_pure_pipeline_artifact_manifest.py` and
`check_pure_pipeline_claim.py`, so a postbuild run records the exact xclbin,
launch packet, postrun artifacts, stage0 artifacts, and baseline artifacts
before ending with a direct build/gate/full proof check.
`check_pure_pipeline_claim.py` turns those claim states into an exit code for
scripts and CI-style gates.

The `df02afa` update adds a regression check that hardware claims require a
passing artifact manifest. `hw_emu` and `hw` now report
`artifact_manifest_build`, `artifact_manifest_gate`, or
`artifact_manifest_full` as missing evidence until postbuild acceptance writes
a complete manifest for the selected proof level.

The `2f46102` update makes the requirement audit consume the same next-step
claim report, so `audit.json`, the evidence bundle, and the human-readable audit
all show the same missing hardware artifact-manifest claims as
`check_pure_pipeline_claim.py`.

The `238d310` update adds a postbuild label guard. Real postbuild acceptance
and wait-helper runs now fail early when the requested `--label` does not match
the target's current launch packet label; dry-run keeps this as a warning so the
commands can still be inspected.

The `36b7915` update promotes that guard into the required source-contract set;
launch packets now report `required_count=18` and require
`postbuild_label_guard ok=yes`.

The `091b5a4` update adds packet-local post-build helper scripts to each fresh
`hw_emu`/`hw` launch packet. The packet now writes and hashes
`postbuild_acceptance_gate.sh`, `wait_then_accept_gate.sh`,
`postbuild_acceptance_full.sh`, and `wait_then_accept_full.sh`; it also records
the pinned `baseline_label` and helper paths in `launch_packet.env`.

The `f461c07` update makes those helper scripts first-class evidence:
`report_pure_pipeline_next_steps.py` prints a `packet_local_helpers` section,
and `collect_pure_pipeline_artifact_manifest.py` records all four helper
scripts as required hashed launch-packet artifacts for `hw_emu` and `hw`.

The `b0c8aa0` update tightens artifact-manifest acceptance. A hardware manifest
is no longer considered passing just because required rows say `exists=yes`;
the report now verifies the expected required row set, recorded hash and size
against current files, the canonical pure-pipeline xclbin path, launch-packet
target/label, and source-fingerprint freshness. A stale, truncated, retargeted,
or tampered manifest therefore keeps `artifact_manifest_build/gate/full` in the
missing evidence list.

The `2a31b41` update closes the stage0 comparison timing gate. After a
postbuild matrix comparison is generated, `run_pure_stage0_postbuild_matrix.sh`
now writes `acceptance_gates_stage0_<mode>.tsv` and runs
`check_pure_pipeline_acceptance_gates.py` to require the four gate families,
PASS status, zero mismatches, and split pure-pipeline timing fields. The
artifact manifest records both the stage0 gate spec and check result as
required artifacts for gate/full claims, and manifest integrity fails if the
recorded acceptance check contains a required non-PASS gate.

The `b201b60` update promotes that stage0 comparison gate into the required
source-contract set. Fresh launch packets now report `required_count=19`, and
both `hw_emu` and `hw` prelaunch checks require
`stage0_comparison_acceptance_gate ok=yes` before any long Vitis build starts.

The `f1c6720` update adds `collect_pure_pipeline_prebuild_snapshot.py`. The
snapshot records next-step JSON/text, target claim gaps, an allow-missing
artifact manifest, and snapshot artifact hashes without launching Vitis. The
fresh `after_f1c6720` `hw_emu` and `hw` snapshots both have
`snapshot_required_missing_count=0`; their manifest missing rows are the
expected xclbin/postrun/stage0 evidence that can only exist after the long
build and postbuild acceptance.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/create_pure_pipeline_launch_packet.sh scripts/run_pure_pipeline_target_flow.sh scripts/run_pure_stage0_postbuild_matrix.sh scripts/refresh_pure_pipeline_readiness_bundle.sh
python3 tests/test_wait_for_pure_pipeline_xclbin_then_accept.py
python3 tests/test_run_pure_pipeline_postbuild_acceptance.py
python3 tests/test_collect_pure_pipeline_artifact_manifest.py
python3 tests/test_check_pure_pipeline_claim.py
python3 tests/test_report_pure_pipeline_next_steps.py
python3 tests/test_check_pure_pipeline_acceptance_gates.py
python3 tests/test_summarize_pure_pipeline_smoke.py
python3 tests/test_audit_pure_pipeline_status.py
python3 tests/test_summarize_pure_stage0_comparison.py
python3 tests/test_summarize_canonical_comparison.py
python3 -m py_compile scripts/audit_pure_pipeline_status.py scripts/run_pure_pipeline_postbuild_acceptance.py scripts/wait_for_pure_pipeline_xclbin_then_accept.py scripts/check_pure_pipeline_claim.py scripts/collect_pure_pipeline_artifact_manifest.py scripts/report_pure_pipeline_next_steps.py scripts/summarize_pure_stage0_comparison.py scripts/check_pure_pipeline_acceptance_gates.py scripts/summarize_pure_pipeline_smoke.py
./scripts/report_pure_pipeline_next_steps.py --json > .tmp_build/report_next_steps_stage0_columns.json
python3 -m json.tool .tmp_build/report_next_steps_stage0_columns.json >/dev/null
./scripts/report_pure_pipeline_next_steps.py --json > .tmp_build/report_next_steps_claim_status.json
python3 -m json.tool .tmp_build/report_next_steps_claim_status.json >/dev/null
set +e
./scripts/check_pure_pipeline_claim.py --level completion
echo completion_rc=$?
./scripts/check_pure_pipeline_claim.py --target hw --level build
echo hw_build_rc=$?
./scripts/check_pure_pipeline_claim.py --target sw_emu --level gate
echo swemu_gate_rc=$?
set -e
python3 scripts/summarize_pure_pipeline_smoke.py --host-summary results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv --pure-summary results/pure_pipeline_sw_emu_smoke_postrun_after_c29ee70/summary.tsv --pure-env results/pure_pipeline_sw_emu_smoke_postrun_after_c29ee70/run.env --spine-summary results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv --out-dir .tmp_build/pure_pipeline_sw_emu_compare_postrun_after_c29ee70_timing_gate
./scripts/check_pure_pipeline_acceptance_gates.py --acceptance-gates .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/acceptance_gates_target_flow_postrun_after_c29ee70.tsv --mode postrun --out-file .tmp_build/acceptance_check_swemu_new_timing_gate.tsv
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw_emu --dry-run --allow-missing-xclbin
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py --target hw_emu --dry-run
./scripts/audit_pure_pipeline_status.py --label audit_manifest_claim_$(git rev-parse --short HEAD) --out-dir .tmp_build/audit_manifest_claim_$(git rev-parse --short HEAD)
./scripts/check_pure_pipeline_source_contracts.py --label contract_label_guard_$(git rev-parse --short HEAD) --out-file .tmp_build/source_contracts_label_guard.tsv
./scripts/check_pure_pipeline_source_contracts.py --label packet_helpers_verify --out-file .tmp_build/source_contracts_packet_helpers_verify.tsv
./scripts/collect_pure_pipeline_artifact_manifest.py --target hw_emu --label after_f1c6720 --baseline-label after_64ba9c3 --mode gate --level gate --out-file .tmp_build/artifact_manifest_hwemu_after_f1c6720_allow_missing.tsv --allow-missing-required
./scripts/create_pure_pipeline_launch_packet.sh --target hw_emu --flow-label after_f1c6720 --allow-active-builders
./scripts/create_pure_pipeline_launch_packet.sh --target hw --flow-label after_f1c6720 --allow-active-builders
./scripts/collect_pure_pipeline_prebuild_snapshot.py --target hw_emu --label after_f1c6720 --baseline-label after_64ba9c3 --mode gate --level gate
./scripts/collect_pure_pipeline_prebuild_snapshot.py --target hw --label after_f1c6720 --baseline-label after_64ba9c3 --mode gate --level gate
bash -n .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_f1c6720/postbuild_acceptance_gate.sh .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_f1c6720/wait_then_accept_gate.sh
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py --target hw_emu --label after_f1c6720 --baseline-label after_64ba9c3 --mode gate --dry-run
set +e
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw_emu --label wrong_label --allow-missing-xclbin
echo label_mismatch_rc=$?
set -e
git diff --check
```

Result:

```text
test_wait_for_pure_pipeline_xclbin_then_accept PASS
test_run_pure_pipeline_postbuild_acceptance PASS
test_collect_pure_pipeline_artifact_manifest PASS
test_check_pure_pipeline_claim PASS
test_report_pure_pipeline_next_steps PASS
test_audit_pure_pipeline_status PASS
test_check_pure_pipeline_acceptance_gates PASS
test_summarize_pure_pipeline_smoke PASS
test_summarize_pure_stage0_comparison PASS
test_summarize_canonical_comparison PASS
report_pure_pipeline_next_steps JSON validation PASS
report_pure_pipeline_next_steps claim-status JSON validation PASS
check_pure_pipeline_claim completion rc=1, hw build rc=1, sw_emu gate rc=0
smoke comparison timing-gate regeneration PASS
acceptance_check_swemu_new_timing_gate PASS=11, SKIP=2
postbuild_acceptance hw_emu dry-run PASS; command sequence includes collect_pure_pipeline_artifact_manifest.py before check_pure_pipeline_claim.py --target hw_emu --level gate
wait_for_pure_pipeline_xclbin_then_accept hw_emu dry-run PASS
artifact manifest hw_emu allow-missing sample PASS with required_missing_count=20 before hw_emu xclbin exists; new missing stage0 evidence includes acceptance_gates and acceptance_check
claim-status manifest regression PASS; hw_emu/hw missing evidence now includes artifact_manifest_build/gate/full until a passing manifest is present
artifact manifest integrity regression PASS; tampering a recorded xclbin produces sha256_mismatch:target:xclbin and a truncated manifest produces manifest_missing_row findings
stage0 comparison acceptance regression PASS; postbuild matrix dry-run emits check_pure_pipeline_acceptance_gates.py and records stage0_acceptance_gates/check paths
stage0 manifest acceptance regression PASS; gate/full manifests require stage0 acceptance_gates and acceptance_check, and required non-PASS stage0 acceptance checks fail manifest integrity
requirement audit manifest regression PASS; completion_summary.missing_artifact_manifest_claims=hw_emu:build,hw_emu:gate,hw_emu:full,hw:build,hw:gate,hw:full
postbuild label guard PASS; wrong label exits rc=2 before xclbin/postbuild work
source-contract label guard PASS; required_count=19 and postbuild_label_guard ok=yes
source-contract stage0 comparison gate PASS; required_count=19 and stage0_comparison_acceptance_gate ok=yes
source-contract packet helper proof PASS; launch_packet_records_acceptance_gates still ok=yes after helper addition
launch packet helper generation PASS; hw_emu/hw packets for after_f1c6720 include postbuild/wait gate and full helpers, all hashed in artifact_hashes.tsv
next-step report helper visibility PASS; packet_local_helpers lists four helpers for hw_emu and four helpers for hw
artifact manifest helper evidence PASS; hw_emu allow-missing manifest records all four packet-local helper scripts as required PASS artifacts
prebuild snapshot PASS; hw_emu/hw snapshot_required_missing_count=0 and manifest_required_missing_count=20 before xclbin exists
packet helper dry-run PASS; current source_fingerprint_sha256=d557efd41f44947798a5f204210ed6267bdcf1df9d66c786e51eacd744df3e43
dry-run logs include source_fingerprint_sha256, launch_command, and claim-status gaps
git diff --check PASS
```

## Interpretation

The repository still has a proven `sw_emu` stage-0 correctness artifact, but
that artifact predates the latest report/claim-script source fingerprint and is
kept as historical control-flow evidence. The current build-relevant source has
fresh launch packets for `hw_emu` and `hw`. It does not yet have evidence for a
successful pure-pipeline `hw_emu` or real U55C `hw` build. Therefore the
hardware pipeline goal remains active and incomplete.
