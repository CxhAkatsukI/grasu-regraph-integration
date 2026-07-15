# Pure Pipeline Status Snapshot

Date: 2026-07-15 Asia/Shanghai

Status command input tree, before this documentation-only update:

```text
/home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head: d37fe7858b5a90047ae2451c38499374dc2437b6
source_fingerprint_sha256: 91ba6a6633efd954b6c1eca9b40cc50909c67aa1bc9dc5acdbfcbe9aec55f415
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

Current `sw_emu` postrun evidence was refreshed without rebuilding the xclbin:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target sw_emu \
  --label postrun_after_b5c60ca \
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
gate summary:          7be55be9ac19f13fe8ab180f8ad95b03f058188a68dcfbc81a42c8cb123190c3
full summary:          8baaff4969490b20bc6b1f9eb8dee5baeb969950ffe479dbdbd13756a2ef3fe9
same-input comparison: eabf1d160160e21220fe267e894b2a11fdd817aef1daf9cf94d58b2e276b908f
requirement audit:     3a19c9611c60a3f3f3095a556fa2be00e5e0ec3c68f273e1e6eba14609ef9857
evidence bundle:       0c230da94647e656e00bb578dab154d5fb14b8865acaaf858ced740eacd7e6a3
postrun acceptance:    68f2fe3d437c9618e94cd4cf93926b1d5a6a638a9418ce8ce6a2fa4862a2386c
xclbin contract:       1cc3d8e5ad44862262cbb1294a3b0b6b0a685bf49aefb132325dad28060adcd3
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

Observed result for this snapshot:

```text
sw_emu: xclbin=yes, flow_current=yes, postrun=pass:PASS=11,SKIP=2
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
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_b5c60ca/launch_command.sh
```

The launch packet matches the current build-relevant source fingerprints. It
records source contracts, source fingerprints, prelaunch acceptance gates,
artifact hashes, and the exact target-flow command it will execute.

The packets were regenerated with:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_b5c60ca \
  --allow-active-builders
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_b5c60ca \
  --allow-active-builders
```

Current launch-packet hashes:

```text
hw_emu launch_command.sh:            7523ed83a0a8b245bec8a99e677f93b86401572044157ce8c61aa7e4b1da08ca
hw_emu source_contracts.tsv:         fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw_emu source_fingerprints.tsv:      95ca5df3443e656d4e111a7d3d239b58952f4598be70298d7fc7818e80d0bdaa
hw_emu readiness_hw_emu.txt:         0761b70598875494f84f6f10b0ed17154e1af06c897c748dc012e83ec589d557
hw_emu acceptance_check_prelaunch:   cda252d0cb287737dd73e2bc903a1cb6da90b07c932b24c5bdaf5bf27d25ae66

hw launch_command.sh:                3c8dd8d11f47e3cf70329c2707e500cc3b1585dc9840b75c635a5f8e55ea7669
hw source_contracts.tsv:             fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw source_fingerprints.tsv:          95ca5df3443e656d4e111a7d3d239b58952f4598be70298d7fc7818e80d0bdaa
hw readiness_hw.txt:                 0ff728190a548f66f31547d668f732d04ee9e7ae58ef5dc60697b7ec6f5e3fe9
hw acceptance_check_prelaunch:       898d5ef9b27df267090ff200e4eb3c03323a2a7ae8b49495c5584d17cb79d5d7
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
  --label after_b5c60ca \
  --baseline-label after_64ba9c3 \
  --mode gate
```

Equivalent low-level postrun validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label postrun_after_b5c60ca \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label postrun_after_b5c60ca \
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
  --label after_b5c60ca \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_b5c60ca \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_b5c60ca \
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
python3 tests/test_run_pure_pipeline_postbuild_acceptance.py
python3 tests/test_report_pure_pipeline_next_steps.py
python3 tests/test_summarize_pure_stage0_comparison.py
python3 tests/test_summarize_canonical_comparison.py
python3 -m py_compile scripts/run_pure_pipeline_postbuild_acceptance.py scripts/report_pure_pipeline_next_steps.py scripts/summarize_pure_stage0_comparison.py
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw_emu --dry-run --allow-missing-xclbin
git diff --check
```

Result:

```text
test_run_pure_pipeline_postbuild_acceptance PASS
test_report_pure_pipeline_next_steps PASS
test_summarize_pure_stage0_comparison PASS
test_summarize_canonical_comparison PASS
```

## Interpretation

The current source tree has a proven `sw_emu` control-flow/correctness artifact
for stage 0, plus current launch packets for `hw_emu` and `hw`. It does not yet
have evidence for a successful pure-pipeline `hw_emu` or real U55C `hw` build.
Therefore the hardware pipeline goal remains active and incomplete.
