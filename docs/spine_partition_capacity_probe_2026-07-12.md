# Spine Partition Capacity Probe

Date: 2026-07-12

## Purpose

The earlier threshold run showed that Spine failed immediately after crossing
the first `131072`-edge batch boundary on chain and hot-destination workloads.
This follow-up checks whether the failure means:

- split-CU carry is generally broken;
- edge-file two-batch carry is generally broken;
- or the input distribution exceeds Spine's per-destination-partition storage
  capacity during level carry.

## Key Finding

The failure is not simply "second batch is broken".

Split-CU can carry from L0 to L1 correctly when the edges are distributed across
destination partitions. The failing chain/hot-destination cases are dominated by
one destination partition, which is legal for L0 but can exceed the per-partition
capacity of L1.

Important constants:

```text
HOST_PARTITIONED_RATIO2_MAX_SORT_N = 131072
HOST_PARTITIONED_CSR_DST_PARTITIONS = 16
L0 capacity per partition = 131072
L1 total capacity = 262144
L1 capacity per partition = ceil(262144 / 16) = 16384
```

So a one-partition batch with `131072` edges can be stored in L0. When the next
batch forces L0 + new edges into L1, the same one-partition distribution needs
more than `16384` L1 slots in that partition and cannot fit.

## Evidence Root

```text
/home/chuxiao/grasu-regraph-integration/results/spine_measure_carry_probe_hw_20260712_211600
```

Split host:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge
sha256 df0aa0dca3eddb09aa58805fe7bb1c65e4c1a7484ab8ae6ca230c11bbff90bdd
```

Split xclbin:

```text
/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin
sha256 69145517738cc1ffff95e91c24393260c346ac683db9eef2989bbc1bdb7a3469
```

Single-kernel diagnostic host:

```text
/home/chuxiao/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke
sha256 83d7654b289d4057e47843c3385c057bdd42863694ab8d78e125201ccd219fcb
```

Single-kernel diagnostic xclbin:

```text
/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/xclbin/spine_partitioned_e2e.hw.xclbin
sha256 ae591fba01896ba6f6835eab866793e932315ffd28459e5e0b7e5c3c2e7ce20c
```

## Environment

Every real-hw run needs XRT loaded:

```bash
source /opt/xilinx/xrt/setup.sh
export XILINX_XRT=/opt/xilinx/xrt
export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}
```

Without this, the host exits before programming the device with:

```text
[XRT] ERROR: XILINX_XRT must be set
```

## Results

| probe | command shape | result | key observation |
| --- | --- | --- | --- |
| single measure-carry small | `--measure-carry 1 1024 64` | PASS | L1 carry works in the single-kernel diagnostic path. |
| single measure-carry full | `--measure-carry 1 131072 64` | PASS | Full-size symmetric carry works; `persisted=262144`, `maint_ms=1266.53`. |
| split repeat fanout small | `SPINE_PARTITIONED_SPLIT=1 --repeat-fanout 1024 2 64` | PASS | Split-CU L0->L1 works for two generated batches. |
| split repeat fanout full | `SPINE_PARTITIONED_SPLIT=1 --repeat-fanout 131072 2 64` | PASS | Split-CU full two-batch carry works when edges are balanced; `persisted=262144`. |
| split edge-file one-partition full+1 | generated `131072+1` edge file, all dst in one partition | FAIL | Hardware reports overflow on batch 2; host expected model did not account for per-partition L1 capacity. |
| split edge-file balanced full+1 | generated `131072+1` edge file, dst balanced across 16 partitions | PASS | Same two-batch asymmetry passes when per-partition capacity is respected. |

## Exact Reproduction Commands

Single-kernel full carry:

```bash
cd /home/chuxiao/grasu-regraph-integration
source /opt/xilinx/xrt/setup.sh
export XILINX_XRT=/opt/xilinx/xrt
export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}

/home/chuxiao/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke \
  /home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/xclbin/spine_partitioned_e2e.hw.xclbin \
  --measure-carry 1 131072 64 --timeout 180
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_measure_carry_probe_hw_20260712_211600/measure_carry_single_l1_131072_s64.log
```

Split-CU full two-batch generated fanout:

```bash
cd /home/chuxiao/grasu-regraph-integration
source /opt/xilinx/xrt/setup.sh
export XILINX_XRT=/opt/xilinx/xrt
export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}

SPINE_PARTITIONED_SPLIT=1 \
/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge \
  /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
  --repeat-fanout 131072 2 64 --timeout 180
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_measure_carry_probe_hw_20260712_211600/split_repeat_fanout_131072x2_s64.log
```

One-partition `131072+1` edge-file probe:

```bash
cd /home/chuxiao/grasu-regraph-integration
RESULT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_measure_carry_probe_hw_20260712_211600
CASE_DIR="${RESULT_ROOT}/split_edge_file_fanout_full_plus_one"
mkdir -p "${CASE_DIR}"
EDGE_FILE="${CASE_DIR}/fanout_full_plus_one.edges"

awk 'BEGIN {
  for (i=0; i<131072; i++) {
    printf "%d %d 1 1\n", i % 64, i + 1;
  }
  printf "64 200000 1 1\n";
}' > "${EDGE_FILE}"

source /opt/xilinx/xrt/setup.sh
export XILINX_XRT=/opt/xilinx/xrt
export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}

SPINE_PARTITIONED_SPLIT=1 \
/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge \
  /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
  --edge-file "${EDGE_FILE}" --timeout 180
```

Observed batch 2:

```text
maintenance diagnostic mismatch batch=2 overflow=1 target=-1 expected_target=1
PARTITIONED_CSR_E2E_BATCH case=edge_file batch=2 input_edges=1 target_level=-1 persisted=0 overflow=1
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_measure_carry_probe_hw_20260712_211600/split_edge_file_fanout_full_plus_one/run.log
```

Balanced `131072+1` edge-file probe:

```bash
cd /home/chuxiao/grasu-regraph-integration
RESULT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_measure_carry_probe_hw_20260712_211600
CASE_DIR="${RESULT_ROOT}/split_edge_file_balanced_full_plus_one"
mkdir -p "${CASE_DIR}"
EDGE_FILE="${CASE_DIR}/balanced_full_plus_one.edges"

awk 'BEGIN {
  vs=1048576;
  for (i=0; i<131072; i++) {
    p=i%16;
    local=int(i/16)+1;
    printf "%d %d 1 1\n", i % 64, p*vs + local;
  }
  printf "64 %d 1 1\n", 900000;
}' > "${EDGE_FILE}"

source /opt/xilinx/xrt/setup.sh
export XILINX_XRT=/opt/xilinx/xrt
export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}

SPINE_PARTITIONED_SPLIT=1 \
/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge \
  /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
  --edge-file "${EDGE_FILE}" --timeout 180
```

Observed:

```text
PARTITIONED_CSR_E2E_BATCH case=edge_file batch=2 input_edges=1 target_level=1 consumed_mask=1 persisted=131073 overflow=0 maint_ms=672.46
PARTITIONED_CSR_E2E_SMOKE PASS case=edge_file ... kernel_e2e_ms=4284.03 errors=0
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_measure_carry_probe_hw_20260712_211600/split_edge_file_balanced_full_plus_one/run.log
```

## Implication For Spine vs GraSU+ReGraph

For fair performance comparison, Spine inputs must be classified by destination
partition distribution:

- Balanced destination distribution: Spine can cross the first batch boundary,
  so these are valid performance cases.
- Highly concentrated destination distribution: Spine may hit per-partition
  capacity during level carry. These should be reported as capacity/architecture
  limitation cases, not as normal timing failures.

This matters for hot-destination graphs. GraSU+ReGraph can still run the same
logical graph, while Spine's current partitioned level layout may be unable to
place it after a carry. That is a real architectural disadvantage, but it should
be described as a storage-layout capacity bottleneck rather than a generic
"hardware hang".

## Tooling Gap

The old `--measure-carry` diagnostic is not split-aware. When used with the
split xclbin it fails with:

```text
[XRT] ERROR: kernel 'spine_partitioned_e2e_kernel' not found
```

The normal split edge-file and generated-batch paths do use
`spine_partconv_rdmaint_kernel` and `spine_partconv_compute_kernel` correctly.
A useful next cleanup is to make `--measure-carry` split-aware too, but the
capacity conclusion above does not require a hardware rebuild.

## Tooling Update

`scripts/summarize_spine_builtin_result.py` now marks explicit hardware
overflow logs as:

```text
UNSUPPORTED_CAPACITY
```

instead of mixing them into ordinary `FAIL` rows. This keeps future comparison
tables from treating a graph that cannot fit the Spine level layout as a normal
performance failure.

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/summarize_spine_builtin_result.py
```

