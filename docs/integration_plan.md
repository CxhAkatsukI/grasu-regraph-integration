# GraSU + ReGraph Integration Plan

Created: 2026-07-09

## Why This Workspace Exists

Spine currently measures an end-to-end path:

```text
edge update -> level maintenance -> active frontier -> SSSP convergence
```

GraSU by itself measures dynamic graph update throughput only. ReGraph by itself
measures static graph computation with a GAS-style scatter/gather/apply model.
Putting GraSU and ReGraph together gives a more comparable baseline:

```text
GraSU update -> export updated graph -> ReGraph compute
```

## Functional Boundaries

- Spine: dynamic graph maintenance plus SSSP relaxation.
- GraSU: dynamic graph update library; insert/delete updates into PMA-like
  adjacency storage.
- ReGraph: static graph accelerator generator/runtime for PR, BFS, and CC.

## Comparison Matrix

1. Update only

```text
Spine max_iterations=0
vs
GraSU update-only
```

2. Compute only

```text
Spine convergence-only or update+tiny-maintenance
vs
ReGraph BFS/SSSP-like compute
```

3. End to end

```text
Spine update + SSSP
vs
GraSU update + export + ReGraph BFS/SSSP-like compute
```

## Important Caveat

ReGraph does not currently provide a weighted SSSP UDF. For an immediate
apples-to-apples experiment, use unit-weight graphs so weighted SSSP reduces to
BFS distance. For a stricter comparison, add a ReGraph SSSP UDF.

## Near-Term Tasks

1. Define a shared workload format:
   - static base edges
   - update batch edges with insert/delete markers
   - optional expected final graph

2. Add a converter:
   - GraSU input graph/update format
   - ReGraph graph dataset format
   - Spine host benchmark input format

3. Add a GraSU export step:
   - run GraSU update
   - recover final edge list with original vertex IDs
   - write ReGraph-readable graph
   - current first-pass script uses the GraSU result file as the checked final
     graph because the existing GraSU host has `OUTPUT_RESULT=0`

4. Add benchmark scripts:
   - GraSU update-only timing
   - ReGraph BFS/PR/CC timing
   - end-to-end composed timing

5. Keep timing categories separate:
   - update kernel time
   - export/conversion time
   - ReGraph preprocessing time
   - ReGraph kernel compute time
   - total wall time
