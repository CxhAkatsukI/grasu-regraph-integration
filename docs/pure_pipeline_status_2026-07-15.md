# Pure Pipeline Status Snapshot

Date: 2026-07-15 Asia/Shanghai

Status command input tree, before this documentation-only update:

```text
/home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head: b1bafb2e1183d32dd7ec2fe013f8dbf33a9a5edb
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
  --label postrun_after_b1bafb2 \
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
source fingerprints:   7f683856535c88ce056c3892d99eebd268624f8cd9b08f61e9c74121e91355f1
readiness report:      2025eaf24d4a49c0f171651f8ce4b38393d57eee46e4a273bd823b66cc485317
smoke summary:         5902ad49dc9d845b03417daad2fdb8039fad9abbfd57eb2a0c6c726aed571b1f
same-input comparison: 60989f5251b1bba37ef4a1cf483e06515977976cf6da436d894c78e948cbc05a
requirement audit:     ee6e48b005c157bfc5d3392013b940820570a7443726285667f33f996ee9c78c
evidence bundle:       0c0cae338433b301537fcdc8ec11f18fda45c8515e0500b5bea3924bde843691
postrun acceptance:    a430fe19b31fef5eabf8e3ff3ef5304c8e9c5204ae8484a147ac54e41c2b6994
xclbin contract:       1cc3d8e5ad44862262cbb1294a3b0b6b0a685bf49aefb132325dad28060adcd3
```

Current `sw_emu` pure_stage0 gate evidence was also refreshed against the
`after_64ba9c3` host/Spine baseline inputs:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_stage0_postbuild_matrix.sh \
  --target sw_emu \
  --mode gate \
  --label after_b1bafb2 \
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
comparison plan:       04de92af08bbe215a685ae1e771d070bbbfc2c86901ca3f0a338b206d0a8c2a5
input identity plan:   fd4a690c32bf7fc6d5f0c1264c575b79157f63ddfe21d65abe063749e5a0940b
gate summary:          e7df944d4de7b7af89a977f14dabfd1388d8af1673c57cbb664a767d64763268
identity audit:        b15473b09bd155620c2a03fe7677aaf77b4681f86656088a7ad4df2e64a1be90
same-input comparison: d21b75657ba30e9e5d7a41b294c4fc25df28c77a215bc23edf9b5099a13ec3c4
postbuild env:         f6a3066cb32843c492f35bcb5e5a433807651fed323cfc8ca1321d398404278e
```

The current requirement audit and evidence bundle were refreshed by the
`sw_emu` postrun command above at commit
`b1bafb2e1183d32dd7ec2fe013f8dbf33a9a5edb`:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/audit_pure_pipeline_status.py \
  --label postrun_after_b1bafb2 \
  --out-dir results/pure_pipeline_requirement_audit_postrun_after_b1bafb2
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_postrun_after_b1bafb2/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_postrun_after_b1bafb2
```

The target-flow wrapper ran these steps sequentially after smoke and comparison
completed.

```text
requirement audit json: ee6e48b005c157bfc5d3392013b940820570a7443726285667f33f996ee9c78c
evidence manifest:      0c0cae338433b301537fcdc8ec11f18fda45c8515e0500b5bea3924bde843691
evidence summary:       457d0ea8e9ca189048e4d40a87ad3063deec1d42bb02ba4162f0d7c7d9551276
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
for stage 0 aligned to the current build-relevant source fingerprint, plus
current launch packets for `hw_emu` and `hw`. It does not yet have evidence for
a successful pure-pipeline `hw_emu` or real U55C `hw` build. Therefore the
hardware pipeline goal remains active and incomplete.
