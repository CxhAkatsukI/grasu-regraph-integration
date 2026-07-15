# Pure Pipeline Status Snapshot

Date: 2026-07-15 Asia/Shanghai

Status command input tree, before this documentation-only update:

```text
/home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head: e2861d448564257e45bc9a042f553d718544b9a9
source_fingerprint_sha256: 46547110418976febae9c4dd8f97f3bb59f611f9628445ee4e77f903aef4da6b
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

Current `sw_emu` pure_stage0 gate evidence was also refreshed against the
`after_64ba9c3` host/Spine baseline inputs:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target sw_emu \
  --mode gate \
  --label after_b5c60ca \
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
comparison plan:       62792c78244b339c4798dab18ddba79a6b8ad5eaa16a555c24ab19982b9d963e
input identity plan:   fd4a690c32bf7fc6d5f0c1264c575b79157f63ddfe21d65abe063749e5a0940b
gate summary:          c332380e540a36e62b418f0bfc6d4311640c52ca0be4f5b74b2bc59068144fc8
identity audit:        b7399e4086f14e4670d3b6dd429c8c12587c77b769a7215d4c0ca76b785c28d0
same-input comparison: f08bdd3d98aaad2821a543d7d543e12d6e100d238c0f8e2ae51511164dedb68d
postbuild env:         52d323b1b883c129bbcce4b6b109135545719f57edb376662ec9368688bf1be4
```

The current requirement audit and evidence bundle were refreshed at commit
`6c26605a07097bd7f0d152b0d78d17463e46e6cf`:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/audit_pure_pipeline_status.py \
  --label after_6c26605 \
  --out-dir results/pure_pipeline_requirement_audit_after_6c26605
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_after_6c26605/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_after_6c26605
```

The first bundle attempt was started in parallel with the audit and failed
because `audit.json` did not exist yet; the sequential command above passed.

```text
requirement audit json: e4a3fe5d4ae31144d66b520c25b3318547ee817ad8f662627cfd6da99570f695
requirement audit md:   fa227290730e08e673d1df679f9b25fad93b231a715f8d4f205681573d7f3de9
evidence manifest:      a6fc63d0e5087a3c51a1be05fe41f4664ba0f0e5d0a20a065c8b88d6ce1edbb0
evidence summary:       f6500a5959c35f97aa0710bafabc155e157d027a54f1df0811375c9ff3e1b799
status counts:          blocked_by_missing_artifact=1, partial=8, proven=1
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
sw_emu: xclbin=yes, flow_current=no,  packet_current=no,  postrun=pass:PASS=11,SKIP=2, stage0_gate=pass,    stage0_full=missing
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
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_after_e2861d4/launch_command.sh
```

The launch packet matches the current build-relevant source fingerprints. It
records source contracts, source fingerprints, prelaunch acceptance gates,
artifact hashes, and the exact target-flow command it will execute.

The packets were regenerated with:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_e2861d4 \
  --allow-active-builders
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_e2861d4 \
  --allow-active-builders
```

Current launch-packet hashes:

```text
hw_emu launch_command.sh:            e1e561e6eaa4afaf5590885efe55e806f807b09e6a6b6ac2d3c553ddaa7b0771
hw_emu source_contracts.tsv:         fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw_emu source_fingerprints.tsv:      7f683856535c88ce056c3892d99eebd268624f8cd9b08f61e9c74121e91355f1
hw_emu readiness_hw_emu.txt:         0725caac83370d5c8df8e56a3b58e6292eba67494c3f439c88d9a47796531af3
hw_emu acceptance_check_prelaunch:   b9a10194534cb7222ee8e8d8911fc3632a635dce33cab4f9d443b5288c8d14cf

hw launch_command.sh:                e8a799d380e35eb66ad34206917aa1bf34ad988b225d8b48a6f856d35edd7b33
hw source_contracts.tsv:             fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac
hw source_fingerprints.tsv:          7f683856535c88ce056c3892d99eebd268624f8cd9b08f61e9c74121e91355f1
hw readiness_hw.txt:                 4a9819750cc7de02b344f8b408b2d03f3b14f6a27e3b7b974fbf7591a2c329e5
hw acceptance_check_prelaunch:       8fa29bf26337e42a35b0f0027c8387bf5c1d8a6afae039b23fc2f2f3e5c1d51d
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
  --label after_e2861d4 \
  --baseline-label after_64ba9c3 \
  --mode gate
```

Equivalent low-level postrun validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label postrun_after_e2861d4 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label postrun_after_e2861d4 \
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
  --label after_e2861d4 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

After the real `hw` xclbin exists and postrun acceptance passes, run the gate:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode gate \
  --label after_e2861d4 \
  --baseline-label after_64ba9c3 \
  --require-compare
```

Then run the full tracked matrix:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target hw \
  --mode full \
  --label after_e2861d4 \
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
./scripts/report_pure_pipeline_next_steps.py --json > .tmp_build/report_next_steps_stage0_columns.json
python3 -m json.tool .tmp_build/report_next_steps_stage0_columns.json >/dev/null
./scripts/run_pure_pipeline_postbuild_acceptance.py --target hw_emu --dry-run --allow-missing-xclbin
git diff --check
```

Result:

```text
test_run_pure_pipeline_postbuild_acceptance PASS
test_report_pure_pipeline_next_steps PASS
test_summarize_pure_stage0_comparison PASS
test_summarize_canonical_comparison PASS
report_pure_pipeline_next_steps JSON validation PASS
postbuild_acceptance hw_emu dry-run PASS
```

## Interpretation

The current source tree has a proven `sw_emu` control-flow/correctness artifact
for stage 0, plus current launch packets for `hw_emu` and `hw`. It does not yet
have evidence for a successful pure-pipeline `hw_emu` or real U55C `hw` build.
Therefore the hardware pipeline goal remains active and incomplete.
