# Pure Pipeline Status Snapshot

Date: 2026-07-15 Asia/Shanghai

Status command input tree, before this documentation-only commit:

```text
/home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head: 12cb7004b57365b3b85a316a8d5b4fd67e453d05
source_fingerprint_sha256: c5af20bf89c4c0294fb31f0935d728c50af63dce3ea11e0bd48f557ad2442971
dirty: false
```

Documentation-only commits do not change the build-relevant source fingerprint
used by `report_pure_pipeline_next_steps.py`.

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

The report has three command sections:

```text
next_commands       immediate build or postrun action
postrun_followup    skip-build validation to run after a manually produced xclbin exists
stage0_followup     same-input stage0 matrix commands after postrun acceptance passes
```

Observed result for this snapshot:

```text
sw_emu: xclbin=yes, postrun=pass:PASS=11,SKIP=2
hw_emu: xclbin=no, packet_current=yes, postrun=waiting_xclbin
hw:     xclbin=no, packet_current=yes, postrun=waiting_xclbin
active_builders=related:0 external:10
```

The active builders are external Vitis/Vivado processes and are not classified
as this integration repository's pure-pipeline build.

## Next Build Command

The next required long command is the current `hw_emu` launch packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_12cb700/launch_command.sh
```

The launch packet matches the current build-relevant source fingerprints. It
records source contracts, source fingerprints, prelaunch acceptance gates,
artifact hashes, and the exact target-flow command it will execute.

Current launch-packet hashes:

```text
hw_emu launch_command.sh:            94bf5f29d0a3164e2b501e744fea9d1eb779ff5f982d6922c70fd177addef337
hw_emu source_contracts.tsv:         fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw_emu source_fingerprints.tsv:      183ba6ec02ac48622892d27f53a64cd58de3866b7b5b848ffcace881f8b7b694
hw_emu readiness_hw_emu.txt:         1160995d9374c6a08fef65f6ea5dad7047ac8e286a4a4d4aaae5971857b0cc6f
hw_emu acceptance_check_prelaunch:   a4b6fcbb37df034f748191d2986723f2334d2c369c62f8a4717748ae9167ed4e

hw launch_command.sh:                c2eeb29fdaf4ecc9e8ef44c87779b6450600b8533eea1ccf10275eab0dedf5a8
hw source_contracts.tsv:             fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw source_fingerprints.tsv:          183ba6ec02ac48622892d27f53a64cd58de3866b7b5b848ffcace881f8b7b694
hw readiness_hw.txt:                 e55398ffd4c17b82d22a39adde9442d24c15c31a5db499d2a4096bf8ac2c5ed3
hw acceptance_check_prelaunch:       092b0552b81cb616ade7eedb1407b10d59dab5fb19c838da88368a508f68926c
```

Because external Vitis/Vivado builders are active, these packets were generated
with `--allow-active-builders`. The target-flow launch command still includes
the wait-idle guard.

If an xclbin is produced outside the target flow, run the skip-build postrun
validation before the stage0 matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label postrun_after_$(git rev-parse --short HEAD) \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label postrun_after_$(git rev-parse --short HEAD) \
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
  --label after_12cb700 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_12cb700 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_12cb700 \
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
python3 tests/test_report_pure_pipeline_next_steps.py
python3 tests/test_summarize_pure_stage0_comparison.py
python3 tests/test_summarize_canonical_comparison.py
python3 -m py_compile scripts/report_pure_pipeline_next_steps.py scripts/summarize_pure_stage0_comparison.py
git diff --check
```

Result:

```text
test_report_pure_pipeline_next_steps PASS
test_summarize_pure_stage0_comparison PASS
test_summarize_canonical_comparison PASS
```

## Interpretation

The current source tree has a proven `sw_emu` control-flow/correctness artifact
for stage 0, plus current launch packets for `hw_emu` and `hw`. It does not yet
have evidence for a successful pure-pipeline `hw_emu` or real U55C `hw` build.
Therefore the hardware pipeline goal remains active and incomplete.
