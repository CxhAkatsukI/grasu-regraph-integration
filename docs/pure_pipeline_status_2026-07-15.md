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
hw_emu/hw xclbins: still missing
```

This snapshot answers the narrow build-status question first: there is not yet a
successful pure-pipeline `hw` xclbin. The only current pure-pipeline xclbin is
the `sw_emu` stage-0 artifact.

## Target State

```text
target    xclbin  status
sw_emu    yes     stage0 gate already passed
hw_emu    no      waiting_xclbin
hw        no      waiting_xclbin
```

Current `sw_emu` artifact:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
sha256: b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
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
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_1d1a588/launch_command.sh
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
1fae7ce864ece0b36c50f90d9f673e83fc2e4b3bec8c26a932012a1340fc7739
```

Current launch-packet hashes:

```text
hw_emu launch_command.sh:            1478d6a72a420032fd4512ddc1dc6e4726d9ab9e4c004dbec164737e76ad1bd7
hw_emu postbuild_acceptance_gate.sh: 21cd63c7ff90b750bbd196e6e4a276a3316c7d4627e46f217b11f6eaa2db6cf0
hw_emu wait_then_accept_gate.sh:     6286b9735157eb9b8dbcbfef68c2db59719fc951ea3b5a801bf8d8b3bba6bc16
hw_emu postbuild_acceptance_full.sh: 69301baa201a737dc19d53757f73ef558cc24fbf205ceedc358e32091df344a4
hw_emu wait_then_accept_full.sh:     3771dbeb28b64534c6c4efff747cb161c9c74588d311e4c859b3f08f4f77af3d
hw_emu source_contracts.tsv:         9629063f87f440dcaebc8f17f5d38009b0673c742bcf356b03c3ad89181a7c73
hw_emu source_fingerprints.tsv:      9a5393fca8d774c374fc5ca046734367fa900dc07424dc7650bcb747aed15498
hw_emu readiness_hw_emu.txt:         0549e6702ef5138f2686141c4309c078795fcf1e3555fe8a8c9f7db6e106e597
hw_emu acceptance_check_prelaunch:   55cf839de62ccf819b68895b491ef628539a04f80fc665cbacff5e5267983986
hw_emu packet audit:                 7c2e307bbdfcf8ef6d72f8fa55f124ffe50ddcc523da868aa86bf438f614c17b
hw_emu packet evidence bundle:       f89cff06a2b135eb3b8fbdf76156b28aa2a099b2bb997540c2a79b048f1d55fa

hw launch_command.sh:                604c87fa5a5a3a946cf5b201da449493a65659184af4055970d55bb120a6c35c
hw postbuild_acceptance_gate.sh:     b907eb9c009b2a0df82241a41ec7c3f83887525eff572fce29cfc22037b29f5d
hw wait_then_accept_gate.sh:         7731c132e45b2fe3a4f7e897b4605c4658497606e71b5be680f35b1e2c2b0a64
hw postbuild_acceptance_full.sh:     5eb247e34c4d410935f807daa2b9140cf4adfde856bc8147d91805a613534c83
hw wait_then_accept_full.sh:         9948bb215ff8e7e9ca6d07410adc67166da0c233b41a2178467b9a3c2fbf4f55
hw source_contracts.tsv:             9629063f87f440dcaebc8f17f5d38009b0673c742bcf356b03c3ad89181a7c73
hw source_fingerprints.tsv:          9a5393fca8d774c374fc5ca046734367fa900dc07424dc7650bcb747aed15498
hw readiness_hw.txt:                 d9d2f8b9362c44977d6d7f5b0f696bc849d0539daefecd7fe7e7dfb9e5db76c6
hw acceptance_check_prelaunch:       9702c865142cf9339c22a717af5ef83e1b6ce9bc33573e5026c3e496e0ddd7ae
hw packet audit:                     407e728ff5eebe3c5dcbee1b56e1f46919bf5474e07636e6946af5eda49dce76
hw packet evidence bundle:           612cddbae20c38ef4a31860e750f3c78c157cd8071ad30da81696cc595ea09f9
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
  --label after_1d1a588 \
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
  --label after_1d1a588 \
  --baseline-label after_64ba9c3 \
  --mode gate

./scripts/wait_for_pure_pipeline_xclbin_then_accept.py \
  --target hw \
  --label after_1d1a588 \
  --baseline-label after_64ba9c3 \
  --mode gate
```

Equivalent packet-local helper scripts:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_1d1a588/wait_then_accept_gate.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_1d1a588/wait_then_accept_gate.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_1d1a588/wait_then_accept_full.sh
```

Equivalent low-level postrun validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label postrun_after_1d1a588 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label postrun_after_1d1a588 \
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
  --label after_1d1a588 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_1d1a588 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_1d1a588 \
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
./scripts/collect_pure_pipeline_artifact_manifest.py --target hw_emu --label after_f461c07 --baseline-label after_64ba9c3 --mode gate --level gate --out-file .tmp_build/artifact_manifest_hwemu_after_f461c07_allow_missing.tsv --allow-missing-required
./scripts/create_pure_pipeline_launch_packet.sh --target hw_emu --flow-label after_f461c07 --allow-active-builders
./scripts/create_pure_pipeline_launch_packet.sh --target hw --flow-label after_f461c07 --allow-active-builders
bash -n .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_f461c07/postbuild_acceptance_gate.sh .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_f461c07/wait_then_accept_gate.sh
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py --target hw_emu --label after_f461c07 --baseline-label after_64ba9c3 --mode gate --dry-run
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
artifact manifest hw_emu allow-missing sample PASS with required_missing_count=18 before hw_emu xclbin exists
claim-status manifest regression PASS; hw_emu/hw missing evidence now includes artifact_manifest_build/gate/full until a passing manifest is present
requirement audit manifest regression PASS; completion_summary.missing_artifact_manifest_claims=hw_emu:build,hw_emu:gate,hw_emu:full,hw:build,hw:gate,hw:full
postbuild label guard PASS; wrong label exits rc=2 before xclbin/postbuild work
source-contract label guard PASS; required_count=18 and postbuild_label_guard ok=yes
source-contract packet helper proof PASS; launch_packet_records_acceptance_gates still ok=yes after helper addition
launch packet helper generation PASS; hw_emu/hw packets for after_f461c07 include postbuild/wait gate and full helpers, all hashed in artifact_hashes.tsv
next-step report helper visibility PASS; packet_local_helpers lists four helpers for hw_emu and four helpers for hw
artifact manifest helper evidence PASS; hw_emu allow-missing manifest records all four packet-local helper scripts as required PASS artifacts
packet helper dry-run PASS; current source_fingerprint_sha256=86d6692740c28cece89ddcb6b80a206b435f51cf8e4398ff2ae668bae63ee9a2
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
