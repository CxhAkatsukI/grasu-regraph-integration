# Canonical Comparison Summary Contract

Date: 2026-07-14

`scripts/summarize_canonical_comparison.py` is the final guard between raw
JSONL measurements and a cross-system winner table. It accepts Spine,
GraSU+ReGraph, and future GraSU+AccuGraph records, but emits a winner only when
all three groups for a case satisfy every gate:

- at least 10 non-warmup runs;
- every measured run passes correctness;
- graph hash and BFS source match the frozen selection;
- all records explicitly permit a performance claim;
- source commits exist and tracked worktrees are clean;
- each host/xclbin identity is unique within the group;
- every measured run has comparable `resident_batch_end_to_end_ms`.

The resident-batch boundary starts after base-graph preload and includes the
ordered update/state input transfer through verified output. Device-only,
cold-workload, and process-wall metrics are retained as diagnostics, but are
not silently substituted when that field is missing. In particular, the
current GraSU+ReGraph host pipeline wall includes host/program startup and
therefore cannot be compared directly with Spine's resident-batch boundary.

Current diagnostic use:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/summarize_canonical_comparison.py \
  --selection /home/chuxiao/grasu-accugraph-integration/.tmp_build/evaluation_comparison/cross_system_selection.json \
  --input /home/chuxiao/grasu-accugraph-integration/results/spine_chain32_canonical_hw_20260714.jsonl \
  --input /home/chuxiao/grasu-accugraph-integration/results/grasu_regraph_chain32_canonical_hw_20260714.jsonl \
  --output-dir .tmp_build/canonical_summary_chain32
```

The expected current result is `all_rankings_eligible=false`: both baselines
have one diagnostic run, GraSU+AccuGraph is not built on hardware yet, and the
baseline xclbin provenance gates remain open. This refusal is intentional.
