# Pure Pipeline Status Snapshot

Date: 2026-07-15 Asia/Shanghai

Status command input tree, before this documentation-only update:

```text
/home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head: c29ee70c5aa3cffd1d5e4701434dcf5a919b8534
source_fingerprint_sha256: 283ae98d78b3821c043af87cf74ca33da83b5bacd591c742ee594e8bcad74dae
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
source_fingerprint_sha256: 8ab5872c8e81e1040af30099de1a435fff3ed691050b4fc73977df8c97203a6a
new helper: scripts/wait_for_pure_pipeline_xclbin_then_accept.py
report block: postbuild_wait
report block: claim_status
postbuild wrappers: print source fingerprint, launch packet, and claim-status gaps before acceptance
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
sw_emu: xclbin=yes, flow_current=no, packet_current=no,  postrun=pass:PASS=11,SKIP=2, stage0_gate=pass,    stage0_full=missing
hw_emu: xclbin=no,  flow_current=no, packet_current=yes, postrun=waiting_xclbin,        stage0_gate=missing, stage0_full=missing
hw:     xclbin=no,  flow_current=no, packet_current=yes, postrun=waiting_xclbin,        stage0_gate=missing, stage0_full=missing
completion claimable=no; missing=hw_emu_gate,hw_gate,hw_full
active_builders=related:0 external:10
```

The active builders are external Vitis/Vivado processes and are not classified
as this integration repository's pure-pipeline build.

## Next Build Command

The next required long command is the current `hw_emu` launch packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_d5302c4/launch_command.sh
```

The launch packet matches the current build-relevant source fingerprints. It
records source contracts, source fingerprints, prelaunch acceptance gates,
artifact hashes, and the exact target-flow command it will execute.

The packets were regenerated with:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_d5302c4 \
  --allow-active-builders
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_d5302c4 \
  --allow-active-builders
```

Current launch-packet hashes:

```text
hw_emu launch_command.sh:            82e690f5209806153fa9e21d2d6c3a429c1aa7c693ab536b6f3db7b63356ade0
hw_emu source_contracts.tsv:         fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw_emu source_fingerprints.tsv:      ccc4c71f34f50147ebe8419c5abca0c6c8ba7ae5d88b8c48c26c04d5be840084
hw_emu readiness_hw_emu.txt:         d840ea7554aba13d3c06c2a234fea1ba12bd7ef6737f66a330f0090668520248
hw_emu acceptance_check_prelaunch:   c3da3d4fe3b18882d6863f0ace047e47f4b227653c8c8872254b72cbc05dd5c3
hw_emu packet audit:                 833cd3fd2c4174b779340b250c7870f3460e4223c2c81f0a31dd951bf847b438
hw_emu packet evidence bundle:       22aa08b9ffd5b6f87a0d151d5a5b3f2d5bc40930b8159c6d4068c714ec0b57cb

hw launch_command.sh:                52576322eefedc7247d1aa3dff7b744ce6712894362928730082c8408381f4e6
hw source_contracts.tsv:             fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw source_fingerprints.tsv:          ccc4c71f34f50147ebe8419c5abca0c6c8ba7ae5d88b8c48c26c04d5be840084
hw readiness_hw.txt:                 6e4cf3f31c2cbad06c652c9a26f2f95f70eeeded932bc410d00d589486148859
hw acceptance_check_prelaunch:       23199fc2956b898de1dd0687647b56b795161f5e51832704fffa31b7bb3fc63f
hw packet audit:                     3baff2d70aa94a81babd9eb01f36a5fd97738b5a2630fa041c81a9b8e4109dc9
hw packet evidence bundle:           fd1798648b4a4654be4734c80a55d923fe5672111b3235ad453229d0ae30dba5
```

Because external Vitis/Vivado builders are active, these packets were generated
with `--allow-active-builders`. The target-flow launch command still includes
the wait-idle guard.

If an xclbin is produced outside the target flow, the guarded wrapper runs
skip-build postrun validation and then the same-input stage0 matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_postbuild_acceptance.py \
  --target hw_emu \
  --label after_d5302c4 \
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
  --label after_d5302c4 \
  --baseline-label after_64ba9c3 \
  --mode gate

./scripts/wait_for_pure_pipeline_xclbin_then_accept.py \
  --target hw \
  --label after_d5302c4 \
  --baseline-label after_64ba9c3 \
  --mode gate
```

Equivalent low-level postrun validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label postrun_after_d5302c4 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label postrun_after_d5302c4 \
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
  --label after_d5302c4 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_d5302c4 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_d5302c4 \
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
context in their dry-run and real acceptance logs.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 tests/test_wait_for_pure_pipeline_xclbin_then_accept.py
python3 tests/test_run_pure_pipeline_postbuild_acceptance.py
python3 tests/test_report_pure_pipeline_next_steps.py
python3 tests/test_check_pure_pipeline_acceptance_gates.py
python3 tests/test_summarize_pure_pipeline_smoke.py
python3 tests/test_audit_pure_pipeline_status.py
python3 tests/test_summarize_pure_stage0_comparison.py
python3 tests/test_summarize_canonical_comparison.py
python3 -m py_compile scripts/audit_pure_pipeline_status.py scripts/run_pure_pipeline_postbuild_acceptance.py scripts/wait_for_pure_pipeline_xclbin_then_accept.py scripts/report_pure_pipeline_next_steps.py scripts/summarize_pure_stage0_comparison.py scripts/check_pure_pipeline_acceptance_gates.py scripts/summarize_pure_pipeline_smoke.py
./scripts/report_pure_pipeline_next_steps.py --json > .tmp_build/report_next_steps_stage0_columns.json
python3 -m json.tool .tmp_build/report_next_steps_stage0_columns.json >/dev/null
./scripts/report_pure_pipeline_next_steps.py --json > .tmp_build/report_next_steps_claim_status.json
python3 -m json.tool .tmp_build/report_next_steps_claim_status.json >/dev/null
python3 scripts/summarize_pure_pipeline_smoke.py --host-summary results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv --pure-summary results/pure_pipeline_sw_emu_smoke_postrun_after_c29ee70/summary.tsv --pure-env results/pure_pipeline_sw_emu_smoke_postrun_after_c29ee70/run.env --spine-summary results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv --out-dir .tmp_build/pure_pipeline_sw_emu_compare_postrun_after_c29ee70_timing_gate
./scripts/check_pure_pipeline_acceptance_gates.py --acceptance-gates .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/acceptance_gates_target_flow_postrun_after_c29ee70.tsv --mode postrun --out-file .tmp_build/acceptance_check_swemu_new_timing_gate.tsv
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw_emu --dry-run --allow-missing-xclbin
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py --target hw_emu --dry-run
git diff --check
```

Result:

```text
test_wait_for_pure_pipeline_xclbin_then_accept PASS
test_run_pure_pipeline_postbuild_acceptance PASS
test_report_pure_pipeline_next_steps PASS
test_check_pure_pipeline_acceptance_gates PASS
test_summarize_pure_pipeline_smoke PASS
test_audit_pure_pipeline_status PASS
test_summarize_pure_stage0_comparison PASS
test_summarize_canonical_comparison PASS
report_pure_pipeline_next_steps JSON validation PASS
report_pure_pipeline_next_steps claim-status JSON validation PASS
smoke comparison timing-gate regeneration PASS
acceptance_check_swemu_new_timing_gate PASS=11, SKIP=2
postbuild_acceptance hw_emu dry-run PASS
wait_for_pure_pipeline_xclbin_then_accept hw_emu dry-run PASS
dry-run logs include source_fingerprint_sha256 and launch_command
git diff --check PASS
```

## Interpretation

The current source tree has a proven `sw_emu` control-flow/correctness artifact
for stage 0 aligned to the current build-relevant source fingerprint, plus
current launch packets for `hw_emu` and `hw`. It does not yet have evidence for
a successful pure-pipeline `hw_emu` or real U55C `hw` build. Therefore the
hardware pipeline goal remains active and incomplete.
