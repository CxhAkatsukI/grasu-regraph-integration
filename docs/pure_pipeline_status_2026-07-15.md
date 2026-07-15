# Pure Pipeline Status Snapshot

Date: 2026-07-15 Asia/Shanghai

Status command input tree, before this documentation-only commit:

```text
/home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head: e7b265e881a5c9b003966e1cc0f8cb0e47f6d962
source_fingerprint_sha256: 87feb423a21e214386388be8c0bfd7cdd6e976f75f2156eaa66321f1e82543c2
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
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_cf046c8/launch_command.sh
```

The launch packet matches the current build-relevant source fingerprints. It
records source contracts, source fingerprints, prelaunch acceptance gates,
artifact hashes, and the exact target-flow command it will execute.

After `hw_emu` exists and postrun acceptance passes, run:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw_emu \
  --mode gate \
  --label after_cf046c8 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_cf046c8 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_cf046c8 \
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
python3 tests/test_summarize_pure_stage0_comparison.py
python3 tests/test_summarize_canonical_comparison.py
python3 -m py_compile scripts/summarize_pure_stage0_comparison.py
git diff --check
```

Result:

```text
test_summarize_pure_stage0_comparison PASS
test_summarize_canonical_comparison PASS
```

## Interpretation

The current source tree has a proven `sw_emu` control-flow/correctness artifact
for stage 0, plus current launch packets for `hw_emu` and `hw`. It does not yet
have evidence for a successful pure-pipeline `hw_emu` or real U55C `hw` build.
Therefore the hardware pipeline goal remains active and incomplete.
