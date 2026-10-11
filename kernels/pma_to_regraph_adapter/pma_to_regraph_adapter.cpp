#include <hls_stream.h>
#include <hls_streamofblocks.h>
#include <ap_axi_sdata.h>
#include <ap_int.h>
#if defined(SW_EMU) && !defined(__SYNTHESIS__)
#include <stdio.h>
#define ADAPTER_DEBUG_PRINTF(fmt, ...) do { printf(fmt, ##__VA_ARGS__); fflush(stdout); } while (0)
#else
#define ADAPTER_DEBUG_PRINTF(fmt, ...)
#endif

typedef ap_axiu<512, 0, 0, 0> edge_burst_pkt_t;

static constexpr unsigned kSegmentSize = 16;
static constexpr unsigned kPmaEmptyMask = 0x80000000u;
static constexpr unsigned kDstLocalMask = 0x7ffffu;
static constexpr unsigned kUnitWeight = 1u;
static constexpr unsigned kWeightShift = 19;

#ifndef GRASU_REGRAPH_WEIGHTED_PMA
#define GRASU_REGRAPH_WEIGHTED_PMA 0
#endif

#ifndef GRASU_REGRAPH_DESTINATION_ONLY
#define GRASU_REGRAPH_DESTINATION_ONLY 0
#endif

#ifndef GRASU_REGRAPH_SHARE_ROW_OFFSET_PORT
#define GRASU_REGRAPH_SHARE_ROW_OFFSET_PORT 0
#endif

#ifndef GRASU_REGRAPH_SHARDED_PMA
#define GRASU_REGRAPH_SHARDED_PMA 0
#endif

#ifndef GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS
#define GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS 0
#endif

#ifndef GRASU_REGRAPH_ROW_PREFETCH
#define GRASU_REGRAPH_ROW_PREFETCH 0
#endif

#ifndef GRASU_REGRAPH_STOP_AFTER_LAST
#define GRASU_REGRAPH_STOP_AFTER_LAST 0
#endif

#ifndef GRASU_REGRAPH_SKIP_EMPTY_SEGMENT
#define GRASU_REGRAPH_SKIP_EMPTY_SEGMENT 0
#endif

#if GRASU_REGRAPH_SKIP_EMPTY_SEGMENT != 0 && GRASU_REGRAPH_SKIP_EMPTY_SEGMENT != 1
#error "GRASU_REGRAPH_SKIP_EMPTY_SEGMENT must be 0 or 1"
#endif

#if GRASU_REGRAPH_STOP_AFTER_LAST != 0 && GRASU_REGRAPH_STOP_AFTER_LAST != 1
#error "GRASU_REGRAPH_STOP_AFTER_LAST must be 0 or 1"
#endif

#if GRASU_REGRAPH_ROW_PREFETCH != 0 && GRASU_REGRAPH_ROW_PREFETCH != 1
#error "GRASU_REGRAPH_ROW_PREFETCH must be 0 or 1"
#endif

#if GRASU_REGRAPH_ROW_PREFETCH
#include "row_prefetch.hpp"
#endif

#if GRASU_REGRAPH_WEIGHTED_PMA != 0 && GRASU_REGRAPH_WEIGHTED_PMA != 1
#error "GRASU_REGRAPH_WEIGHTED_PMA must be 0 or 1"
#endif

#if GRASU_REGRAPH_DESTINATION_ONLY != 0 && GRASU_REGRAPH_DESTINATION_ONLY != 1
#error "GRASU_REGRAPH_DESTINATION_ONLY must be 0 or 1"
#endif

#if GRASU_REGRAPH_SHARE_ROW_OFFSET_PORT != 0 && GRASU_REGRAPH_SHARE_ROW_OFFSET_PORT != 1
#error "GRASU_REGRAPH_SHARE_ROW_OFFSET_PORT must be 0 or 1"
#endif

#if GRASU_REGRAPH_SHARDED_PMA != 0 && GRASU_REGRAPH_SHARDED_PMA != 1
#error "GRASU_REGRAPH_SHARDED_PMA must be 0 or 1"
#endif

#if GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS != 0 && \
    GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS != 1
#error "GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS must be 0 or 1"
#endif

#if GRASU_REGRAPH_WEIGHTED_PMA && GRASU_REGRAPH_DESTINATION_ONLY
#error "weighted and destination-only PMA output modes are mutually exclusive"
#endif

static ap_uint<32> pack_regraph_dst(ap_uint<32> dst, bool dummy)
{
#pragma HLS INLINE
#if GRASU_REGRAPH_WEIGHTED_PMA
    ap_uint<32> packed = dst & ~ap_uint<32>(kPmaEmptyMask);
#elif GRASU_REGRAPH_DESTINATION_ONLY
#if GRASU_REGRAPH_SHARDED_PMA
    ap_uint<32> packed = dst & ~ap_uint<32>(kPmaEmptyMask);
#else
    ap_uint<32> packed = dst & kDstLocalMask;
#endif
#else
    ap_uint<32> packed = (dst & kDstLocalMask) | (kUnitWeight << kWeightShift);
#endif
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

static void write_edge_burst(edge_burst_pkt_t &pkt,
                             unsigned lane,
                             ap_uint<32> src,
                             ap_uint<32> dst)
{
#pragma HLS INLINE
    const unsigned base = lane * 64;
    pkt.data.range(base + 31, base) = src;
    pkt.data.range(base + 63, base + 32) = dst;
}

static void emit_row_segments(const ap_uint<512> *pma0,
                              const ap_uint<512> *pma1,
                              const ap_uint<512> *pma2,
                              const ap_uint<512> *pma3,
                              unsigned max_cache_segment,
                              unsigned part_dst_offset,
                              unsigned part_vertex_count,
                              unsigned src,
                              ap_uint<64> begin,
                              ap_uint<64> end,
                              ap_uint<64> total_slots,
                              ap_uint<64> &emitted_slots,
                              unsigned &emitted_bursts,
                              hls::stream<edge_burst_pkt_t> &edge_burst_out)
{
#if GRASU_REGRAPH_SKIP_EMPTY_SEGMENT
// Keep the empty-row decision in the caller, outside the pipelined helper.
#pragma HLS INLINE off
#else
#pragma HLS INLINE
#endif
    edge_burst_pkt_t out;
    const ap_uint<64> begin_segment = begin >> 4;
    const ap_uint<64> end_segment = (end + (kSegmentSize - 1)) >> 4;
segment_loop:
    for (ap_uint<64> segment = begin_segment; segment < end_segment; ++segment) {
#pragma HLS PIPELINE II=1
        const ap_uint<512> pma_segment =
            read_pma_segment(pma0, pma1, pma2, pma3, segment, max_cache_segment);

    half_segment_loop:
        for (unsigned half = 0; half < 2; ++half) {
            out.data = 0;
            out.keep = -1;
            out.strb = -1;
            out.last = 0;

        lane_loop:
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                const ap_uint<64> slot = (segment << 4) + (half << 3) + lane;
                const unsigned pma_lane = half * 8 + lane;
                ap_uint<32> raw_dst = pma_segment.range(pma_lane * 32 + 31,
                                                        pma_lane * 32);
                const ap_uint<32> local_dst = raw_dst & kDstLocalMask;
#if GRASU_REGRAPH_SHARDED_PMA
                const bool in_partition = local_dst < part_vertex_count;
                ap_uint<32> adapter_dst = raw_dst;
#if GRASU_REGRAPH_DESTINATION_ONLY
                adapter_dst = ap_uint<32>(part_dst_offset) + local_dst;
#endif
#else
                const ap_uint<33> partition_end =
                    ap_uint<33>(part_dst_offset) + part_vertex_count;
                const ap_uint<32> global_dst = local_dst;
                const bool in_partition =
                    global_dst >= part_dst_offset &&
                    ap_uint<33>(global_dst) < partition_end;
#endif
                bool dummy = raw_dst[31] || slot < begin || slot >= end ||
                             slot >= total_slots || !in_partition;
                const ap_uint<32> out_src = dummy ? (ap_uint<32>(src) | kPmaEmptyMask)
                                                  : ap_uint<32>(src);
#if GRASU_REGRAPH_SHARDED_PMA
                const ap_uint<32> out_dst = pack_regraph_dst(adapter_dst, dummy);
#else
                const ap_uint<32> out_dst = pack_regraph_dst(raw_dst, dummy);
#endif
                write_edge_burst(out, lane, out_src, out_dst);
            }

            emitted_slots += 8;
            out.last = (emitted_slots >= total_slots);
            edge_burst_out.write(out);
            emitted_bursts++;
            if (emitted_bursts <= 4 || (emitted_bursts & 0xf) == 0) {
                ADAPTER_DEBUG_PRINTF("[KDEBUG] adapter: emitted burst=%u slots=%u last=%u\n",
                                     emitted_bursts,
                                     static_cast<unsigned>(emitted_slots),
                                     static_cast<unsigned>(out.last));
            }
        }
    }
}

extern "C" {
void pma_to_regraph_adapter(const ap_uint<512> *pma0,
                            const ap_uint<512> *pma1,
                            const ap_uint<512> *pma2,
                            const ap_uint<512> *pma3,
                            const ap_uint<64> *row_offset,
                            unsigned node_count,
                            unsigned pma_slot_count,
                            unsigned max_cache_segment,
                            unsigned part_dst_offset,
                            unsigned part_vertex_count,
                            hls::stream<edge_burst_pkt_t> &edge_burst_out)
{
#if GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS
#ifdef GRASU_REGRAPH_COSIM_DEPTH
#pragma HLS INTERFACE m_axi port=pma0 offset=slave bundle=gmem0 depth=256
#pragma HLS INTERFACE m_axi port=pma1 offset=slave bundle=gmem0 depth=256
#pragma HLS INTERFACE m_axi port=pma2 offset=slave bundle=gmem0 depth=256
#pragma HLS INTERFACE m_axi port=pma3 offset=slave bundle=gmem0 depth=256
#pragma HLS INTERFACE m_axi port=row_offset offset=slave bundle=gmem0 depth=1025
#else
#pragma HLS INTERFACE m_axi port=pma0 offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=pma1 offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=pma2 offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=pma3 offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=row_offset offset=slave bundle=gmem0
#endif
#else
#pragma HLS INTERFACE m_axi port=pma0 offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=pma1 offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=pma2 offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=pma3 offset=slave bundle=gmem3
#if GRASU_REGRAPH_SHARE_ROW_OFFSET_PORT
#pragma HLS INTERFACE m_axi port=row_offset offset=slave bundle=gmem0
#else
#pragma HLS INTERFACE m_axi port=row_offset offset=slave bundle=gmem4
#endif
#endif
#pragma HLS INTERFACE s_axilite port=pma0 bundle=control
#pragma HLS INTERFACE s_axilite port=pma1 bundle=control
#pragma HLS INTERFACE s_axilite port=pma2 bundle=control
#pragma HLS INTERFACE s_axilite port=pma3 bundle=control
#pragma HLS INTERFACE s_axilite port=row_offset bundle=control
#pragma HLS INTERFACE s_axilite port=node_count bundle=control
#pragma HLS INTERFACE s_axilite port=pma_slot_count bundle=control
#pragma HLS INTERFACE s_axilite port=max_cache_segment bundle=control
#pragma HLS INTERFACE s_axilite port=part_dst_offset bundle=control
#pragma HLS INTERFACE s_axilite port=part_vertex_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE axis port=edge_burst_out

    ADAPTER_DEBUG_PRINTF(
        "[KDEBUG] adapter: begin nodes=%u pma_slots=%u dst=[%u,%u)\n",
        node_count, pma_slot_count, part_dst_offset,
        part_dst_offset + part_vertex_count);

    ap_uint<64> total_slots = 0;
    // HLS may issue this read speculatively even when the value is discarded.
    const unsigned last_source = node_count == 0 ? 0 : node_count - 1;
    if (node_count != 0) {
        ap_uint<64> last_begin = 0;
        unpack_row_bounds(row_offset[last_source], last_begin, total_slots);
        if (total_slots > pma_slot_count) {
            total_slots = pma_slot_count;
        }
    }
    ADAPTER_DEBUG_PRINTF("[KDEBUG] adapter: total_slots=%u\n",
                         static_cast<unsigned>(total_slots));

    ap_uint<64> emitted_slots = 0;
    unsigned emitted_bursts = 0;
#if GRASU_REGRAPH_ROW_PREFETCH
    ap_uint<64> row_cache[kRowPrefetchCount];
#pragma HLS ARRAY_PARTITION variable=row_cache complete
#endif

source_loop:
    for (unsigned src = 0; src < node_count; ++src) {
#if GRASU_REGRAPH_STOP_AFTER_LAST
        // The aligned, monotonic row ABI uses the final row end as the stream
        // length. Once its last packet is sent, no later source has any slots.
        if (emitted_slots >= total_slots) break;
#endif
        ap_uint<64> begin = 0;
        ap_uint<64> end = 0;
#if GRASU_REGRAPH_ROW_PREFETCH
        unpack_row_bounds(
            read_prefetched_row(row_offset, src, node_count, row_cache),
            begin, end);
#else
        unpack_row_bounds(row_offset[src], begin, end);
#endif
        if (end > pma_slot_count) {
            end = pma_slot_count;
        }

slot_loop:
        const ap_uint<64> begin_segment = begin >> 4;
        const ap_uint<64> end_segment = (end + (kSegmentSize - 1)) >> 4;

#if GRASU_REGRAPH_SKIP_EMPTY_SEGMENT
        // Avoid starting the pipelined helper when it cannot emit a packet.
        // Compare segment bounds so partial, unaligned rows retain their ABI.
        if (begin_segment >= end_segment) continue;
#endif

        emit_row_segments(pma0, pma1, pma2, pma3, max_cache_segment,
                          part_dst_offset, part_vertex_count, src, begin, end,
                          total_slots, emitted_slots, emitted_bursts, edge_burst_out);
    }
    ADAPTER_DEBUG_PRINTF("[KDEBUG] adapter: done bursts=%u slots=%u\n",
                         emitted_bursts, static_cast<unsigned>(emitted_slots));
}
}
