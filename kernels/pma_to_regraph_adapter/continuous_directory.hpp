#ifndef GRASU_REGRAPH_CONTINUOUS_DIRECTORY_HPP
#define GRASU_REGRAPH_CONTINUOUS_DIRECTORY_HPP

// Keep directory and segment reads in one process on the existing AXI master.
// A single loop crosses cached-line boundaries without draining per eight rows.
// Rejected timing candidate: synthesis achieved II=71, not II=1. Default off.
static void read_continuous_row_segments(const ap_uint<512> *pma0,
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
    unsigned source = 0;
    ap_uint<64> begin = 0, end = 0, segment = 0, limit = 0, emitted = 0;
    bool need_line = true;
read_continuous_sources_loop:
    while (source < node_count && emitted < total) {
#pragma HLS PIPELINE II=1
        if (need_line) {
            read_cached_row_line(rows, source, cache);
            bool occupied = false;
check_continuous_row_line:
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                ap_uint<64> row_begin = 0, row_end = 0;
                unpack_row_bounds(cache[lane], row_begin, row_end);
                if (row_end > capacity) row_end = capacity;
                if (lane < node_count - source &&
                    (row_begin >> 4) < ((row_end + 15) >> 4)) occupied = true;
            }
            if (occupied) {
                unpack_row_bounds(cache[0], begin, end);
                if (end > capacity) end = capacity;
                segment = begin >> 4;
                limit = (end + 15) >> 4;
                need_line = false;
            } else {
                source += 8;
            }
        } else if (segment < limit) {
            loaded_row_segment record;
            record.task = {source, begin, end, segment, total, false};
            record.data = read_pma_segment(pma0, pma1, pma2, pma3,
                                           segment, max_cache_segment);
            loaded.write(record);
            ++segment;
            emitted += 16;
        } else {
            ++source;
            need_line = (source & 7) == 0;
            if (!need_line) {
                unpack_row_bounds(cache[source & 7], begin, end);
                if (end > capacity) end = capacity;
                segment = begin >> 4;
                limit = (end + 15) >> 4;
            }
        }
    }
    loaded_row_segment terminal = {};
    terminal.task.terminal = true;
    loaded.write(terminal);
}

#endif
