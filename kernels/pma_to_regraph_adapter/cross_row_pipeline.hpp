#ifndef GRASU_REGRAPH_CROSS_ROW_PIPELINE_HPP
#define GRASU_REGRAPH_CROSS_ROW_PIPELINE_HPP

// Internal FIFO records, not a new external row/edge ABI. One terminal record
// closes every stage, including empty input; no host-created sparse index.
struct row_segment_task {
    unsigned source;
    ap_uint<64> begin;
    ap_uint<64> end;
    ap_uint<64> segment;
    ap_uint<64> total_slots;
    bool terminal;
};

struct loaded_row_segment {
    row_segment_task task;
    ap_uint<512> data;
};

#if GRASU_REGRAPH_CONTINUOUS_DIRECTORY
#include "continuous_directory.hpp"
#endif

static void read_row_segments(const ap_uint<512> *pma0,
                              const ap_uint<512> *pma1,
                              const ap_uint<512> *pma2,
                              const ap_uint<512> *pma3,
                              const ap_uint<512> *rows,
                              unsigned node_count, unsigned capacity,
                              unsigned max_cache_segment,
                              hls::stream<loaded_row_segment> &loaded)
{
#pragma HLS INLINE off
    ap_uint<64> total = 0;
    if (node_count != 0) {
        ap_uint<64> unused = 0;
        unpack_row_bounds(read_row_line_entry(rows, node_count - 1), unused, total);
        if (total > capacity) total = capacity;
    }
    ap_uint<64> cache[8];
#pragma HLS ARRAY_PARTITION variable=cache complete
    ap_uint<64> emitted = 0;
read_line_loop:
    for (unsigned base = 0; base < node_count; base += 8) {
        if (emitted >= total) break;
        read_cached_row_line(rows, base, cache);
        // Test segment bounds, not begin != end: an unaligned empty interval
        // can still occupy a masked segment under the historical packet ABI.
        bool has_segments = false;
check_cached_row_line:
        for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
            ap_uint<64> row_begin = 0, row_end = 0;
            unpack_row_bounds(cache[lane], row_begin, row_end);
            if (row_end > capacity) row_end = capacity;
            if (lane < node_count - base &&
                (row_begin >> 4) < ((row_end + (kSegmentSize - 1)) >> 4))
                has_segments = true;
        }
        if (!has_segments) continue;
        unsigned source = base;
        ap_uint<64> begin = 0, end = 0;
        unpack_row_bounds(cache[0], begin, end);
        if (end > capacity) end = capacity;
        ap_uint<64> segment = begin >> 4;
        ap_uint<64> limit = (end + (kSegmentSize - 1)) >> 4;
        // Both reads share one AXI master. Flatten source/segment traversal
        // inside a cached line so PMA loads can overlap across short rows.
read_cached_sources_loop:
        while (source < node_count && source - base < 8 && emitted < total) {
#pragma HLS PIPELINE II=1
            if (segment < limit) {
                loaded_row_segment record;
                record.task = {source, begin, end, segment, total, false};
                record.data = read_pma_segment(pma0, pma1, pma2, pma3,
                                               segment, max_cache_segment);
                loaded.write(record);
                ++segment;
                emitted += 16;
            } else {
                ++source;
                unpack_row_bounds(cache[source & 7], begin, end);
                if (end > capacity) end = capacity;
                segment = begin >> 4;
                limit = (end + (kSegmentSize - 1)) >> 4;
            }
        }
    }
    loaded_row_segment terminal = {};
    terminal.task.terminal = true;
    loaded.write(terminal);
}

static void publish_row_segments(hls::stream<loaded_row_segment> &loaded,
                                 unsigned part_dst_offset,
                                 unsigned part_vertex_count,
                                 hls::stream<edge_burst_pkt_t> &output)
{
#pragma HLS INLINE off
    ap_uint<64> emitted = 0;
publish_segment_loop:
    while (true) {
        const loaded_row_segment record = loaded.read();
        if (record.task.terminal) break;
publish_half_loop:
        for (unsigned half = 0; half < 2; ++half) {
#pragma HLS PIPELINE II=1
            edge_burst_pkt_t packet;
            packet.data = 0;
            packet.keep = -1;
            packet.strb = -1;
publish_lane_loop:
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                const ap_uint<64> slot = (record.task.segment << 4) + (half << 3) + lane;
                const unsigned pma_lane = half * 8 + lane;
                const ap_uint<32> raw = record.data.range(pma_lane * 32 + 31, pma_lane * 32);
                const ap_uint<32> local = raw & kDstLocalMask;
#if GRASU_REGRAPH_SHARDED_PMA
                const bool in_partition = local < part_vertex_count;
                ap_uint<32> destination = raw;
#if GRASU_REGRAPH_DESTINATION_ONLY
                destination = ap_uint<32>(part_dst_offset) + local;
#endif
#else
                const ap_uint<33> partition_end = ap_uint<33>(part_dst_offset) + part_vertex_count;
                const bool in_partition = local >= part_dst_offset && ap_uint<33>(local) < partition_end;
                const ap_uint<32> destination = raw;
#endif
                const bool dummy = raw[31] || slot < record.task.begin || slot >= record.task.end
                                   || slot >= record.task.total_slots || !in_partition;
                const ap_uint<32> source = dummy ? ap_uint<32>(record.task.source) | kPmaEmptyMask
                                                 : ap_uint<32>(record.task.source);
                write_edge_burst(packet, lane, source, pack_regraph_dst(destination, dummy));
            }
            emitted += 8;
            packet.last = emitted >= record.task.total_slots;
            output.write(packet);
        }
    }
}

static void cross_row_pipeline(const ap_uint<512> *pma0,
                               const ap_uint<512> *pma1,
                               const ap_uint<512> *pma2,
                               const ap_uint<512> *pma3,
                               const ap_uint<512> *rows,
                               unsigned node_count, unsigned capacity,
                               unsigned max_cache_segment,
                               unsigned part_dst_offset, unsigned part_vertex_count,
                               hls::stream<edge_burst_pkt_t> &output)
{
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<loaded_row_segment> loaded("loaded_row_segments");
#pragma HLS STREAM variable=loaded depth=16
#if GRASU_REGRAPH_CONTINUOUS_DIRECTORY
    read_continuous_row_segments(pma0, pma1, pma2, pma3, rows, node_count, capacity,
                                 max_cache_segment, loaded);
#else
    read_row_segments(pma0, pma1, pma2, pma3, rows, node_count, capacity,
                      max_cache_segment, loaded);
#endif
    publish_row_segments(loaded, part_dst_offset, part_vertex_count, output);
}

#endif
