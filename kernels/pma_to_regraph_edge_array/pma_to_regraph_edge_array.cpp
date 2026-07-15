#include <ap_int.h>

#if defined(SW_EMU) && !defined(__SYNTHESIS__)
#include <stdio.h>
#define COMPACT_DEBUG_PRINTF(fmt, ...) do { printf(fmt, ##__VA_ARGS__); fflush(stdout); } while (0)
#else
#define COMPACT_DEBUG_PRINTF(fmt, ...)
#endif

static constexpr unsigned kSegmentSize = 16;
static constexpr unsigned kPmaEmptyMask = 0x80000000u;
static constexpr unsigned kDstLocalMask = 0x7ffffu;
static constexpr unsigned kUnitWeight = 1u;
static constexpr unsigned kWeightShift = 19;
static constexpr unsigned kEdgesPerBurst = 8;

static ap_uint<32> pack_regraph_dst(ap_uint<32> dst, bool dummy)
{
#pragma HLS INLINE
    ap_uint<32> packed = (dst & kDstLocalMask) | (kUnitWeight << kWeightShift);
    if (dummy) {
        packed |= kPmaEmptyMask;
    }
    return packed;
}

static ap_uint<512> read_pma_segment(const ap_uint<512> *pma0,
                                     const ap_uint<512> *pma1,
                                     const ap_uint<512> *pma2,
                                     const ap_uint<512> *pma3,
                                     ap_uint<64> segment_idx,
                                     unsigned max_cache_segment)
{
#pragma HLS INLINE
    const ap_uint<64> local_idx = segment_idx >> 1;
    const ap_uint<64> cache_segment_limit =
        static_cast<ap_uint<64>>(max_cache_segment) * 2;

    if (segment_idx < cache_segment_limit) {
        return (segment_idx & 0x1) ? pma2[local_idx] : pma0[local_idx];
    }
    return (segment_idx & 0x1) ? pma3[local_idx] : pma1[local_idx];
}

static void unpack_row_bounds(ap_uint<64> packed,
                              ap_uint<64> &begin,
                              ap_uint<64> &end)
{
#pragma HLS INLINE
    begin = packed.range(63, 32);
    end = packed.range(31, 0);
}

static void append_edge(ap_uint<512> *edge_array,
                        ap_uint<512> &burst,
                        unsigned &lane,
                        ap_uint<32> &burst_idx,
                        ap_uint<64> &emitted_slots,
                        unsigned compact_edge_slots,
                        ap_uint<32> src,
                        ap_uint<32> raw_dst,
                        bool dummy)
{
#pragma HLS INLINE
    if (emitted_slots >= compact_edge_slots) {
        return;
    }

    const ap_uint<32> out_src = dummy ? (src | kPmaEmptyMask) : src;
    const ap_uint<32> out_dst = pack_regraph_dst(raw_dst, dummy);
    const unsigned base = lane * 64;
    burst.range(base + 31, base) = out_src;
    burst.range(base + 63, base + 32) = out_dst;

    lane++;
    emitted_slots++;
    if (lane == kEdgesPerBurst) {
        edge_array[burst_idx] = burst;
        burst_idx++;
        burst = 0;
        lane = 0;
    }
}

extern "C" {
void pma_to_regraph_edge_array(const ap_uint<512> *pma0,
                               const ap_uint<512> *pma1,
                               const ap_uint<512> *pma2,
                               const ap_uint<512> *pma3,
                               const ap_uint<64> *row_offset,
                               unsigned node_count,
                               unsigned pma_slot_count,
                               unsigned compact_edge_slots,
                               unsigned max_cache_segment,
                               ap_uint<512> *edge_array)
{
#pragma HLS INTERFACE m_axi port=pma0 offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=pma1 offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=pma2 offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=pma3 offset=slave bundle=gmem3
#pragma HLS INTERFACE m_axi port=row_offset offset=slave bundle=gmem4
#pragma HLS INTERFACE m_axi port=edge_array offset=slave bundle=gmem5
#pragma HLS INTERFACE s_axilite port=pma0 bundle=control
#pragma HLS INTERFACE s_axilite port=pma1 bundle=control
#pragma HLS INTERFACE s_axilite port=pma2 bundle=control
#pragma HLS INTERFACE s_axilite port=pma3 bundle=control
#pragma HLS INTERFACE s_axilite port=row_offset bundle=control
#pragma HLS INTERFACE s_axilite port=node_count bundle=control
#pragma HLS INTERFACE s_axilite port=pma_slot_count bundle=control
#pragma HLS INTERFACE s_axilite port=compact_edge_slots bundle=control
#pragma HLS INTERFACE s_axilite port=max_cache_segment bundle=control
#pragma HLS INTERFACE s_axilite port=edge_array bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    COMPACT_DEBUG_PRINTF("[KDEBUG] pma_compact: begin nodes=%u pma_slots=%u compact_slots=%u\n",
                         node_count, pma_slot_count, compact_edge_slots);

    ap_uint<64> total_slots = 0;
    if (node_count != 0) {
        ap_uint<64> last_begin = 0;
        unpack_row_bounds(row_offset[node_count - 1], last_begin, total_slots);
        if (total_slots > pma_slot_count) {
            total_slots = pma_slot_count;
        }
    }

    ap_uint<512> burst = 0;
    unsigned lane = 0;
    ap_uint<32> burst_idx = 0;
    ap_uint<64> emitted_slots = 0;
    ap_uint<64> valid_edges = 0;

source_loop:
    for (unsigned src = 0; src < node_count; ++src) {
        ap_uint<64> begin = 0;
        ap_uint<64> end = 0;
        unpack_row_bounds(row_offset[src], begin, end);
        if (end > pma_slot_count) {
            end = pma_slot_count;
        }

        const ap_uint<64> begin_segment = begin >> 4;
        const ap_uint<64> end_segment = (end + (kSegmentSize - 1)) >> 4;

segment_loop:
        for (ap_uint<64> segment = begin_segment; segment < end_segment; ++segment) {
            const ap_uint<512> pma_segment =
                read_pma_segment(pma0, pma1, pma2, pma3, segment, max_cache_segment);

lane_loop:
            for (unsigned pma_lane = 0; pma_lane < kSegmentSize; ++pma_lane) {
#pragma HLS PIPELINE II=1
                const ap_uint<64> slot = (segment << 4) + pma_lane;
                const ap_uint<32> raw_dst =
                    pma_segment.range(pma_lane * 32 + 31, pma_lane * 32);
                const bool valid = !raw_dst[31] && slot >= begin && slot < end &&
                                   slot < total_slots;
                if (valid) {
                    append_edge(edge_array, burst, lane, burst_idx, emitted_slots,
                                compact_edge_slots, src, raw_dst, false);
                    valid_edges++;
                }
            }
        }
    }

pad_loop:
    while (emitted_slots < compact_edge_slots) {
#pragma HLS PIPELINE II=1
        append_edge(edge_array, burst, lane, burst_idx, emitted_slots,
                    compact_edge_slots, 0, 0, true);
    }
    if (lane != 0) {
        edge_array[burst_idx] = burst;
    }

    COMPACT_DEBUG_PRINTF("[KDEBUG] pma_compact: done valid=%u emitted=%u bursts=%u\n",
                         static_cast<unsigned>(valid_edges),
                         static_cast<unsigned>(emitted_slots),
                         static_cast<unsigned>(burst_idx));
}
}
