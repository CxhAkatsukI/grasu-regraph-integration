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

Postbuild helper update:

```text
helper commit: 782ce71b6e0568de4baf564366e3e582083c9ddb
source_fingerprint_sha256: 6ad3673a33472d87bf13d71eb99ffd5be83a7d384e64ce61b714c31f4b7a2df6
new helper: scripts/wait_for_pure_pipeline_xclbin_then_accept.py
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

The report has four command sections:

```text
next_commands       immediate build or postrun action
postbuild_acceptance
                    guarded wrapper commands to run after a target xclbin exists
postrun_followup    skip-build validation to run after a manually produced xclbin exists
stage0_followup     same-input stage0 matrix commands after postrun acceptance passes
```

The target table also reports `stage0_gate` and `stage0_full`. `stage0_gate`
means the four required smoke families have passed the same-input matrix for
that target; `stage0_full` is reserved for the full tracked stage-0 matrix.

Observed result for this snapshot:

```text
sw_emu: xclbin=yes, flow_current=yes, packet_current=no,  postrun=pass:PASS=11,SKIP=2, stage0_gate=pass,    stage0_full=missing
hw_emu: xclbin=no,  flow_current=no,  packet_current=yes, postrun=waiting_xclbin,        stage0_gate=missing, stage0_full=missing
hw:     xclbin=no,  flow_current=no,  packet_current=yes, postrun=waiting_xclbin,        stage0_gate=missing, stage0_full=missing
active_builders=related:0 external:10
```

The active builders are external Vitis/Vivado processes and are not classified
as this integration repository's pure-pipeline build.

## Next Build Command

The next required long command is the current `hw_emu` launch packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_782ce71/launch_command.sh
```

The launch packet matches the current build-relevant source fingerprints. It
records source contracts, source fingerprints, prelaunch acceptance gates,
artifact hashes, and the exact target-flow command it will execute.

The packets were regenerated with:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_782ce71 \
  --allow-active-builders
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_782ce71 \
  --allow-active-builders
```

Current launch-packet hashes:

```text
hw_emu launch_command.sh:            9a43a1f48e1e89668aeb927ee0298eb44fb825b6b0132d6ed042e305c25443ab
hw_emu source_contracts.tsv:         fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw_emu source_fingerprints.tsv:      907f93798197bad6faef842ffe1ed5119c805a40b2e08a91f3f56aafc005a178
hw_emu readiness_hw_emu.txt:         4e82bbc9ff8f901b148f1b7b957d610cd07e72867a729ee4290c13cc2e201904
hw_emu acceptance_check_prelaunch:   549ee4afc174f998b4684a3ac9cd40176faf6841dc3df16870bfe1277cbdd9c5
hw_emu packet audit:                 40abfe786db4129d8a14c8e22c807f9e61ac44b31f01b266a3953a884af79476
hw_emu packet evidence bundle:       d3b24df2523acbaae78b4d09ea1f47a7fce736b32c6e2832d1c933684ce3a3c2

hw launch_command.sh:                f90d7caa2a179ad1f241a5b8675ee3adc83b870d71247e9d702745d375d78a3b
hw source_contracts.tsv:             fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw source_fingerprints.tsv:          907f93798197bad6faef842ffe1ed5119c805a40b2e08a91f3f56aafc005a178
hw readiness_hw.txt:                 3ea338e17f4204063b3c7afdbcf9d066860be6104f58fe6e9042c203118489bf
hw acceptance_check_prelaunch:       78697c944cbee678f90d6d542478bf8376403ec511de30ede4e02a40f4c012cd
hw packet audit:                     f44fc14f19ac9f868917cd3382cccedb3d88b5fd13deeb84cb5f9bbbac32a60b
hw packet evidence bundle:           1c42ebfa4d117094470d092d02979cd47f840d485b0f139ef706a3311ee0d793
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
  --label after_782ce71 \
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
  --label after_782ce71 \
  --baseline-label after_64ba9c3 \
  --mode gate

./scripts/wait_for_pure_pipeline_xclbin_then_accept.py \
  --target hw \
  --label after_782ce71 \
  --baseline-label after_64ba9c3 \
  --mode gate
```

Equivalent low-level postrun validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label postrun_after_782ce71 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label postrun_after_782ce71 \
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
  --label after_782ce71 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_782ce71 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_782ce71 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

## Latest Script Validation

The comparison-report path now has a regression test that covers missing
pure-pipeline rows. This prevents an absent `hw_emu` or `hw` row from being
reported as if it had real mismatches or `sw_emu` timing.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 tests/test_wait_for_pure_pipeline_xclbin_then_accept.py
python3 tests/test_run_pure_pipeline_postbuild_acceptance.py
python3 tests/test_report_pure_pipeline_next_steps.py
python3 tests/test_audit_pure_pipeline_status.py
python3 tests/test_summarize_pure_stage0_comparison.py
python3 tests/test_summarize_canonical_comparison.py
python3 -m py_compile scripts/audit_pure_pipeline_status.py scripts/run_pure_pipeline_postbuild_acceptance.py scripts/wait_for_pure_pipeline_xclbin_then_accept.py scripts/report_pure_pipeline_next_steps.py scripts/summarize_pure_stage0_comparison.py
./scripts/report_pure_pipeline_next_steps.py --json > .tmp_build/report_next_steps_stage0_columns.json
python3 -m json.tool .tmp_build/report_next_steps_stage0_columns.json >/dev/null
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw_emu --dry-run --allow-missing-xclbin
./scripts/wait_for_pure_pipeline_xclbin_then_accept.py --target hw_emu --dry-run
git diff --check
```

Result:

```text
test_wait_for_pure_pipeline_xclbin_then_accept PASS
test_run_pure_pipeline_postbuild_acceptance PASS
test_report_pure_pipeline_next_steps PASS
test_audit_pure_pipeline_status PASS
test_summarize_pure_stage0_comparison PASS
test_summarize_canonical_comparison PASS
report_pure_pipeline_next_steps JSON validation PASS
postbuild_acceptance hw_emu dry-run PASS
```

## Interpretation

The current source tree has a proven `sw_emu` control-flow/correctness artifact
for stage 0 aligned to the current build-relevant source fingerprint, plus
current launch packets for `hw_emu` and `hw`. It does not yet have evidence for
a successful pure-pipeline `hw_emu` or real U55C `hw` build. Therefore the
hardware pipeline goal remains active and incomplete.
