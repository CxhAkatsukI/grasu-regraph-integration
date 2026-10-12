#ifndef GRASU_REGRAPH_DIRECTORY_TILE_HPP
#define GRASU_REGRAPH_DIRECTORY_TILE_HPP

// Experimental bounded cache, on the existing shared AXI master. Directory
// loads finish before the edge loop, avoiding its memory-dependent recurrence.
template<bool Banked = false>
static void read_tiled_row_segments(const ap_uint<512> *pma0,
                                    const ap_uint<512> *pma1,
                                    const ap_uint<512> *pma2,
                                    const ap_uint<512> *pma3,
                                    const ap_uint<512> *rows,
                                    unsigned node_count, unsigned capacity,
                                    unsigned max_cache_segment,
                                    hls::stream<loaded_row_segment> &loaded,
                                    hls::stream<ap_uint<512>> &even,
                                    hls::stream<ap_uint<512>> &odd,
                                    ap_uint<64> banked_total = 0)
{
#pragma HLS INLINE off
    ap_uint<64> total = 0;
    if (Banked) total = banked_total;
    else if (node_count != 0) {
        ap_uint<64> unused = 0;
        unpack_row_bounds(read_row_line_entry(rows, node_count - 1), unused, total);
        if (total > capacity) total = capacity;
    }
    constexpr unsigned tile_rows = GRASU_REGRAPH_DIRECTORY_TILE_ROWS;
    ap_uint<64> cache[tile_rows];
#pragma HLS ARRAY_PARTITION variable=cache cyclic factor=8
    ap_uint<64> emitted = 0;
read_tile_loop:
    for (unsigned base = 0; base < node_count; base += tile_rows) {
        if (emitted >= total) break;
        const unsigned count = node_count - base < tile_rows ? node_count - base : tile_rows;
        bool has_segments = false;
load_directory_tile_loop:
        for (unsigned line = 0; line < (count + 7) / 8; ++line) {
#pragma HLS PIPELINE II=1
            const ap_uint<512> value = rows[(base >> 3) + line];
            bool occupied = false;
unpack_directory_tile_loop:
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                const ap_uint<64> packed = value.range(lane * 64 + 63, lane * 64);
                cache[line * 8 + lane] = packed;
                ap_uint<64> begin = 0, end = 0;
                unpack_row_bounds(packed, begin, end);
                if (end > capacity) end = capacity;
                occupied |= line * 8 + lane < count && (begin >> 4) < ((end + 15) >> 4);
            }
            has_segments |= occupied;
        }
        if (!has_segments) continue;
        unsigned source = base;
        ap_uint<64> begin = 0, end = 0;
        unpack_row_bounds(cache[0], begin, end);
        if (end > capacity) end = capacity;
        ap_uint<64> segment = begin >> 4;
        ap_uint<64> limit = (end + 15) >> 4;
read_tiled_sources_loop:
        while (source < base + count && emitted < total) {
#pragma HLS PIPELINE II=1
            if (segment < limit) {
                loaded_row_segment record;
                record.task = {source, begin, end, segment, total, false};
                if (Banked) record.data = (segment & 1) ? odd.read() : even.read();
                else record.data = read_pma_segment(pma0, pma1, pma2, pma3,
                                                    segment, max_cache_segment);
                loaded.write(record);
                ++segment;
                emitted += 16;
            } else {
                ++source;
                unpack_row_bounds(cache[source & (tile_rows - 1)], begin, end);
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
