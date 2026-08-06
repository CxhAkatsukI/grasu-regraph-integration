# Spine PK SSSP U55C evidence

- Date: 2026-08-06
- Spine source: `3678ad488e0d0fe8538a36a11d87ddffa182fa99`
- Algorithm: weighted SSSP
- Workload: PK insertion batch 8
- Vertices: 1,632,803
- Initial edges: 44,603,928
- Destination partitions: 16
- Hot vertices: 248,899
- Hot edges: 24,321,670
- Maintenance: pass, zero overflow
- Propagation: pass in two hardware rounds
- Dynamic setup-inclusive latency: 185.608 ms
- Timing scope: maintenance plus iterative algorithm; static resident graph
  construction and upload are excluded

## Artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| Routed xclbin | `b6e415f0d749d831a5ee5d98acbd691749cbd13b8a20945b306085f668b69862` |
| Host executable | `c3875b941aa1dc18062d3dda6b245712c484837a50629b2ce0b06feed812ded7` |
| Workload | `efddd1bebd16d8fd64b29f17783d2615d8a2513f3f9c541a1a1d353cb81bb2dd` |
| Run log | `b9fc562a92af6a42b54bac02ed899833f917c0cb9d3bb2bfcaf58c6f1a26119e` |

The xclbin predates the host-side resident baseline fix.  The fix uses the
existing hot bitmap, hot-family shards, metadata format, and kernel ABI; no RTL
or HLS datapath changed.
